# CareCommit

CareCommit is a hackathon app that takes a public GitHub repository, lists recent commits, and runs an **AI code review** on a chosen commit’s diff (Google **Gemini**). All business logic lives in [`backend.py`](backend.py); [`app.py`](app.py) is Streamlit only.

**Setup**

1. Clone the repo, create a virtual environment, and run `pip install -r requirements.txt`.
2. Copy [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example) to `.streamlit/secrets.toml`. Set **`GEMINI_API_KEY`** (required; from [Google AI Studio](https://aistudio.google.com/apikey)). Optionally set **`GITHUB_TOKEN`** for private repos or higher rate limits.
3. From the project root, run `streamlit run app.py`.

Do not commit `.streamlit/secrets.toml`.
