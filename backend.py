"""CareCommit backend: GitHub + Gemini code review — no UI."""

from __future__ import annotations

import json
import re
import time
from urllib.parse import urlparse

import google.generativeai as genai
import requests

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MAX_OUTPUT_TOKENS = 8192
DIFF_TRUNCATE_LIMIT = 15000  # chars, safety margin for context window

GITHUB_API_BASE = "https://api.github.com"


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse a GitHub repo reference into (owner, repo)."""
    raw = (url or "").strip()
    if not raw:
        raise ValueError("GitHub URL is empty.")

    raw = re.sub(r"^git@github\.com:", "https://github.com/", raw, flags=re.I)

    # Plain owner/repo
    if "/" in raw and "://" not in raw and "@" not in raw.split("/")[0]:
        parts = [p for p in raw.split("/") if p]
        if len(parts) == 2:
            owner, repo = parts[0], parts[1]
            if owner and repo:
                if repo.endswith(".git"):
                    repo = repo.removesuffix(".git")
                _validate_owner_repo(owner, repo)
                return owner, repo
        raise ValueError(
            "Invalid owner/repo format. Expected `owner/repo` with non-empty segments."
        )

    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw

    parsed = urlparse(raw)
    netloc = (parsed.netloc or "").lower().split("@")[-1]
    if netloc not in ("github.com", "www.github.com"):
        raise ValueError(
            f"Host must be github.com (got {parsed.netloc or 'empty'})."
        )

    path = (parsed.path or "").strip("/")
    if not path:
        raise ValueError("Missing repository path (expected /owner/repo).")

    segments = [s for s in path.split("/") if s]
    if len(segments) < 2:
        raise ValueError(
            "Invalid path: need at least owner and repo in the URL path."
        )

    owner, repo = segments[0], segments[1]
    if repo.endswith(".git"):
        repo = repo.removesuffix(".git")

    _validate_owner_repo(owner, repo)
    return owner, repo


def _validate_owner_repo(owner: str, repo: str) -> None:
    segment = re.compile(r"^[a-zA-Z0-9._-]+$")
    if not segment.match(owner) or not segment.match(repo):
        raise ValueError(
            "Invalid owner or repo name (allowed: letters, digits, ., _, -)."
        )


def _github_headers(github_token: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if extra:
        h.update(extra)
    if github_token:
        h["Authorization"] = f"Bearer {github_token}"
    return h


def _raise_github_error(resp: requests.Response) -> None:
    body = resp.text or ""
    raise ConnectionError(f"HTTP {resp.status_code}: {body}")


def fetch_recent_commits(
    owner: str,
    repo: str,
    n: int = 10,
    github_token: str = "",
    ref: str = "",
) -> list[dict]:
    """Fetch recent commits from GitHub REST API. Optional `ref` filters by branch/tag/sha."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits"
    params: dict[str, str | int] = {"per_page": n}
    rref = (ref or "").strip()
    if rref:
        params["sha"] = rref

    resp = requests.get(
        url,
        headers=_github_headers(github_token),
        params=params,
        timeout=30,
    )
    if not resp.ok:
        _raise_github_error(resp)

    data = resp.json()
    if not isinstance(data, list):
        raise ConnectionError(f"Unexpected GitHub response shape: {type(data)}")

    out: list[dict] = []
    for item in data:
        sha_full = item.get("sha") or ""
        commit = item.get("commit") or {}
        author_block = commit.get("author") or {}
        name = author_block.get("name") or ""
        date = author_block.get("date") or ""
        if not name:
            committer = commit.get("committer") or {}
            name = committer.get("name") or ""
            if not date:
                date = committer.get("date") or ""
        msg = commit.get("message") or ""
        html = item.get("html_url") or ""
        out.append(
            {
                "sha": sha_full,
                "short_sha": sha_full[:7] if sha_full else "",
                "message": msg,
                "author": name,
                "date": date,
                "url": html,
            }
        )
    return out


def fetch_commit_diff(
    owner: str, repo: str, sha: str, github_token: str = ""
) -> str:
    """Fetch raw diff for a commit; truncated to DIFF_TRUNCATE_LIMIT."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{sha}"
    resp = requests.get(
        url,
        headers=_github_headers(
            github_token,
            {"Accept": "application/vnd.github.v3.diff"},
        ),
        timeout=60,
    )
    if not resp.ok:
        _raise_github_error(resp)

    text = resp.text or ""
    original_len = len(text)
    if original_len > DIFF_TRUNCATE_LIMIT:
        text = (
            text[:DIFF_TRUNCATE_LIMIT]
            + f"\n\n[DIFF TRUNCATED — original was {original_len} chars]"
        )
    return text


_REVIEW_SYSTEM = """You are a senior software engineer performing a code review on a commit diff. Analyze the changes and return ONLY valid JSON with no markdown fences and no extra text.

Required JSON structure:
{
  "summary": "2-3 sentence overall assessment of the commit",
  "issues": [
    {
      "line": <int or null if not applicable>,
      "severity": "critical" | "high" | "medium" | "low",
      "category": "security" | "bug" | "performance" | "style" | "logic",
      "description": "Clear explanation of the problem",
      "suggested_fix": "Concrete fix or improvement"
    }
  ],
  "score": <int 0-100, where 100 is perfect>,
  "language_detected": "primary language in the diff"
}

Rules:
- Be thorough on security vulnerabilities and logic errors
- If the code is clean, return empty issues array with high score
- Every issue MUST have a concrete suggested_fix, not vague advice
- severity "critical" = will cause data loss, security breach, or crash in production
"""


def _strip_json_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def review_diff(diff_text: str, commit_message: str, gemini_api_key: str) -> dict:
    """Run Gemini code review on the diff."""
    user_message = (
        f"Commit message: {commit_message}\n\nDiff:\n```\n{diff_text}\n```"
    )
    t0 = time.time()
    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            system_instruction=_REVIEW_SYSTEM,
        )
        response = model.generate_content(
            user_message,
            generation_config={
                "max_output_tokens": GEMINI_MAX_OUTPUT_TOKENS,
            },
        )
    except Exception as e:
        return {
            "summary": f"Review failed: {e!s}",
            "issues": [],
            "score": 0,
            "_meta": {"error": str(e)},
        }

    t1 = time.time()
    latency_ms = int((t1 - t0) * 1000)
    usage_md = getattr(response, "usage_metadata", None)
    in_tok = getattr(usage_md, "prompt_token_count", None) if usage_md else None
    out_tok = getattr(usage_md, "candidates_token_count", None) if usage_md else None
    if in_tok is None:
        in_tok = 0
    if out_tok is None:
        out_tok = 0

    try:
        raw_text = response.text
    except (ValueError, AttributeError) as e:
        return {
            "summary": f"Review failed: no model text returned ({e!s})",
            "issues": [],
            "score": 0,
            "_meta": {
                "model": GEMINI_MODEL,
                "latency_ms": latency_ms,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "error": str(e),
            },
        }

    cleaned = _strip_json_fences(raw_text)
    try:
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise json.JSONDecodeError("Expected object", cleaned, 0)
    except json.JSONDecodeError:
        return {
            "summary": "Review failed — model returned invalid JSON",
            "issues": [],
            "score": 0,
            "_meta": {
                "error": "json_parse_failure",
                "raw_response": raw_text[:500],
            },
        }

    parsed.setdefault("summary", "")
    parsed.setdefault("issues", [])
    parsed.setdefault("score", 0)
    parsed.setdefault("language_detected", "")
    parsed["_meta"] = {
        "model": GEMINI_MODEL,
        "latency_ms": latency_ms,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
    }
    return parsed


def run_pipeline(
    owner: str,
    repo: str,
    sha: str,
    commit_message: str,
    gemini_api_key: str,
    github_token: str = "",
) -> dict:
    """Fetch diff, run Gemini review. ``decision`` is ``error`` on diff failure, else ``ok``."""
    wall0 = time.time()

    try:
        diff_text = fetch_commit_diff(owner, repo, sha, github_token)
    except ConnectionError as e:
        elapsed = int((time.time() - wall0) * 1000)
        err = str(e)
        return {
            "review": {
                "summary": f"Failed to fetch diff: {err}",
                "issues": [],
                "score": 0,
                "_meta": {"error": err},
            },
            "decision": "error",
            "total_latency_ms": elapsed,
            "commit": {
                "sha": sha,
                "message": commit_message,
                "diff_preview": "",
            },
        }

    review = review_diff(diff_text, commit_message, gemini_api_key)
    total_latency_ms = int((time.time() - wall0) * 1000)
    preview = diff_text[:200]

    return {
        "review": review,
        "decision": "ok",
        "total_latency_ms": total_latency_ms,
        "commit": {
            "sha": sha,
            "message": commit_message,
            "diff_preview": preview,
        },
    }
