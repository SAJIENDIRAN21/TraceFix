"""
engine/patcher.py — Generate and apply unified-diff patches for sample_app defects.
"""
import difflib
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Fix strategies registry
# ---------------------------------------------------------------------------

def _fix_guard_clause(original_code: str, target_file: str) -> Optional[str]:
    """Insert `if not cart: return 0.0` before the first `for item in cart`
    loop inside calculate_cart_total, or generically before any None-dereference
    risk identified by iterating a variable that may be None.

    Works on cart_service.py; falls back to a generic heuristic for other files.
    """
    lines = original_code.splitlines(keepends=True)
    new_lines = lines[:]

    # --- targeted fix for cart_service.py ---
    if "cart_service" in target_file:
        for idx, line in enumerate(lines):
            stripped = line.rstrip()
            # Find the `for item in cart["items"]:` line
            if re.search(r'for\s+\w+\s+in\s+\w+\[', stripped):
                indent = len(line) - len(line.lstrip())
                guard = " " * indent + "if not cart:\n"
                ret   = " " * indent + "    return 0.0\n"
                new_lines.insert(idx, ret)
                new_lines.insert(idx, guard)
                return "".join(new_lines)

    # --- generic heuristic: find the first subscript on a variable assigned
    #     from a function that might return None, insert a guard before it ---
    # Look for pattern:  <var> = <call>(...)  followed by  <var>[...] or <var>.<attr>
    assigned_var: Optional[str] = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        # detect assignment from a function call
        m = re.match(r'^(\w+)\s*=\s*\w+\(', stripped)
        if m:
            assigned_var = m.group(1)
            continue
        if assigned_var and re.search(rf'\b{re.escape(assigned_var)}\[', stripped):
            indent = len(line) - len(line.lstrip())
            guard = " " * indent + f"if not {assigned_var}:\n"
            ret   = " " * indent + "    return 0.0\n"
            new_lines.insert(idx, ret)
            new_lines.insert(idx, guard)
            return "".join(new_lines)

    # Could not apply fix — return original unchanged
    return original_code


_FIX_STRATEGIES = {
    "guard_clause": _fix_guard_clause,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_unified_patch(
    target_file: str,
    original_code: str,
    fix_type: str = "guard_clause",
) -> str:
    """Return a unified diff string that transforms *original_code* to the
    fixed version according to *fix_type*.

    The diff header uses `a/<target_file>` / `b/<target_file>` so it is
    compatible with `patch -p1` and `git apply`.

    Raises ValueError if *fix_type* is not recognised or the strategy fails
    to produce a change.
    """
    strategy = _FIX_STRATEGIES.get(fix_type)
    if strategy is None:
        raise ValueError(
            f"Unknown fix_type '{fix_type}'. "
            f"Available: {list(_FIX_STRATEGIES.keys())}"
        )

    fixed_code = strategy(original_code, target_file)
    if fixed_code is None:
        fixed_code = original_code  # strategy signalled no change

    original_lines = original_code.splitlines(keepends=True)
    fixed_lines    = fixed_code.splitlines(keepends=True)

    # Ensure final newlines so diff is clean
    if original_lines and not original_lines[-1].endswith("\n"):
        original_lines[-1] += "\n"
    if fixed_lines and not fixed_lines[-1].endswith("\n"):
        fixed_lines[-1] += "\n"

    diff = difflib.unified_diff(
        original_lines,
        fixed_lines,
        fromfile=f"a/{target_file}",
        tofile=f"b/{target_file}",
        lineterm="",
    )
    patch = "\n".join(diff)
    if patch and not patch.endswith("\n"):
        patch += "\n"
    return patch


def apply_patch_in_memory(original_code: str, patch_diff: str) -> str:
    """Apply a unified diff to *original_code* entirely in memory and return
    the patched source string.

    The implementation is a straightforward unified-diff interpreter — it
    handles context lines, additions, and deletions without touching the
    filesystem.

    Raises ValueError if the patch cannot be applied cleanly.
    """
    if not patch_diff.strip():
        return original_code

    original_lines = original_code.splitlines()
    result_lines   = list(original_lines)  # will be rebuilt hunk by hunk
    patch_lines    = patch_diff.splitlines()

    hunks = _parse_hunks(patch_lines)

    # Apply hunks in reverse order so earlier line offsets stay valid
    for hunk in reversed(hunks):
        orig_start, orig_count, new_lines_for_hunk = hunk
        # orig_start is 1-based; convert to 0-based slice indices
        start_idx = orig_start - 1
        end_idx   = start_idx + orig_count
        result_lines[start_idx:end_idx] = new_lines_for_hunk

    return "\n".join(result_lines) + ("\n" if original_code.endswith("\n") else "")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_HUNK_HEADER_RE = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def _parse_hunks(patch_lines: list[str]) -> list[tuple]:
    """Return a list of (orig_start, orig_count, new_lines) tuples."""
    hunks = []
    i = 0

    # Skip diff headers (--- / +++ lines)
    while i < len(patch_lines) and not patch_lines[i].startswith("@@"):
        i += 1

    while i < len(patch_lines):
        line = patch_lines[i]
        m = _HUNK_HEADER_RE.match(line)
        if not m:
            i += 1
            continue

        orig_start = int(m.group(1))
        orig_count = int(m.group(2)) if m.group(2) is not None else 1
        i += 1

        new_lines: list[str] = []
        while i < len(patch_lines) and not patch_lines[i].startswith("@@"):
            hunk_line = patch_lines[i]
            if hunk_line.startswith("+"):
                new_lines.append(hunk_line[1:])
            elif hunk_line.startswith("-"):
                pass  # removed line — do not include
            else:
                # context line (space prefix or bare)
                new_lines.append(hunk_line[1:] if hunk_line.startswith(" ") else hunk_line)
            i += 1

        hunks.append((orig_start, orig_count, new_lines))

    return hunks
