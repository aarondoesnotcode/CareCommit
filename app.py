from __future__ import annotations

import os
import re

import requests
import streamlit as st


BASE_URL = "http://localhost:8000"
LAYER_TECHNICAL = f"{BASE_URL}/layer_technical"
LAYER_ENTERPRISE = f"{BASE_URL}/layer_enterprise"

GITHUB_API = "https://api.github.com"
MAX_DIFF_CHARS = 450_000

st.set_page_config(page_title="CareCommit", page_icon="🛡️")

if "technical_result" not in st.session_state:
    st.session_state.technical_result = None
if "enterprise_result" not in st.session_state:
    st.session_state.enterprise_result = None
if "technical_payload" not in st.session_state:
    st.session_state.technical_payload = None
if "step" not in st.session_state:
    st.session_state.step = 0
if "review_context" not in st.session_state:
    st.session_state.review_context = {}
if "technical_request_done" not in st.session_state:
    st.session_state.technical_request_done = False
if "enterprise_request_done" not in st.session_state:
    st.session_state.enterprise_request_done = False


def reset_guardrail_flow():
    st.session_state.step = 0
    st.session_state.review_context = {}
    st.session_state.technical_result = None
    st.session_state.enterprise_result = None
    st.session_state.technical_payload = None
    st.session_state.technical_request_done = False
    st.session_state.enterprise_request_done = False


def _secrets_github_token() -> str:
    try:
        return (st.secrets.get("GITHUB_TOKEN") or "").strip()
    except Exception:
        return ""


def parse_github_repo(raw: str) -> tuple[str, str] | None:
    s = (raw or "").strip().rstrip("/")
    if not s:
        return None
    s = re.sub(r"^git@github\.com:", "https://github.com/", s)
    if "github.com/" in s:
        after = s.split("github.com/", 1)[1]
        parts = after.split("/")
        if len(parts) < 2:
            return None
        owner, repo = parts[0], parts[1]
        repo = repo.split("/")[0].split("?")[0]
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo
    if "/" in s and "://" not in s and "@" not in s:
        parts = s.split("/")
        if len(parts) == 2:
            repo = parts[1]
            if repo.endswith(".git"):
                repo = repo[:-4]
            return parts[0], repo
    return None


def github_headers(token: str) -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def fetch_recent_commit_diffs(
    owner: str,
    repo: str,
    n: int,
    token: str,
    branch: str,
) -> tuple[str, list[dict]]:
    headers = github_headers(token)
    params: dict = {"per_page": min(max(n, 1), 100)}
    if (branch or "").strip():
        params["sha"] = branch.strip()

    r = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/commits",
        params=params,
        headers=headers,
        timeout=45,
    )
    r.raise_for_status()
    commits = r.json()
    if not commits:
        raise ValueError("No commits returned for this repo / ref.")

    blocks: list[str] = []
    meta: list[dict] = []
    for c in commits[:n]:
        sha = c["sha"]
        cr = requests.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/commits/{sha}",
            headers=headers,
            timeout=45,
        )
        cr.raise_for_status()
        data = cr.json()
        msg = ((data.get("commit") or {}).get("message") or "").strip()
        msg_one_line = msg.split("\n")[0] if msg else "(no message)"
        patch_parts: list[str] = []
        for f in data.get("files") or []:
            name = f.get("filename") or "unknown"
            patch = f.get("patch")
            if patch:
                patch_parts.append(f"--- {name}\n{patch}")
            else:
                status = f.get("status") or "?"
                patch_parts.append(f"--- {name} ({status}; binary or patch omitted by API)")
        block = f"### {sha[:7]} — {msg_one_line.rstrip()}\n\n" + "\n\n".join(patch_parts)
        blocks.append(block)
        meta.append({"sha": sha, "message": msg_one_line})

    full = "\n\n---\n\n".join(blocks)
    if len(full) > MAX_DIFF_CHARS:
        full = (
            full[:MAX_DIFF_CHARS]
            + f"\n\n… **[truncated at {MAX_DIFF_CHARS} characters for UI / API limits]**"
        )
    return full, meta


if st.session_state.step == 0:
    st.title("CareCommit")
    st.markdown("**Using WhiteCircle & AI to automate your code review** | Hackathon Track:  Review + QA track")
    st.markdown(
        """
        Breakdown:
        1. **Connect GitHub** — point at a repo. We pull recent commits and **raw patch text** from the API.
        2. **Inspect the difference** — review what changed.
        3. **Technical layer** — checks claims against the diff (logic, APIs, edge cases).
        4. **Enterprise safety layer** — using WhiteCircle we are able to check for policy fit (PII, secrets, compliance tone, overconfidence).

        **Disclaimer:** This is to be used as a pre-limininary check before human review, to help speed up the process and catch any potential issues. It does not replace human review or formal QA.
        """
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Start", type="primary"):
            st.session_state.step = 1
            st.rerun()
    with c2:
        if st.button("Reset session"):
            reset_guardrail_flow()
            st.rerun()

elif st.session_state.step == 1:
    st.header("1 · Fetch commits from GitHub")
    with st.sidebar:
        st.subheader("GitHub API")
        default_tok = _secrets_github_token() or os.environ.get("GITHUB_TOKEN", "")
        token_in = st.text_input(
            "Token (optional)",
            value=default_tok,
            type="password",
            help="Fine-grained or classic PAT for private repos / 5k hourly rate limit.",
            key="gh_token_sidebar",
        )

    with st.form("github_fetch"):
        repo_in = st.text_input(
            "Repository",
            placeholder="https://github.com/org/repo or org/repo",
        )
        branch_in = st.text_input("Branch or tag (optional)", placeholder="main")
        n_commits = st.number_input("Recent commits to load", min_value=1, max_value=50, value=5, step=1)
        submitted = st.form_submit_button("Fetch commits")

    if submitted:
        parsed = parse_github_repo(repo_in)
        if not parsed:
            st.error("Could not parse repository. Use `owner/repo` or a full `github.com` URL.")
        else:
            owner, repo = parsed
            token = (token_in or "").strip()
            try:
                diff_text, meta = fetch_recent_commit_diffs(
                    owner, repo, int(n_commits), token, branch_in
                )
            except requests.HTTPError as e:
                detail = ""
                if e.response is not None:
                    try:
                        detail = e.response.json().get("message", e.response.text)
                    except Exception:
                        detail = e.response.text or str(e)
                st.error(f"GitHub API error ({e.response.status_code if e.response else '?'}): {detail}")
            except requests.RequestException as e:
                st.error(f"Network error: {e}")
            except ValueError as e:
                st.error(str(e))
            else:
                st.session_state.review_context = {
                    "github_owner": owner,
                    "github_repo": repo,
                    "repo_hint": f"{owner}/{repo}",
                    "commits_meta": meta,
                    "code_context": diff_text,
                    "review_text": "",
                    "language": "Unspecified",
                    "branch": (branch_in or "").strip(),
                }
                st.session_state.technical_request_done = False
                st.session_state.enterprise_request_done = False
                st.session_state.technical_payload = None
                st.session_state.enterprise_result = None
                st.session_state.step = 2
                st.rerun()

    if st.button("← Back"):
        st.session_state.step = 0
        st.rerun()

elif st.session_state.step == 2:
    st.header("2 · Commit diffs & review input")
    ctx = st.session_state.review_context
    owner, repo = ctx.get("github_owner"), ctx.get("github_repo")
    st.markdown(f"**Repository:** `{owner}/{repo}`" + (f" · **ref:** `{ctx['branch']}`" if ctx.get("branch") else ""))

    st.subheader("Commits")
    for m in ctx.get("commits_meta") or []:
        st.markdown(f"- `{m['sha'][:7]}` — {m.get('message', '')}")

    st.subheader("Raw patches (from GitHub)")
    diff_default = ctx.get("code_context", "")
    with st.expander("Unified diff text", expanded=True):
        st.code(diff_default, language="diff")

    review_text = st.text_area(
        "Optional: paste an **AI-generated review** of these changes to run through the guardrail",
        value=ctx.get("review_text", ""),
        height=160,
        placeholder="Leave empty to send only the diff; your backend can still analyze the patch.",
        key="optional_ai_review",
    )
    code_context_edited = st.text_area(
        "Diff / context sent to guardrail (editable)",
        value=diff_default,
        height=320,
        key="diff_for_guardrail",
    )
    _langs = [
        "Unspecified",
        "Python",
        "TypeScript / JavaScript",
        "Go",
        "Java / Kotlin",
        "C# / .NET",
        "Rust",
        "Other",
    ]
    _prev = ctx.get("language") or "Unspecified"
    language = st.selectbox(
        "Primary language / stack (hint)",
        _langs,
        index=_langs.index(_prev) if _prev in _langs else 0,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Run guardrail layers", type="primary"):
            st.session_state.review_context["review_text"] = review_text.strip()
            st.session_state.review_context["code_context"] = code_context_edited.strip()
            st.session_state.review_context["language"] = language
            st.session_state.step = 3
            st.session_state.technical_request_done = False
            st.rerun()
    with c2:
        if st.button("Re-fetch different repo"):
            st.session_state.step = 1
            st.rerun()

elif st.session_state.step == 3:
    st.header("3 · Technical layer (accuracy check)")
    ctx = st.session_state.review_context

    form_data = {
        "review_text": ctx.get("review_text", ""),
        "code_context": ctx.get("code_context", ""),
        "language": ctx.get("language", ""),
        "repo_hint": ctx.get("repo_hint", ""),
    }

    if not st.session_state.technical_request_done:
        try:
            response = requests.post(LAYER_TECHNICAL, data=form_data, timeout=120)
            st.write("HTTP status:", response.status_code)
            if response.status_code == 200:
                result = response.json()
                st.session_state.technical_result = result
                st.session_state.technical_payload = result.get("technical_report") or result.get(
                    "report"
                ) or str(result)
                st.success("Technical layer completed.")
                if st.session_state.technical_payload:
                    st.subheader("Technical layer output")
                    st.markdown(st.session_state.technical_payload)
            else:
                st.error(f"Technical layer failed: {response.status_code} — {response.text}")
        except requests.RequestException as e:
            st.error(f"Request error: {e}")
            st.info(
                f"Ensure the API is running at `{BASE_URL}` and exposes `POST /layer_technical`."
            )
            st.stop()
        st.session_state.technical_request_done = True

    else:
        if st.session_state.technical_payload:
            st.subheader("Technical layer output")
            st.markdown(st.session_state.technical_payload)

    if st.button("Continue to enterprise safety layer"):
        st.session_state.step = 4
        st.rerun()

elif st.session_state.step == 4:
    st.header("4 · Review technical gate")
    ctx = st.session_state.review_context
    if ctx:
        st.markdown(f"**Repo:** `{ctx.get('repo_hint', '—')}` · **Language hint:** {ctx.get('language', '—')}")
        preview = (ctx.get("review_text") or "").strip()
        if preview:
            st.markdown("**AI review (preview)**")
            st.code(preview[:1200] + ("…" if len(preview) > 1200 else ""), language="markdown")
        else:
            st.caption("No separate AI review text — guardrail used the diff only.")
        dc = ctx.get("code_context") or ""
        st.markdown("**Diff preview (first lines)**")
        st.code(dc[:1500] + ("…" if len(dc) > 1500 else ""), language="diff")
    st.divider()
    if st.button("Run enterprise safety layer", type="primary"):
        st.session_state.step = 5
        st.session_state.enterprise_request_done = False
        st.rerun()
    if st.button("← Back to technical output"):
        st.session_state.step = 3
        st.rerun()

elif st.session_state.step == 5:
    st.header("5 · Enterprise safety layer")
    ctx = st.session_state.review_context
    form_data = {
        "review_text": ctx.get("review_text", ""),
        "code_context": ctx.get("code_context", ""),
        "language": ctx.get("language", ""),
        "repo_hint": ctx.get("repo_hint", ""),
        "technical_summary": st.session_state.technical_payload or "",
    }

    if not st.session_state.enterprise_request_done:
        with st.spinner("Running policy and safety checks on the review…"):
            try:
                response = requests.post(LAYER_ENTERPRISE, data=form_data, timeout=120)
                if response.status_code == 200:
                    res = response.json()
                    st.session_state.enterprise_result = res.get("enterprise_report") or res.get(
                        "report"
                    ) or str(res)
                    st.success("Enterprise layer completed.")
                else:
                    st.error(f"Enterprise layer failed: {response.status_code} — {response.text}")
            except requests.RequestException as e:
                st.error(f"Request error: {e}")
        st.session_state.enterprise_request_done = True

    final_enterprise = st.session_state.get("enterprise_result")
    if final_enterprise:
        st.subheader("Enterprise safety output")
        st.markdown(final_enterprise)

    st.divider()
    st.subheader("CareCommit summary")
    t_ok = bool(st.session_state.technical_payload)
    e_ok = bool(st.session_state.get("enterprise_result"))
    if t_ok and e_ok:
        st.success("Both layers produced output. Ship to developers only after your own policy sign-off.")
    elif t_ok:
        st.warning("Technical layer only — enterprise layer missing or failed.")
    else:
        st.error("Incomplete guardrail run.")

    if st.button("Start new verification"):
        reset_guardrail_flow()
        st.rerun()
