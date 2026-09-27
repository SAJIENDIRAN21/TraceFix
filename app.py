"""
app.py — TraceFix Streamlit UI
3-column triage pipeline: Parse → Patch → Verify
"""
import os
import streamlit as st

from engine.parser import parse_traceback
from engine.patcher import generate_unified_patch, apply_patch_in_memory
from engine.verifier import run_test_suite


def _esc(s: str) -> str:
    """HTML-escape a string for safe inline rendering."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TraceFix",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Preset incident ───────────────────────────────────────────────────────────
_PRESET_TRACE = """\
Traceback (most recent call last):
  File "tests/test_cart.py", line 7, in test_nonexistent_user_cart
    assert calculate_cart_total("user_999") == 0.0
  File "sample_app/cart_service.py", line 6, in calculate_cart_total
    for item in cart["items"]:
TypeError: 'NoneType' object is not subscriptable
"""

_PRESET_FILE = "sample_app/cart_service.py"

# ── Shared CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* soften column borders */
    [data-testid="column"] {
        border-right: 1px solid #e5e7eb;
        padding-right: 1.2rem;
        padding-left: 1.2rem;
    }
    [data-testid="column"]:last-child { border-right: none; }

    /* badge helpers */
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-green  { background:#d1fae5; color:#065f46; }
    .badge-red    { background:#fee2e2; color:#991b1b; }
    .badge-yellow { background:#fef9c3; color:#854d0e; }
    .badge-blue   { background:#dbeafe; color:#1e40af; }
    .badge-gray   { background:#f3f4f6; color:#374151; }

    /* diff coloring inside st.code */
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🔧 TraceFix — Autonomous CI/CD Incident Triage Engine")

# Status badges — derive from session state
_parsed  = bool(st.session_state.get("parsed"))
_patched = bool(st.session_state.get("patch_diff"))
_verified = st.session_state.get("verify_result") is not None

badge_parse   = '<span class="badge badge-green">✔ Parsed</span>'   if _parsed   else '<span class="badge badge-gray">○ Parser</span>'
badge_patch   = '<span class="badge badge-green">✔ Patched</span>'  if _patched  else '<span class="badge badge-gray">○ Patcher</span>'
badge_verify  = '<span class="badge badge-green">✔ Verified</span>' if (_verified and st.session_state.get("verify_result", {}).get("exit_code") == 0) \
               else ('<span class="badge badge-red">✖ Failed</span>' if _verified else '<span class="badge badge-gray">○ Verifier</span>')

st.markdown(
    f'{badge_parse}{badge_patch}{badge_verify}'
    '<span class="badge badge-blue">Python · pytest · Git diff</span>',
    unsafe_allow_html=True,
)
st.divider()

# ── Preset button ─────────────────────────────────────────────────────────────
if st.button("⚡ Load CI/CD Failure Incident (Cart Service NoneType)", type="primary"):
    st.session_state["raw_trace"]    = _PRESET_TRACE
    st.session_state["target_file"]  = _PRESET_FILE
    # Auto-run parse + patch so all three columns are live immediately
    parsed = parse_traceback(_PRESET_TRACE)
    st.session_state["parsed"] = parsed

    target_file = _PRESET_FILE
    try:
        original_code = open(target_file, "r", encoding="utf-8").read()
    except FileNotFoundError:
        original_code = ""
    st.session_state["original_code"] = original_code

    if original_code:
        patch = generate_unified_patch(target_file, original_code, "guard_clause")
        patched_code = apply_patch_in_memory(original_code, patch)
        st.session_state["patch_diff"]    = patch
        st.session_state["patched_code"]  = patched_code
    st.rerun()

st.divider()

# ── 3-Column layout ───────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3, gap="medium")

# ════════════════════════════════════════════════════════════════════════════
# COLUMN 1 — Stack Trace Ingestion & Parser
# ════════════════════════════════════════════════════════════════════════════
with col1:
    st.markdown("### 📥 Stack Trace Ingestion")
    st.caption("Paste a raw Python traceback or use the preset incident above.")

    raw_trace = st.text_area(
        "Raw traceback log",
        value=st.session_state.get("raw_trace", ""),
        height=220,
        placeholder="Traceback (most recent call last):\n  File ...\nTypeError: ...",
        key="raw_trace_input",
        label_visibility="collapsed",
    )

    target_file = st.text_input(
        "Target source file",
        value=st.session_state.get("target_file", "sample_app/cart_service.py"),
        key="target_file_input",
        help="Path to the file the patch will be applied to.",
    )

    parse_clicked = st.button("🔍 Parse Traceback", use_container_width=True)

    if parse_clicked and raw_trace.strip():
        parsed = parse_traceback(raw_trace)
        st.session_state["parsed"]       = parsed
        st.session_state["raw_trace"]    = raw_trace
        st.session_state["target_file"]  = target_file
        try:
            original_code = open(target_file, "r", encoding="utf-8").read()
        except FileNotFoundError:
            original_code = ""
        st.session_state["original_code"] = original_code
        # clear downstream state
        st.session_state.pop("patch_diff",   None)
        st.session_state.pop("patched_code", None)
        st.session_state.pop("verify_result", None)
        st.rerun()

    parsed = st.session_state.get("parsed")
    if parsed:
        st.markdown("---")
        st.markdown("#### 🧬 Parse Results")

        exc_color = "red" if "Error" in parsed["exc_type"] else "orange"
        st.markdown(
            f'**Exception:** <span style="color:{exc_color};font-weight:700">'
            f'{parsed["exc_type"]}</span>',
            unsafe_allow_html=True,
        )
        if parsed["message"]:
            st.markdown(f'**Message:** `{parsed["message"]}`')

        c_a, c_b = st.columns(2)
        with c_a:
            st.metric("Failing Line", parsed["failing_line"] or "—")
        with c_b:
            st.metric("Frames", len(parsed["frames"]))

        if parsed["failing_file"]:
            st.markdown(f'**File:** `{parsed["failing_file"]}`')
        if parsed["failing_func"]:
            st.markdown(f'**Function:** `{parsed["failing_func"]}`')
        if parsed["root_cause_module"]:
            st.markdown(f'**Root Cause Module:** `{parsed["root_cause_module"]}`')
        if parsed["caller_module"]:
            st.markdown(f'**Caller Module:** `{parsed["caller_module"]}`')

        st.markdown("**Call Stack**")
        for i, frame in enumerate(parsed["frames"]):
            marker = "🔴" if i == len(parsed["frames"]) - 1 else "⬜"
            with st.expander(
                f'{marker} Frame {i+1} — `{frame["func"]}` @ line {frame["lineno"]}',
                expanded=(i == len(parsed["frames"]) - 1),
            ):
                st.markdown(f'`{frame["file"]}:{frame["lineno"]}`')
                if frame["source"]:
                    st.code(frame["source"], language="python")

    elif parse_clicked:
        st.warning("Please paste a traceback before parsing.")


# ════════════════════════════════════════════════════════════════════════════
# COLUMN 2 — Diff & Patch Synthesizer
# ════════════════════════════════════════════════════════════════════════════
with col2:
    st.markdown("### 🩹 Diff & Patch Synthesizer")
    st.caption("Generates a unified Git diff and previews the patched source.")

    fix_type = st.selectbox(
        "Fix strategy",
        options=["guard_clause"],
        format_func=lambda x: {"guard_clause": "Guard Clause (None check)"}[x],
        key="fix_type_select",
    )

    patch_clicked = st.button(
        "⚙️ Generate Patch",
        use_container_width=True,
        disabled=not bool(st.session_state.get("parsed")),
    )

    if patch_clicked:
        target_file   = st.session_state.get("target_file", "sample_app/cart_service.py")
        original_code = st.session_state.get("original_code", "")
        if not original_code:
            try:
                original_code = open(target_file, "r", encoding="utf-8").read()
                st.session_state["original_code"] = original_code
            except FileNotFoundError:
                st.error(f"Cannot read `{target_file}` — file not found.")
                original_code = ""
        if original_code:
            patch       = generate_unified_patch(target_file, original_code, fix_type)
            patched_code = apply_patch_in_memory(original_code, patch)
            st.session_state["patch_diff"]   = patch
            st.session_state["patched_code"] = patched_code
            st.session_state.pop("verify_result", None)
            st.rerun()

    patch_diff   = st.session_state.get("patch_diff")
    patched_code = st.session_state.get("patched_code")
    original_code = st.session_state.get("original_code")

    if patch_diff:
        st.markdown("---")
        st.markdown("#### 📄 Unified Diff")

        # Colorise diff lines manually using HTML
        colored_lines = []
        for line in patch_diff.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                colored_lines.append(
                    f'<span style="color:#6b7280;font-weight:600">{_esc(line)}</span>'
                )
            elif line.startswith("@@"):
                colored_lines.append(
                    f'<span style="color:#2563eb;font-weight:600">{_esc(line)}</span>'
                )
            elif line.startswith("+"):
                colored_lines.append(
                    f'<span style="background:#d1fae5;color:#065f46;display:block">{_esc(line)}</span>'
                )
            elif line.startswith("-"):
                colored_lines.append(
                    f'<span style="background:#fee2e2;color:#991b1b;display:block">{_esc(line)}</span>'
                )
            else:
                colored_lines.append(f'<span style="color:#374151">{_esc(line)}</span>')

        diff_html = (
            '<pre style="background:#f8fafc;border:1px solid #e5e7eb;'
            'border-radius:6px;padding:12px;overflow-x:auto;'
            'font-size:0.8rem;line-height:1.5">'
            + "\n".join(colored_lines)
            + "</pre>"
        )
        st.markdown(diff_html, unsafe_allow_html=True)

        st.markdown("#### 🔎 Patched Source Preview")
        st.code(patched_code or "", language="python")

        if original_code:
            st.markdown("#### 📂 Original Source")
            st.code(original_code, language="python")

    elif not st.session_state.get("parsed"):
        st.info("Parse a traceback in Column 1 first.")
    else:
        st.info("Click **Generate Patch** to synthesize the fix.")


# ════════════════════════════════════════════════════════════════════════════
# COLUMN 3 — Live Verification Suite
# ════════════════════════════════════════════════════════════════════════════
with col3:
    st.markdown("### ✅ Live Verification Suite")
    st.caption("Applies the patch in memory and runs pytest live.")

    test_target = st.text_input(
        "Test target",
        value="tests/test_cart.py",
        key="test_target_input",
    )

    verify_clicked = st.button(
        "▶ Run pytest",
        use_container_width=True,
        type="primary",
        disabled=not bool(st.session_state.get("patch_diff")),
    )

    if verify_clicked:
        patched_code = st.session_state.get("patched_code", "")
        target_file  = st.session_state.get("target_file", "sample_app/cart_service.py")

        with st.spinner("Running pytest against patched code…"):
            # Write patched file to a temp location so pytest can import it
            import tempfile, shutil, sys, importlib

            project_root = os.path.dirname(os.path.abspath(__file__))
            abs_target   = os.path.join(project_root, target_file)
            backup_path  = abs_target + ".tracefix_backup"

            try:
                # Backup original
                shutil.copy2(abs_target, backup_path)
                # Write patched version
                with open(abs_target, "w", encoding="utf-8") as fh:
                    fh.write(patched_code)

                result = run_test_suite(test_target)
            finally:
                # Always restore original
                if os.path.exists(backup_path):
                    shutil.copy2(backup_path, abs_target)
                    os.remove(backup_path)

        st.session_state["verify_result"] = result
        st.rerun()

    result = st.session_state.get("verify_result")
    if result:
        st.markdown("---")
        all_passed = result["exit_code"] == 0

        if all_passed:
            st.success(f"🎉 All tests passed — {result['passed']} / {result['total']}")
        else:
            st.error(
                f"❌ {result['failed']} failed, {result['passed']} passed "
                f"({result['total']} total)"
            )

        m1, m2, m3 = st.columns(3)
        m1.metric("Passed",  result["passed"],  delta=None)
        m2.metric("Failed",  result["failed"],  delta=None)
        m3.metric("Exit Code", result["exit_code"])

        st.markdown("#### 🧪 Test Results")
        for tr in result.get("test_results", []):
            icon = {"PASSED": "✅", "FAILED": "❌", "ERROR": "💥", "SKIPPED": "⏭"}.get(
                tr["status"], "❓"
            )
            color = {"PASSED": "#065f46", "FAILED": "#991b1b", "ERROR": "#7c2d12"}.get(
                tr["status"], "#374151"
            )
            st.markdown(
                f'{icon} <span style="color:{color};font-family:monospace">{tr["node"]}</span>'
                f' — <strong style="color:{color}">{tr["status"]}</strong>',
                unsafe_allow_html=True,
            )

        st.markdown("#### 📋 Raw Output")
        st.code(result["stdout"], language="text")

    elif not st.session_state.get("patch_diff"):
        st.info("Generate a patch in Column 2 first.")
    else:
        st.info("Click **▶ Run pytest** to verify the fix live.")


