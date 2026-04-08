"""CareCommit Streamlit UI — all logic lives in backend.py."""

from __future__ import annotations

import json
import os

import streamlit as st

from backend import fetch_recent_commits, parse_github_url, run_pipeline

st.set_page_config(page_title="CareCommit", page_icon="🛡️")


st.markdown(
    """
    <style>
      :root {
        --cc-surface: rgba(255, 255, 255, 0.05);
        --cc-surface-strong: rgba(255, 255, 255, 0.08);
        --cc-border: rgba(255, 255, 255, 0.14);
        --cc-text-muted: rgba(250, 250, 250, 0.78);
      }

      .block-container {
        padding-top: 1.75rem !important;
        max-width: 980px;
      }

      [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(1200px 700px at -10% -20%, rgba(59, 130, 246, 0.25), transparent 55%),
          radial-gradient(900px 600px at 110% -10%, rgba(14, 165, 233, 0.18), transparent 52%),
          linear-gradient(180deg, #0b1220 0%, #0a1020 42%, #070c18 100%);
      }

      [data-testid="stAppViewContainer"]::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        opacity: 0.32;
        background:
          radial-gradient(circle at 18% 24%, rgba(96, 165, 250, 0.55) 0 2px, transparent 3px),
          radial-gradient(circle at 39% 16%, rgba(56, 189, 248, 0.45) 0 2px, transparent 3px),
          radial-gradient(circle at 72% 22%, rgba(125, 211, 252, 0.5) 0 2px, transparent 3px),
          radial-gradient(circle at 84% 35%, rgba(59, 130, 246, 0.4) 0 2px, transparent 3px),
          radial-gradient(circle at 29% 71%, rgba(14, 165, 233, 0.45) 0 2px, transparent 3px),
          radial-gradient(circle at 66% 78%, rgba(56, 189, 248, 0.5) 0 2px, transparent 3px),
          linear-gradient(118deg, transparent 22%, rgba(96, 165, 250, 0.22) 23%, transparent 24%),
          linear-gradient(36deg, transparent 44%, rgba(56, 189, 248, 0.18) 45%, transparent 46%),
          linear-gradient(160deg, transparent 66%, rgba(125, 211, 252, 0.14) 67%, transparent 68%);
      }

      [data-testid="stAppViewContainer"]::after {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        opacity: 0.11;
        background-image:
          linear-gradient(rgba(148, 163, 184, 0.35) 1px, transparent 1px),
          linear-gradient(90deg, rgba(148, 163, 184, 0.35) 1px, transparent 1px);
        background-size: 44px 44px;
        mask-image: radial-gradient(circle at 50% 30%, black, transparent 82%);
        -webkit-mask-image: radial-gradient(circle at 50% 30%, black, transparent 82%);
      }

      [data-testid="stHeader"] {
        background: transparent;
      }

      [data-testid="stSidebar"] > div:first-child {
        background: linear-gradient(180deg, rgba(17, 24, 39, 0.92), rgba(10, 15, 28, 0.95));
      }

      .cc-hero {
        border: 1px solid var(--cc-border);
        background: linear-gradient(145deg, #1f2937 0%, #111827 52%, #0f172a 100%);
        border-radius: 18px;
        padding: 1.2rem 1.3rem;
        margin-bottom: 1rem;
      }

      .cc-eyebrow {
        font-size: 0.8rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #93c5fd;
        margin-bottom: 0.35rem;
      }

      .cc-subtle {
        color: var(--cc-text-muted);
        margin-top: 0.35rem;
      }

      .cc-step-title {
        margin-top: 0.15rem;
        margin-bottom: 0.35rem;
      }

      .cc-panel {
        border: 1px solid var(--cc-border);
        background: var(--cc-surface);
        border-radius: 12px;
        padding: 0.85rem 1rem;
        margin: 0.65rem 0 0.9rem;
      }

      .cc-action-wrap {
        border: 1px solid var(--cc-border);
        background: rgba(15, 23, 42, 0.42);
        border-radius: 14px;
        padding: 0.8rem 0.9rem 0.2rem;
        margin-top: 0.25rem;
      }

      .cc-chip {
        display: inline-block;
        border: 1px solid var(--cc-border);
        background: var(--cc-surface-strong);
        border-radius: 999px;
        padding: 0.15rem 0.65rem;
        margin-right: 0.45rem;
        font-size: 0.8rem;
      }

      div[data-testid="stMetric"] {
        border: 1px solid var(--cc-border);
        background: var(--cc-surface);
        border-radius: 12px;
        padding: 0.45rem 0.8rem;
      }

      div[data-testid="stForm"] {
        border: 1px solid var(--cc-border);
        background: rgba(17, 24, 39, 0.35);
        border-radius: 14px;
        padding: 0.9rem 1rem 0.2rem;
      }

      div[data-testid="stRadio"] > label {
        margin-bottom: 0.4rem;
      }

      .cc-help {
        color: var(--cc-text-muted);
        font-size: 0.92rem;
        margin-bottom: 0.45rem;
      }

      div[data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%);
        border: 1px solid rgba(147, 197, 253, 0.45);
        color: #f8fafc;
        box-shadow: 0 8px 24px rgba(14, 165, 233, 0.28);
      }

      div[data-testid="stButton"] button[kind="primary"]:hover {
        border-color: rgba(186, 230, 253, 0.7);
        box-shadow: 0 10px 28px rgba(37, 99, 235, 0.38);
        filter: brightness(1.04);
      }

      div[data-testid="stButton"] button[kind="primary"]:focus {
        outline: 2px solid rgba(125, 211, 252, 0.8);
        outline-offset: 1px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

if "step" not in st.session_state:
    st.session_state.step = 0
if "owner" not in st.session_state:
    st.session_state.owner = ""
if "repo" not in st.session_state:
    st.session_state.repo = ""
if "ref" not in st.session_state:
    st.session_state.ref = ""
if "commits" not in st.session_state:
    st.session_state.commits = []
if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None
if "last_error" not in st.session_state:
    st.session_state.last_error = None


def reset_flow():
    st.session_state.step = 0
    st.session_state.owner = ""
    st.session_state.repo = ""
    st.session_state.ref = ""
    st.session_state.commits = []
    st.session_state.pipeline_result = None
    st.session_state.last_error = None


def _secret(key: str) -> str:
    try:
        return (st.secrets.get(key) or "").strip()
    except Exception:
        return ""


def _secrets_github_token() -> str:
    return _secret("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "").strip()


def _secrets_gemini() -> str:
    return _secret("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "").strip()


if st.session_state.step == 0:
    st.markdown(
        """
        <div class="cc-hero">
          <div class="cc-eyebrow">Ship safer code faster</div>
          <h1 style="margin:0;">CareCommit</h1>
          <p class="cc-subtle">
            AI code review for real GitHub commits. Pick a commit and get a structured
            verdict on bugs, security risks, and quality.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        ### How it works
        1. Paste a public repo URL or `owner/repo`.
        2. Pick a recent commit.
        3. Read an AI review with score, issues, and suggested fixes.
        """
    )
    st.markdown('<div class="cc-action-wrap">', unsafe_allow_html=True)
    st.markdown(
        '<div class="cc-help">Start a new review flow, or clear all current session data.</div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([1.8, 1.2])
    with c1:
        if st.button("Start review", type="primary", use_container_width=True):
            st.session_state.step = 1
            st.rerun()
    with c2:
        if st.button("Reset session", use_container_width=True):
            reset_flow()
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.step == 1:
    st.markdown('<h3 class="cc-step-title">1 · Fetch commits from GitHub</h3>', unsafe_allow_html=True)
    st.progress(0.33, text="Step 1 of 3")
    st.markdown(
        '<div class="cc-panel">Enter a repository and load recent commits for review.</div>',
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.subheader("Credentials")
        default_tok = _secrets_github_token()
        token_in = st.text_input(
            "GitHub token (optional)",
            value=default_tok,
            type="password",
            help="PAT for private repos or 5k req/hr rate limit.",
            key="gh_token_sidebar",
        )

    with st.form("github_fetch"):
        repo_in = st.text_input(
            "Repository",
            placeholder="https://github.com/org/repo or org/repo",
        )
        branch_in = st.text_input("Branch or tag (optional)", placeholder="main")
        n_commits = st.number_input(
            "Recent commits to load", min_value=1, max_value=50, value=5, step=1
        )
        submitted = st.form_submit_button("Fetch commits")

    if submitted:
        st.session_state.last_error = None
        try:
            owner, repo = parse_github_url(repo_in)
        except ValueError as e:
            st.error(str(e))
        else:
            token = (token_in or "").strip()
            try:
                commits = fetch_recent_commits(
                    owner,
                    repo,
                    n=int(n_commits),
                    github_token=token,
                    ref=(branch_in or "").strip(),
                )
            except ConnectionError as e:
                st.error(f"GitHub API error: {e}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")
            else:
                if not commits:
                    st.warning("No commits returned.")
                else:
                    st.session_state.owner = owner
                    st.session_state.repo = repo
                    st.session_state.ref = (branch_in or "").strip()
                    st.session_state.commits = commits
                    st.session_state.pipeline_result = None
                    st.session_state.step = 2
                    st.rerun()

    if st.button("← Back"):
        st.session_state.step = 0
        st.rerun()

elif st.session_state.step == 2:
    st.markdown('<h3 class="cc-step-title">2 · Choose a commit</h3>', unsafe_allow_html=True)
    st.progress(0.66, text="Step 2 of 3")
    owner = st.session_state.owner
    repo = st.session_state.repo
    st.markdown(
        f'<span class="cc-chip">Repository: {owner}/{repo}</span>'
        + (f'<span class="cc-chip">Ref: {st.session_state.ref}</span>' if st.session_state.ref else ""),
        unsafe_allow_html=True,
    )

    commits = st.session_state.commits or []
    if not commits:
        st.error("No commits loaded. Go back and fetch again.")
        if st.button("← Back"):
            st.session_state.step = 1
            st.rerun()
        st.stop()

    labels = []
    for c in commits:
        msg = (c.get("message") or "").strip().split("\n")[0][:80]
        labels.append(f"`{c.get('short_sha', '')}` — {msg}")

    pick = st.radio("Commit", range(len(commits)), format_func=lambda i: labels[i])
    chosen = commits[pick]
    url = chosen.get("url") or ""
    if url:
        st.markdown(f"[Open on GitHub]({url})")

    gemini_key = _secrets_gemini()
    sidebar_tok = st.sidebar.text_input(
        "GitHub token (optional)",
        value=_secrets_github_token(),
        type="password",
        key="gh_step2",
    )

    if not gemini_key:
        st.warning("Set **GEMINI_API_KEY** in `.streamlit/secrets.toml` to run the review.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Run AI review", type="primary", disabled=not gemini_key):
            gh_tok = (sidebar_tok or "").strip()
            sha = chosen.get("sha") or ""
            full_msg = chosen.get("message") or ""
            with st.spinner("Running Gemini review…"):
                st.session_state.pipeline_result = run_pipeline(
                    owner,
                    repo,
                    sha,
                    full_msg,
                    gemini_key,
                    gh_tok,
                )
            st.session_state.step = 3
            st.rerun()
    with c2:
        if st.button("Re-fetch different repo"):
            st.session_state.step = 1
            st.session_state.commits = []
            st.rerun()

    if st.button("← Back to welcome"):
        st.session_state.step = 0
        st.rerun()

elif st.session_state.step == 3:
    st.markdown('<h3 class="cc-step-title">3 · Review and verdict</h3>', unsafe_allow_html=True)
    st.progress(1.0, text="Step 3 of 3")
    result = st.session_state.pipeline_result
    if not result:
        st.warning("No result. Go back and run the pipeline.")
        if st.button("← Back"):
            st.session_state.step = 2
            st.rerun()
        st.stop()

    decision = result.get("decision") or "ok"
    if decision == "error":
        st.error("**Error** — could not complete the pipeline (see review summary).")
    else:
        st.success("**Review complete** — see summary and issues below.")

    review = result.get("review") or {}
    st.subheader("Gemini review")
    st.markdown(
        f'<div class="cc-panel">{review.get("summary") or "—"}</div>',
        unsafe_allow_html=True,
    )
    meta = review.get("_meta") or {}
    if meta.get("latency_ms") is not None:
        st.caption(
            f"Model latency ~{meta.get('latency_ms')} ms · "
            f"tokens in/out: {meta.get('input_tokens', '?')}/{meta.get('output_tokens', '?')}"
        )
    c_score, c_lang = st.columns(2)
    with c_score:
        st.metric("Score (0–100)", review.get("score", "—"))
    with c_lang:
        st.metric("Language", review.get("language_detected") or "—")

    issues = review.get("issues") or []
    if issues:
        with st.expander(f"Issues ({len(issues)})", expanded=True):
            for i, issue in enumerate(issues):
                sev = issue.get("severity", "")
                cat = issue.get("category", "")
                line = issue.get("line")
                st.markdown(f"**{i + 1}.** `{sev}` · `{cat}`" + (f" · line `{line}`" if line is not None else ""))
                st.markdown(issue.get("description") or "")
                st.markdown(f"*Fix:* {issue.get('suggested_fix') or '—'}")

    st.caption(f"Total pipeline time: ~{result.get('total_latency_ms', '?')} ms")

    with st.expander("Raw JSON for judges"):
        out = {
            "decision": result.get("decision"),
            "total_latency_ms": result.get("total_latency_ms"),
            "commit": result.get("commit"),
            "review": review,
        }
        st.code(json.dumps(out, indent=2, default=str), language="json")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Pick another commit"):
            st.session_state.pipeline_result = None
            st.session_state.step = 2
            st.rerun()
    with c2:
        if st.button("Start new verification"):
            reset_flow()
            st.rerun()
