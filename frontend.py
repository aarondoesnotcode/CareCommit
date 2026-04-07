# """Entrypoint shim so `streamlit run frontend.py` works. Prefer `streamlit run app.py` for clearer reload/watch behavior."""

# from importlib.util import module_from_spec, spec_from_file_location
# from pathlib import Path

# _app = Path(__file__).resolve().parent / "app.py"
# _spec = spec_from_file_location("carecommit_app", _app)
# _module = module_from_spec(_spec)
# _spec.loader.exec_module(_module)
