"""
engine/patcher.py — Generate and apply unified-diff patches for Python defects.
Supports: TypeError/NoneType, KeyError, ZeroDivisionError, IndexError,
          SyntaxError/IndentationError, and a generic try/except fallback.
"""
import difflib
import re
import textwrap
from typing import Optional


# ---------------------------------------------------------------------------
# Fix strategies
# ---------------------------------------------------------------------------

def _fix_guard_clause(original_code: str, target_file: str) -> str:
    """Guard against NoneType subscript (TypeError).

    Targeted: cart_service.py — inserts `if not cart: return 0.0` before
    the for-loop that iterates cart["items"].
    Generic: finds a call-result variable that is immediately subscripted
    and inserts a None-guard before the subscript line.
    """
    lines = original_code.splitlines(keepends=True)
    new_lines = lines[:]

    if "cart_service" in target_file:
        for idx, line in enumerate(lines):
            if re.search(r'for\s+\w+\s+in\s+\w+\[', line.rstrip()):
                indent = len(line) - len(line.lstrip())
                new_lines.insert(idx, " " * indent + "    return 0.0\n")
                new_lines.insert(idx, " " * indent + "if not cart:\n")
                return "".join(new_lines)

    assigned_var: Optional[str] = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        m = re.match(r'^(\w+)\s*=\s*\w+\(', stripped)
        if m:
            assigned_var = m.group(1)
            continue
        if assigned_var and re.search(rf'\b{re.escape(assigned_var)}\[', stripped):
            indent = len(line) - len(line.lstrip())
            new_lines.insert(idx, " " * indent + f"    return 0.0\n")
            new_lines.insert(idx, " " * indent + f"if not {assigned_var}:\n")
            return "".join(new_lines)

    return original_code


def _fix_key_error(original_code: str, target_file: str) -> str:
    """Replace bare dict[key] with dict.get(key, default) (KeyError)."""
    lines = original_code.splitlines(keepends=True)
    new_lines = lines[:]

    if "pricing_service" in target_file:
        for idx, line in enumerate(lines):
            if "pricing_dict['discount_rate']" in line or 'pricing_dict["discount_rate"]' in line:
                fixed = re.sub(
                    r"pricing_dict\[(['\"])discount_rate\1\]",
                    r"pricing_dict.get('discount_rate', 0.0)",
                    line,
                )
                new_lines[idx] = fixed
                return "".join(new_lines)

    # Generic: rewrite the first string-key subscript on any line
    for idx, line in enumerate(lines):
        m = re.search(r'(\w+)\[([\'"])(\w+)\2\]', line)
        if m:
            var, quote, key = m.group(1), m.group(2), m.group(3)
            new_lines[idx] = line.replace(
                f"{var}[{quote}{key}{quote}]",
                f"{var}.get('{key}', 0.0)",
            )
            return "".join(new_lines)

    return original_code


def _fix_zero_division(original_code: str, target_file: str) -> str:
    """Insert zero-denominator guard before a division (ZeroDivisionError)."""
    lines = original_code.splitlines(keepends=True)
    new_lines = lines[:]

    if "analytics_service" in target_file:
        for idx, line in enumerate(lines):
            if re.search(r'\btotal_revenue\s*/\s*order_count\b', line):
                indent = len(line) - len(line.lstrip())
                new_lines.insert(idx, " " * indent + "    return 0.0\n")
                new_lines.insert(idx, " " * indent + "if order_count == 0:\n")
                return "".join(new_lines)

    for idx, line in enumerate(lines):
        m = re.search(r'(\w+)\s*/\s*(\w+)', line)
        if m:
            denominator = m.group(2)
            indent = len(line) - len(line.lstrip())
            new_lines.insert(idx, " " * indent + "    return 0.0\n")
            new_lines.insert(idx, " " * indent + f"if {denominator} == 0:\n")
            return "".join(new_lines)

    return original_code


def _fix_index_guard(original_code: str, target_file: str) -> str:
    """Insert boundary check before an unsafe list index (IndexError).

    Transforms:  value = arr[idx]
    Into:
        if idx < len(arr):
            value = arr[idx]
        else:
            value = None
    """
    lines = original_code.splitlines(keepends=True)
    new_lines = lines[:]

    for idx, line in enumerate(lines):
        # Find  <var> = <arr>[<idx_var>]  patterns
        m = re.search(r'(\w+)\s*=\s*(\w+)\[(\w+)\]', line.strip())
        if m:
            val_var, arr_var, idx_var = m.group(1), m.group(2), m.group(3)
            indent = len(line) - len(line.lstrip())
            pad = " " * indent
            guard_block = (
                f"{pad}if {idx_var} < len({arr_var}):\n"
                f"{pad}    {val_var} = {arr_var}[{idx_var}]\n"
                f"{pad}else:\n"
                f"{pad}    {val_var} = None\n"
            )
            new_lines[idx] = guard_block
            return "".join(new_lines)

    return original_code


def _fix_syntax(original_code: str, target_file: str) -> str:
    """Best-effort correction of common SyntaxError / IndentationError patterns.

    Handles:
    - Missing colon at end of def/class/if/for/while/with/else/elif/try/except/finally
    - Mismatched quotes (unterminated string on a single line)
    - Trailing commas inside function signatures that break older parsers
    """
    lines = original_code.splitlines(keepends=True)
    new_lines = []

    # Keywords that must end their header line with ':'
    _KW_RE = re.compile(
        r'^\s*(def |class |if |elif |else|for |while |with |try:|'
        r'except|except |finally:?)'
    )

    for line in lines:
        stripped = line.rstrip("\n\r")
        # Fix missing colon
        if _KW_RE.match(stripped):
            if stripped.rstrip() and not stripped.rstrip().endswith(":"):
                stripped = stripped.rstrip() + ":"
        # Fix unterminated single-line string (odd number of unescaped quotes)
        for q in ('"', "'"):
            count = stripped.count(q) - stripped.count("\\" + q)
            if count % 2 != 0:
                stripped = stripped + q
                break
        new_lines.append(stripped + "\n" if line.endswith("\n") else stripped)

    return "".join(new_lines)


def _fix_generic_try_except(original_code: str, target_file: str) -> str:
    """Wrap the body of the first function definition in a try/except block
    that returns a safe default instead of propagating an unknown exception.
    """
    lines = original_code.splitlines(keepends=True)
    new_lines = lines[:]

    func_idx: Optional[int] = None
    body_indent: Optional[int] = None

    for idx, line in enumerate(lines):
        if re.match(r'^\s*def\s+\w+', line):
            func_idx = idx
            continue
        if func_idx is not None and body_indent is None:
            stripped = line.lstrip()
            if stripped and not stripped.startswith("#"):
                body_indent = len(line) - len(line.lstrip())
                break

    if func_idx is None or body_indent is None:
        return original_code

    # Find the extent of the function body
    body_start = func_idx + 1
    body_end   = len(lines)
    for idx in range(body_start, len(lines)):
        stripped = lines[idx].lstrip()
        if stripped and not stripped.startswith("#"):
            curr_indent = len(lines[idx]) - len(stripped)
            if curr_indent < body_indent:
                body_end = idx
                break

    pad     = " " * body_indent
    try_line    = f"{pad}try:\n"
    except_line = f"{pad}except Exception:\n"
    return_line = f"{pad}    return None  # auto-patched: swallowed unknown exception\n"

    body_lines = new_lines[body_start:body_end]
    indented   = [f"    {l}" if l.strip() else l for l in body_lines]

    new_lines[body_start:body_end] = [try_line] + indented + [except_line, return_line]
    return "".join(new_lines)


# ---------------------------------------------------------------------------
# Registry and public constants
# ---------------------------------------------------------------------------

_FIX_STRATEGIES: dict = {
    "guard_clause":       _fix_guard_clause,
    "key_error":          _fix_key_error,
    "zero_division":      _fix_zero_division,
    "index_guard":        _fix_index_guard,
    "syntax_fix":         _fix_syntax,
    "generic_try_except": _fix_generic_try_except,
}

EXC_TO_FIX: dict[str, str] = {
    "TypeError":          "guard_clause",
    "KeyError":           "key_error",
    "ZeroDivisionError":  "zero_division",
    "IndexError":         "index_guard",
    "SyntaxError":        "syntax_fix",
    "IndentationError":   "syntax_fix",
}

FIX_LABELS: dict[str, str] = {
    "guard_clause":       "Guard Clause — None check before subscript",
    "key_error":          "Safe .get() — KeyError defence",
    "zero_division":      "Zero Guard — ZeroDivisionError defence",
    "index_guard":        "Boundary Check — IndexError defence",
    "syntax_fix":         "Syntax Repair — colon / quote correction",
    "generic_try_except": "try/except Wrapper — generic exception containment",
}

FIX_SAFETY: dict[str, dict] = {
    "guard_clause":       {"label": "Low Risk — Defensive Guard Clause",   "color": "#065f46", "bg": "#d1fae5"},
    "key_error":          {"label": "Low Risk — Safe Default via .get()",   "color": "#1e40af", "bg": "#dbeafe"},
    "zero_division":      {"label": "Low Risk — Zero-Guard Before Division","color": "#854d0e", "bg": "#fef9c3"},
    "index_guard":        {"label": "Low Risk — Bounds Check on Index",     "color": "#5b21b6", "bg": "#ede9fe"},
    "syntax_fix":         {"label": "Medium Risk — Syntactic Correction",   "color": "#92400e", "bg": "#fef3c7"},
    "generic_try_except": {"label": "Medium Risk — Broad Exception Catch",  "color": "#374151", "bg": "#f3f4f6"},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_unified_patch(
    target_file: str,
    original_code: str,
    fix_type: str = "guard_clause",
) -> str:
    """Return a unified diff compatible with `patch -p1` / `git apply`."""
    strategy = _FIX_STRATEGIES.get(fix_type)
    if strategy is None:
        raise ValueError(
            f"Unknown fix_type '{fix_type}'. Available: {list(_FIX_STRATEGIES)}"
        )

    fixed_code = strategy(original_code, target_file)
    if fixed_code is None:
        fixed_code = original_code

    orig_lines  = original_code.splitlines(keepends=True)
    fixed_lines = fixed_code.splitlines(keepends=True)

    if orig_lines  and not orig_lines[-1].endswith("\n"):
        orig_lines[-1]  += "\n"
    if fixed_lines and not fixed_lines[-1].endswith("\n"):
        fixed_lines[-1] += "\n"

    diff  = difflib.unified_diff(
        orig_lines, fixed_lines,
        fromfile=f"a/{target_file}", tofile=f"b/{target_file}",
        lineterm="",
    )
    patch = "\n".join(diff)
    if patch and not patch.endswith("\n"):
        patch += "\n"
    return patch


def apply_patch_in_memory(original_code: str, patch_diff: str) -> str:
    """Apply a unified diff entirely in memory and return the patched source."""
    if not patch_diff.strip():
        return original_code

    result_lines = original_code.splitlines()
    hunks        = _parse_hunks(patch_diff.splitlines())

    for hunk in reversed(hunks):
        orig_start, orig_count, new_hunk_lines = hunk
        start_idx = orig_start - 1
        result_lines[start_idx : start_idx + orig_count] = new_hunk_lines

    return "\n".join(result_lines) + ("\n" if original_code.endswith("\n") else "")


def get_fixed_code(original_code: str, target_file: str, fix_type: str) -> str:
    """Convenience: return the fixed source without going through the diff round-trip."""
    strategy = _FIX_STRATEGIES.get(fix_type)
    if strategy is None:
        return original_code
    result = strategy(original_code, target_file)
    return result if result is not None else original_code


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_HUNK_HEADER_RE = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def _parse_hunks(patch_lines: list[str]) -> list[tuple]:
    hunks, i = [], 0
    while i < len(patch_lines) and not patch_lines[i].startswith("@@"):
        i += 1
    while i < len(patch_lines):
        m = _HUNK_HEADER_RE.match(patch_lines[i])
        if not m:
            i += 1
            continue
        orig_start = int(m.group(1))
        orig_count = int(m.group(2)) if m.group(2) is not None else 1
        i += 1
        new_lines: list[str] = []
        while i < len(patch_lines) and not patch_lines[i].startswith("@@"):
            hl = patch_lines[i]
            if   hl.startswith("+"):  new_lines.append(hl[1:])
            elif hl.startswith("-"):  pass
            else:                     new_lines.append(hl[1:] if hl.startswith(" ") else hl)
            i += 1
        hunks.append((orig_start, orig_count, new_lines))
    return hunks
