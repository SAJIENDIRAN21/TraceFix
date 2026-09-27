# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project Overview

**TraceFix** — autonomous CI/CD incident triage tool. Parses raw Python stack traces, identifies multi-file upstream defects in `sample_app/`, synthesizes unified Git diff patches, and verifies fixes live with pytest. Exposed via a 3-column Streamlit UI.

## Stack

- Python 3, Streamlit
- pytest for test verification
- pip / `requirements.txt` for dependencies

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run app.py

# Run all tests
pytest

# Run a single test file
pytest tests/test_<name>.py

# Run a single test by name
pytest tests/test_<name>.py::test_function_name -v
```

## Directory Layout

```
engine/         # Core triage logic: trace parsing, patch synthesis, fix verification
sample_app/     # Intentionally buggy multi-file app used as triage target
tests/          # pytest test suite
screenshots/    # UI screenshots / assets
app.py          # Streamlit entry point (3-column layout)
requirements.txt
```

## Architecture Flow

1. **Parse** — `engine/` ingests a raw stack trace and identifies affected files in `sample_app/`
2. **Synthesize** — generates a unified Git diff patch targeting the upstream defect(s)
3. **Verify** — applies patch and runs pytest live; surfaces pass/fail in the UI

## Code Style & Conventions

- **Modules are self-contained per responsibility** — each engine module does one job (parse, patch, verify); do not merge concerns
- **`sample_app/` is the triage target, not production code** — bugs there are intentional; do not fix them unless a test explicitly requires it
- **Patches must be valid unified diff format** (`--- a/...` / `+++ b/...`) so they can be applied with `patch` or `git apply`
- **pytest verification runs against `sample_app/`**, not the engine itself — keep `tests/` scoped accordingly
- **Streamlit state** — use `st.session_state` for inter-column data flow; avoid module-level mutable globals in `app.py`
- **No external AI/LLM calls assumed** — patch synthesis logic lives entirely in `engine/`; do not add network calls without updating `requirements.txt`

## Critical Gotchas

- `sample_app/` bugs are **intentional** — touching them to make tests pass defeats the purpose; the engine should fix them programmatically
- Patches are applied **in-memory or to a temp copy** during verification; never destructively mutate `sample_app/` source files at rest
- Single test runs (`pytest tests/test_foo.py::test_bar`) are the primary debugging loop — always scope to one test when iterating on engine logic
- Streamlit reruns the entire script on each interaction — any expensive engine operation must be guarded with `st.cache_data` or `st.cache_resource`
