"""
engine/verifier.py — Run pytest programmatically and return structured results.
"""
import subprocess
import sys
import re
import os
from typing import Optional


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_test_suite(test_target: str = "tests/test_cart.py") -> dict:
    """Run pytest against *test_target* and return a structured result dict.

    The tests are executed in a subprocess so that any import-side-effects
    (e.g. patched in-memory modules) do not bleed into the caller's process.

    Returns:
        {
            "exit_code":  int,          # 0 = all passed, 1 = failures, 2+ = error
            "passed":     int,
            "failed":     int,
            "errors":     int,
            "warnings":   int,
            "total":      int,
            "summary":    str,          # the short summary line from pytest output
            "stdout":     str,          # full captured stdout + stderr
            "test_results": list[dict], # per-test outcome dicts
        }
    """
    cmd = [sys.executable, "-m", "pytest", test_target, "-v", "--tb=short", "--no-header"]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=_find_project_root(),
        )
    except FileNotFoundError:
        return _error_result("pytest / python executable not found on PATH.")
    except subprocess.TimeoutExpired:
        return _error_result("pytest run timed out after 60 seconds.")

    stdout = proc.stdout + proc.stderr
    exit_code = proc.returncode

    passed, failed, errors, warnings, summary = _parse_summary(stdout)
    test_results = _parse_test_results(stdout)

    return {
        "exit_code":    exit_code,
        "passed":       passed,
        "failed":       failed,
        "errors":       errors,
        "warnings":     warnings,
        "total":        passed + failed + errors,
        "summary":      summary,
        "stdout":       stdout,
        "test_results": test_results,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Matches: "2 passed", "1 failed", "1 error", "3 warnings"
_COUNT_RE = re.compile(r'(\d+)\s+(passed|failed|error(?:s)?|warning(?:s)?)')

# Matches individual test outcome lines produced by -v:
#   tests/test_cart.py::test_foo PASSED
#   tests/test_cart.py::test_bar FAILED
_TEST_LINE_RE = re.compile(r'^(?P<node>\S+::[\w\[\-\]]+)\s+(?P<status>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)', re.MULTILINE)


def _parse_summary(output: str) -> tuple[int, int, int, int, str]:
    """Extract pass/fail/error/warning counts and the summary line."""
    passed = failed = errors = warnings = 0
    summary = ""

    for line in reversed(output.splitlines()):
        # pytest summary lines contain "passed", "failed", etc.
        counts = _COUNT_RE.findall(line)
        if counts:
            for count_str, label in counts:
                n = int(count_str)
                if label == "passed":
                    passed = n
                elif label == "failed":
                    failed = n
                elif label in ("error", "errors"):
                    errors = n
                elif label in ("warning", "warnings"):
                    warnings = n
            summary = line.strip()
            break

    return passed, failed, errors, warnings, summary


def _parse_test_results(output: str) -> list[dict]:
    """Extract per-test outcomes from verbose pytest output."""
    results = []
    for m in _TEST_LINE_RE.finditer(output):
        results.append({
            "node":   m.group("node"),
            "status": m.group("status"),
        })
    return results


def _find_project_root() -> str:
    """Walk upward from this file to find the project root (contains requirements.txt)."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = here
    for _ in range(5):
        if os.path.exists(os.path.join(candidate, "requirements.txt")):
            return candidate
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent
    # Fallback: directory containing this file's parent
    return os.path.dirname(here)


def _error_result(msg: str) -> dict:
    return {
        "exit_code":    -1,
        "passed":       0,
        "failed":       0,
        "errors":       1,
        "warnings":     0,
        "total":        0,
        "summary":      msg,
        "stdout":       msg,
        "test_results": [],
    }
