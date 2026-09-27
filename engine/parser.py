"""
engine/parser.py — Parse raw Python tracebacks into structured data.
"""
import re
from typing import Optional

# Matches lines like:   File "path/to/file.py", line 42, in some_function
_FRAME_RE = re.compile(
    r'^\s*File "(?P<file>[^"]+)",\s+line\s+(?P<lineno>\d+),\s+in\s+(?P<func>.+)$'
)

# Matches the final exception line: ExcType: message  (or bare ExcType)
_EXC_RE = re.compile(r'^(?P<exc_type>[\w.]+(?:Error|Exception|Warning|Interrupt|Exit|Stop|Fault|Mismatch|Break|[A-Z]\w*)):\s*(?P<message>.*)$')
_BARE_EXC_RE = re.compile(r'^(?P<exc_type>[\w.]+)$')


def parse_traceback(raw_log: str) -> dict:
    """Parse a raw Python traceback string into a structured dict.

    Returns:
        {
            "exc_type":      str,          # e.g. "TypeError"
            "message":       str,          # e.g. "'NoneType' object is not subscriptable"
            "frames":        list[dict],   # ordered list of stack frames (outermost first)
            "failing_file":  str | None,   # file of the innermost (crashing) frame
            "failing_line":  int | None,   # line number of the innermost frame
            "failing_func":  str | None,   # function name of the innermost frame
            "root_cause_module": str|None, # the module that directly raised the error
            "caller_module":     str|None, # the module one level up the call stack
        }
    """
    lines = raw_log.splitlines()

    frames: list[dict] = []
    exc_type: Optional[str] = None
    message: Optional[str] = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Try to parse a frame header
        m = _FRAME_RE.match(line)
        if m:
            frame = {
                "file": m.group("file"),
                "lineno": int(m.group("lineno")),
                "func": m.group("func").strip(),
                "source": None,
            }
            # The next line (if not another frame / exception) is the source snippet
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if not _FRAME_RE.match(next_line) and not _EXC_RE.match(next_line):
                    frame["source"] = next_line.strip()
                    i += 1  # consume the source line
            frames.append(frame)
            i += 1
            continue

        # Try to parse the exception line
        m = _EXC_RE.match(line.strip())
        if m:
            exc_type = m.group("exc_type")
            message = m.group("message").strip()
            i += 1
            continue

        # Handle chained exceptions / context lines — skip
        i += 1

    # If we never matched a structured exc line, try a bare word on the last non-empty line
    if exc_type is None:
        for line in reversed(lines):
            line = line.strip()
            if line:
                m = _BARE_EXC_RE.match(line)
                if m:
                    exc_type = m.group("exc_type")
                    message = ""
                break

    # Innermost frame = root cause
    failing_file: Optional[str] = None
    failing_line: Optional[int] = None
    failing_func: Optional[str] = None
    root_cause_module: Optional[str] = None
    caller_module: Optional[str] = None

    if frames:
        innermost = frames[-1]
        failing_file = innermost["file"]
        failing_line = innermost["lineno"]
        failing_func = innermost["func"]
        root_cause_module = _module_name(innermost["file"])

        if len(frames) >= 2:
            caller_module = _module_name(frames[-2]["file"])

    return {
        "exc_type": exc_type or "Unknown",
        "message": message or "",
        "frames": frames,
        "failing_file": failing_file,
        "failing_line": failing_line,
        "failing_func": failing_func,
        "root_cause_module": root_cause_module,
        "caller_module": caller_module,
    }


def _module_name(filepath: str) -> str:
    """Convert a file path to a dot-separated module name, best-effort."""
    # Normalise separators and strip extension
    path = filepath.replace("\\", "/")
    if path.endswith(".py"):
        path = path[:-3]
    # Drop leading ./
    if path.startswith("./"):
        path = path[2:]
    return path.replace("/", ".")
