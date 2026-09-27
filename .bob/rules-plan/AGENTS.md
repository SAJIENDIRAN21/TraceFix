# Project Architecture Rules (Non-Obvious Only)

- **Pipeline is strictly linear and stateless between stages**: parse → patch → verify; earlier stages must not be re-run implicitly when a later stage is retried
- **`sample_app/` is multi-file by design** — the patch synthesis stage must handle cross-file diffs in a single unified patch, not one patch per file
- **Verification is live pytest, not static analysis** — architecture decisions that replace live test execution with heuristics break the core value proposition
- **No LLM/network dependency assumed in the engine** — if AI-assisted patch generation is added, it must be an optional engine module, not a hard dependency
- **Streamlit is the only UI layer** — there is no REST API; if headless/CI usage is needed, the engine modules must be callable independently of `app.py`
- **`requirements.txt` is the sole dependency contract** — no `setup.py`, `pyproject.toml`, or virtual-env tooling assumed; keep it flat
