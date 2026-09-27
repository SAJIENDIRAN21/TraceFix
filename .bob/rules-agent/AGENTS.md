# Project Coding Rules (Non-Obvious Only)

- **Never edit `sample_app/` to make tests green** — defects there are the triage input, not bugs to fix directly
- **Patches must be unified diff format** (`--- a/file` / `+++ b/file` headers required) — the verification step uses `patch`/`git apply` semantics
- **Verification applies patches to a temp copy**, not in-place — engine code that mutates `sample_app/` files on disk is wrong
- **`st.cache_data` / `st.cache_resource` required** on any engine call invoked from `app.py` — Streamlit reruns the full script on every widget interaction
- **Inter-column data flows through `st.session_state`** — do not use module-level mutable state in `app.py`
- **Each `engine/` module owns one stage** (parse → patch → verify) — cross-stage logic belongs in a dedicated orchestrator, not scattered across modules
- Run a single test with `pytest tests/test_foo.py::test_bar -v` when iterating — never run the full suite to check one fix
