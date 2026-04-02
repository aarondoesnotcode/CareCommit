# """
# CareCommit guardrail API expected by app.py.

# Run:  uvicorn guardrail_api:app --reload --host 127.0.0.1 --port 8000

# Responses are demo stubs; swap in Gemini / WhiteCircle / internal policy checks as needed.
# """

# from typing import Annotated, List, Optional

# from fastapi import FastAPI, File, Form, UploadFile
# from fastapi.middleware.cors import CORSMiddleware

# app = FastAPI(title="CareCommit Guardrail API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# @app.post("/layer_technical")
# async def layer_technical(
#     review_text: Annotated[str, Form()] = "",
#     code_context: Annotated[str, Form()] = "",
#     language: Annotated[str, Form()] = "",
#     repo_hint: Annotated[str, Form()] = "",
#     supporting_files: Annotated[Optional[List[UploadFile]], File()] = None,
# ):
#     n_files = len(supporting_files) if supporting_files else 0
#     excerpt = review_text[:600] + ("…" if len(review_text) > 600 else "")
#     code_len = len(code_context or "")
#     report = f"""## Technical layer (demo stub)

# **Stack:** {language or "—"} · **Ref:** {repo_hint or "—"} · **Code context:** {code_len} characters · **Files:** {n_files}

# ### Summary
# This endpoint returns placeholder text so the Streamlit UI can run without your real model. Wire `guardrail_api.layer_technical` to your verifier (e.g. Gemini) for the hackathon.

# ### Quick checklist (simulated)
# - Claims in the review are not automatically validated here.
# - Supply real code/diff in the UI so a production layer can compare line-by-line.

# ### Review excerpt
# {excerpt}
# """
#     return {"technical_report": report}


# @app.post("/layer_enterprise")
# async def layer_enterprise(
#     review_text: Annotated[str, Form()] = "",
#     code_context: Annotated[str, Form()] = "",
#     language: Annotated[str, Form()] = "",
#     repo_hint: Annotated[str, Form()] = "",
#     technical_summary: Annotated[str, Form()] = "",
# ):
#     excerpt = (review_text or "")[:400] + ("…" if len(review_text or "") > 400 else "")
#     report = f"""## Enterprise safety layer (demo stub)

# **Simulated policy / WhiteCircle-style gate** — no external call in this file.

# | Gate | Result |
# |------|--------|
# | Secrets / high-entropy strings | Manual review recommended |
# | PII handling language | Not scanned (stub) |
# | Overconfident tone ("definitely safe") | Stub only |

# **Prior technical output length:** {len(technical_summary or "")} characters.

# ### Review excerpt
# {excerpt}
# """
#     return {"enterprise_report": report}
