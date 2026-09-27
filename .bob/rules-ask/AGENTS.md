# Project Documentation Rules (Non-Obvious Only)

- **`sample_app/` is NOT the application being developed** — it is an intentionally broken fixture that TraceFix triages; treat it as test data, not source
- **`engine/` is the canonical reference** — no separate docs exist; read the module code directly for authoritative behavior
- **The 3-column Streamlit UI maps 1-to-1 to the pipeline stages**: column 1 = trace input, column 2 = synthesized patch, column 3 = live pytest results
- **`tests/` validates the engine's output against `sample_app/`**, not the engine internals — test failures mean the triage pipeline produced a wrong or invalid patch
- **`screenshots/`** contains UI reference images only; not auto-generated, not part of any test
