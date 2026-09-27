"""
engine/parser.py — Parse raw Python tracebacks and validate arbitrary code snippets.
"""
import ast
import re
import time
from typing import Optional

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

# Matches:  File "path/to/file.py", line 42, in some_function
_FRAME_RE = re.compile(
    r'^\s*File "(?P<file>[^"]+)",\s+line\s+(?P<lineno>\d+),\s+in\s+(?P<func>.+)$'
)

# Matches the final exception line: ExcType: message  (or bare ExcType)
_EXC_RE = re.compile(
    r'^(?P<exc_type>[\w.]+(?:Error|Exception|Warning|Interrupt|Exit|Stop|'
    r'Fault|Mismatch|Break|[A-Z]\w*)):\s*(?P<message>.*)$'
)
_BARE_EXC_RE = re.compile(r'^(?P<exc_type>[\w.]+)$')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_traceback(raw_log: str) -> dict:
    """Parse a raw Python traceback string into a structured dict.

    Returns:
        {
            "exc_type":          str,
            "message":           str,
            "frames":            list[dict],
            "failing_file":      str | None,
            "failing_line":      int | None,
            "failing_func":      str | None,
            "root_cause_module": str | None,
            "caller_module":     str | None,
            "source":            str,        # raw input preserved
        }
    """
    t0 = time.monotonic()
    lines = raw_log.splitlines()

    frames: list[dict] = []
    exc_type: Optional[str] = None
    message: Optional[str] = None

    i = 0
    while i < len(lines):
        line = lines[i]

        m = _FRAME_RE.match(line)
        if m:
            frame = {
                "file":   m.group("file"),
                "lineno": int(m.group("lineno")),
                "func":   m.group("func").strip(),
                "source": None,
            }
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if not _FRAME_RE.match(next_line) and not _EXC_RE.match(next_line):
                    frame["source"] = next_line.strip()
                    i += 1
            frames.append(frame)
            i += 1
            continue

        m = _EXC_RE.match(line.strip())
        if m:
            exc_type = m.group("exc_type")
            message  = m.group("message").strip()
            i += 1
            continue

        i += 1

    if exc_type is None:
        for line in reversed(lines):
            line = line.strip()
            if line:
                m = _BARE_EXC_RE.match(line)
                if m:
                    exc_type = m.group("exc_type")
                    message  = ""
                break

    failing_file:      Optional[str] = None
    failing_line:      Optional[int] = None
    failing_func:      Optional[str] = None
    root_cause_module: Optional[str] = None
    caller_module:     Optional[str] = None

    if frames:
        innermost        = frames[-1]
        failing_file     = innermost["file"]
        failing_line     = innermost["lineno"]
        failing_func     = innermost["func"]
        root_cause_module = _module_name(innermost["file"])
        if len(frames) >= 2:
            caller_module = _module_name(frames[-2]["file"])

    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

    return {
        "exc_type":          exc_type or "Unknown",
        "message":           message or "",
        "frames":            frames,
        "failing_file":      failing_file,
        "failing_line":      failing_line,
        "failing_func":      failing_func,
        "root_cause_module": root_cause_module,
        "caller_module":     caller_module,
        "source":            raw_log,
        "elapsed_ms":        elapsed_ms,
    }


def validate_and_parse_code(code: str, filename: str = "<snippet>") -> dict:
    """Attempt to compile *code* via AST and infer any static defects.

    Returns a parse-result dict compatible with the shape returned by
    parse_traceback(), so the rest of the pipeline can treat both paths
    uniformly.

    Extra keys:
        "syntax_valid":  bool
        "syntax_error":  str | None   (human-readable compile error)
        "ast_issues":    list[str]    (heuristic warnings from AST walk)
        "elapsed_ms":    float
    """
    t0 = time.monotonic()
    syntax_valid = True
    syntax_error: Optional[str] = None
    exc_type = "Unknown"
    message  = ""
    failing_line: Optional[int] = None

    try:
        tree = ast.parse(code, filename=filename)
    except SyntaxError as e:
        syntax_valid = False
        exc_type     = type(e).__name__   # SyntaxError or IndentationError
        message      = str(e.msg) if hasattr(e, "msg") else str(e)
        failing_line = e.lineno
        syntax_error = f"{exc_type} at line {e.lineno}: {message}"
        tree         = None

    ast_issues: list[str] = []
    inferred_exc = exc_type

    if tree is not None:
        ast_issues, inferred_exc = _scan_ast(tree)
        if inferred_exc != "Unknown":
            exc_type = inferred_exc

    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

    return {
        "exc_type":          exc_type,
        "message":           message or (ast_issues[0] if ast_issues else ""),
        "frames":            [],
        "failing_file":      filename,
        "failing_line":      failing_line,
        "failing_func":      None,
        "root_cause_module": None,
        "caller_module":     None,
        "source":            code,
        "syntax_valid":      syntax_valid,
        "syntax_error":      syntax_error,
        "ast_issues":        ast_issues,
        "elapsed_ms":        elapsed_ms,
    }


def infer_fix_type(parsed: dict) -> str:
    """Return the recommended patcher fix_type string for a parsed result."""
    exc = parsed.get("exc_type", "")
    mapping = {
        "TypeError":         "guard_clause",
        "KeyError":          "key_error",
        "ZeroDivisionError": "zero_division",
        "IndexError":        "index_guard",
        "SyntaxError":       "syntax_fix",
        "IndentationError":  "syntax_fix",
    }
    return mapping.get(exc, "generic_try_except")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scan_ast(tree: ast.AST) -> tuple[list[str], str]:
    """Walk the AST and emit heuristic warnings for common runtime errors.

    Returns (issues, inferred_exc_type).
    """
    issues: list[str] = []
    inferred = "Unknown"

    for node in ast.walk(tree):
        # Division → potential ZeroDivisionError
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv)):
            right = node.right
            if isinstance(right, ast.Name):
                issues.append(
                    f"Potential ZeroDivisionError: dividing by `{right.id}` "
                    f"(line {getattr(node, 'lineno', '?')}) — no zero-guard found."
                )
                inferred = "ZeroDivisionError"

        # Subscript on Name → potential KeyError / IndexError / TypeError
        if isinstance(node, ast.Subscript):
            val = node.value
            if isinstance(val, ast.Name):
                issues.append(
                    f"Potential KeyError/IndexError/TypeError: subscript on `{val.id}` "
                    f"(line {getattr(node, 'lineno', '?')}) without bounds/key check."
                )
                if inferred == "Unknown":
                    inferred = "KeyError"

    return issues, inferred


def _module_name(filepath: str) -> str:
    path = filepath.replace("\\", "/")
    if path.endswith(".py"):
        path = path[:-3]
    if path.startswith("./"):
        path = path[2:]
    return path.replace("/", ".")
