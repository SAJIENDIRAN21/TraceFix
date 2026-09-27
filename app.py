"""
app.py — TraceFix · AI Code Debugger Studio
Dark studio theme matching the UI reference image.
All engine logic, session-state, and test verification preserved.
"""
import ast as _ast
import os
import shutil
import time
import streamlit as st

from engine.parser  import parse_traceback, validate_and_parse_code, infer_fix_type
from engine.patcher import (
    generate_unified_patch, apply_patch_in_memory, get_fixed_code,
    FIX_LABELS, FIX_SAFETY,
)
from engine.verifier import run_test_suite


# ── Utilities ─────────────────────────────────────────────────────────────────
def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── Session-state initialisation ─────────────────────────────────────────────
if "custom_code_input" not in st.session_state:
    st.session_state.custom_code_input = ""


def load_sample():
    st.session_state.custom_code_input = """\
def calculate_discount(price, discount_rate):
    # Potential ZeroDivisionError if rate is 0
    return price / discount_rate
"""


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TraceFix · AI Debugger Studio",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Reset & dark slate base ─────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
    background-color: #0d1117 !important;
    color: #f0f6fc !important;
}
[data-testid="stHeader"] { background: #0d1117 !important; }
[data-testid="stSidebar"] { background: #0d1117 !important; }

/* hide Streamlit branding */
#MainMenu, footer, header { visibility: hidden; }

/* ── Typography ──────────────────────────────────────────────────────────── */
h1,h2,h3,h4,h5,h6 { color: #f0f6fc; }
p,label,div,span   { color: #c9d1d9; }

/* ── Card surface ─────────────────────────────────────────────────────────── */
.tf-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 16px 18px;
    margin-bottom: 14px;
}

/* ── Stepper ribbon ──────────────────────────────────────────────────────── */
.stepper {
    display: flex;
    align-items: center;
    gap: 0;
    margin: 12px 0 18px 0;
    flex-wrap: nowrap;
    overflow-x: auto;
}
.step {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 600;
    white-space: nowrap;
    color: #8b949e;
    background: #21262d;
    border: 1px solid #30363d;
    margin-right: 2px;
}
.step.active {
    background: #1f3a5f;
    color: #388bfd;
    border: 1px solid #388bfd;
}
.step .num {
    width: 22px; height: 22px;
    border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 0.72rem; font-weight: 700;
    background: #30363d; color: #8b949e;
}
.step.active .num { background: #1f6feb; color: #ffffff; }
.step-arrow { color: #30363d; font-size: 1rem; padding: 0 6px; }

/* ── Mode tab / radio buttons ────────────────────────────────────────────── */
.mode-tabs { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
.mode-tab {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 0.76rem;
    color: #8b949e;
    cursor: pointer;
    font-weight: 500;
}
.mode-tab.active { background: #1f3a5f; color: #388bfd; border-color: #388bfd; }

/* Streamlit native radio pills */
[data-testid="stRadio"] label {
    background: #21262d !important;
    border: 1px solid #30363d !important;
    border-radius: 6px !important;
    color: #8b949e !important;
    padding: 4px 10px !important;
}
[data-testid="stRadio"] label[data-selected="true"],
[data-testid="stRadio"] [aria-checked="true"] + label {
    background: #1f3a5f !important;
    border-color: #388bfd !important;
    color: #388bfd !important;
}

/* ── Editor chrome ───────────────────────────────────────────────────────── */
.editor-chrome {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px 10px 0 0;
    padding: 8px 14px;
    display: flex;
    align-items: center;
    gap: 10px;
    border-bottom: none;
}
.editor-tab {
    background: #0d1117;
    border: 1px solid #30363d;
    border-bottom: none;
    border-radius: 5px 5px 0 0;
    padding: 4px 12px;
    font-size: 0.75rem;
    color: #c9d1d9;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.editor-body {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 0 0 10px 10px;
    border-top: none;
    padding: 0 0 4px 0;
}
.editor-body textarea {
    background: #0d1117 !important;
    color: #58a6ff !important;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace !important;
    font-size: 0.82rem !important;
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
}

/* ── Logs terminal ───────────────────────────────────────────────────────── */
.log-chrome {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px 10px 0 0;
    padding: 7px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: none;
}
.log-body {
    background: #090d16;
    border: 1px solid #30363d;
    border-radius: 0 0 10px 10px;
    border-top: 1px solid #30363d;
    padding: 10px 14px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: #8b949e;
    min-height: 90px;
    max-height: 180px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
}
.log-pass { color: #3fb950; }
.log-fail { color: #f85149; }
.log-info { color: #8b949e; }
.log-head { color: #d29922; }

/* ── CTA button ──────────────────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1f6feb 0%, #238636 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    padding: 12px 0 !important;
    letter-spacing: 0.3px;
    box-shadow: 0 4px 16px rgba(31,111,235,0.30);
    transition: opacity 0.15s;
}
.stButton > button[kind="primary"]:hover { opacity: 0.88; }

/* ── KPI metric cards ────────────────────────────────────────────────────── */
.kpi-grid { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.kpi-card {
    flex: 1 1 120px;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 12px 14px;
}
.kpi-icon { font-size: 1.3rem; margin-bottom: 4px; }
.kpi-label { font-size: 0.68rem; color: #8b949e; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
.kpi-value { font-size: 1rem; font-weight: 700; color: #f0f6fc; margin: 2px 0 1px 0; }
.kpi-sub   { font-size: 0.7rem; color: #8b949e; }

/* ── Right panel ─────────────────────────────────────────────────────────── */
.assistant-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
}
.assistant-title { font-size: 1rem; font-weight: 700; color: #f0f6fc; }
.ibm-badge {
    background: #1f3a5f;
    border: 1px solid #388bfd;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 0.7rem;
    color: #388bfd;
    font-weight: 600;
}

/* ── Diagnostic block ────────────────────────────────────────────────────── */
.diag-block {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 12px;
    font-size: 0.85rem;
    line-height: 1.65;
}
.diag-row { margin-bottom: 10px; }
.diag-icon { font-size: 1rem; margin-right: 6px; }
.diag-key { font-weight: 700; color: #f0f6fc; }
.diag-val { color: #8b949e; margin-top: 2px; margin-left: 1.6rem; }
code.inline {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 1px 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: #ff7b72;
}

/* ── Suggested fix chrome ─────────────────────────────────────────────────── */
.fix-chrome {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px 10px 0 0;
    padding: 8px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: none;
}
.fix-body {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 0 0 10px 10px;
    border-top: 1px solid #30363d;
    padding: 10px 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    overflow-x: auto;
}
.diff-add { background: #132c1b; color: #3fb950; display: block; padding: 0 4px; }
.diff-del { background: #3d1a1f; color: #f85149; display: block; padding: 0 4px; }
.diff-ctx { color: #8b949e; display: block; padding: 0 4px; }
.diff-hdr { color: #388bfd; display: block; padding: 0 4px; font-weight: 600; }

/* ── Prompt chips ────────────────────────────────────────────────────────── */
.chip-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0 4px 0; }
.chip {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 20px;
    padding: 4px 13px;
    font-size: 0.73rem;
    color: #8b949e;
    cursor: default;
    white-space: nowrap;
}

/* ── Chat input area ─────────────────────────────────────────────────────── */
.stTextInput input {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    color: #c9d1d9 !important;
    font-size: 0.85rem !important;
}

/* ── Secondary buttons ───────────────────────────────────────────────────── */
.stButton > button:not([kind="primary"]) {
    background: #21262d !important;
    border: 1px solid #30363d !important;
    color: #c9d1d9 !important;
    border-radius: 6px !important;
    font-size: 0.78rem !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: #388bfd !important;
    color: #388bfd !important;
}

/* ── Streamlit text-area ──────────────────────────────────────────────────── */
textarea {
    background: #0d1117 !important;
    color: #58a6ff !important;
    border: 1px solid #30363d !important;
    border-radius: 0 0 10px 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
}

/* ── Selectbox / radio ────────────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stRadio"] label { color: #c9d1d9 !important; }
[data-baseweb="select"] > div {
    background: #21262d !important;
    border-color: #30363d !important;
    color: #c9d1d9 !important;
}

/* ── Divider ─────────────────────────────────────────────────────────────── */
hr { border-color: #30363d !important; }

/* ── st.code ─────────────────────────────────────────────────────────────── */
[data-testid="stCode"] pre, code {
    background: #161b22 !important;
    color: #c9d1d9 !important;
    border: 1px solid #30363d !important;
}

/* ── Expander ────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] { background: #161b22 !important; border-color: #30363d !important; }
[data-testid="stExpander"] summary { color: #8b949e !important; }

/* ── Tabs ────────────────────────────────────────────────────────────────── */
button[data-baseweb="tab"] {
    background: transparent !important;
    color: #8b949e !important;
    font-size: 0.8rem !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #388bfd !important;
    border-bottom-color: #388bfd !important;
}

/* ── Alerts ──────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    background: #161b22 !important;
    border-color: #30363d !important;
    color: #c9d1d9 !important;
}

/* ── Columns divider ─────────────────────────────────────────────────────── */
[data-testid="column"] + [data-testid="column"] {
    border-left: 1px solid #30363d;
    padding-left: 1.4rem;
}
</style>
""", unsafe_allow_html=True)

# ── Data / presets ────────────────────────────────────────────────────────────
INCIDENTS = {
    "Cart Service — NoneType Crash (TypeError)": {
        "trace": """\
Traceback (most recent call last):
  File "tests/test_cart.py", line 7, in test_nonexistent_user_cart
    assert calculate_cart_total("user_999") == 0.0
  File "sample_app/cart_service.py", line 6, in calculate_cart_total
    for item in cart["items"]:
TypeError: 'NoneType' object is not subscriptable""",
        "file":     "sample_app/cart_service.py",
        "fix_type": "guard_clause",
        "test":     "tests/test_cart.py",
        "chat_fix": 'Inserts <code class="inline">if not cart: return 0.0</code> before iterating <code class="inline">cart["items"]</code>.',
    },
    "Pricing Service — Missing Discount Key (KeyError)": {
        "trace": """\
Traceback (most recent call last):
  File "tests/test_pricing.py", line 11, in test_apply_discount_missing_key
    result = apply_discount({"base_amount": 200.0})
  File "sample_app/pricing_service.py", line 2, in apply_discount
    return pricing_dict['discount_rate'] * pricing_dict['base_amount']
KeyError: 'discount_rate'""",
        "file":     "sample_app/pricing_service.py",
        "fix_type": "key_error",
        "test":     "tests/test_pricing.py",
        "chat_fix": "Replaces <code class=\"inline\">pricing_dict['discount_rate']</code> with <code class=\"inline\">pricing_dict.get('discount_rate', 0.0)</code>.",
    },
    "Analytics Service — Zero-Order Aggregation (ZeroDivisionError)": {
        "trace": """\
Traceback (most recent call last):
  File "tests/test_analytics.py", line 11, in test_average_order_zero_count
    result = calculate_average_order(500.0, 0)
  File "sample_app/analytics_service.py", line 2, in calculate_average_order
    return total_revenue / order_count
ZeroDivisionError: float division by zero""",
        "file":     "sample_app/analytics_service.py",
        "fix_type": "zero_division",
        "test":     "tests/test_analytics.py",
        "chat_fix": "Inserts <code class=\"inline\">if order_count == 0: return 0.0</code> before the division.",
    },
}

CHAT_ROOT_CAUSE = {
    "TypeError":
        "The function receives a <code class='inline'>None</code> value and immediately "
        "attempts to subscript or iterate it — Python raises "
        "<code class='inline'>TypeError: 'NoneType' object is not subscriptable</code> "
        "because <code class='inline'>None</code> does not support the <code class='inline'>[]</code> operator.",
    "KeyError":
        "A dictionary is accessed with a bare <code class='inline'>dict[key]</code> subscript "
        "but the key is absent at runtime, so Python raises <code class='inline'>KeyError</code> "
        "instead of returning a default.",
    "ZeroDivisionError":
        "A division <code class='inline'>a / b</code> is executed when "
        "<code class='inline'>b == 0</code>. Python raises <code class='inline'>ZeroDivisionError</code> "
        "because division by zero is mathematically undefined. A zero-guard returns a safe default.",
    "IndexError":
        "A list is accessed at an index that equals or exceeds <code class='inline'>len(seq)</code>, "
        "causing Python to raise <code class='inline'>IndexError</code>. A bounds check prevents the unsafe access.",
    "SyntaxError":
        "Python's compiler cannot parse the source due to a structural violation — "
        "commonly a missing colon, mismatched bracket, or unterminated string literal.",
    "IndentationError":
        "Python encountered inconsistent indentation — typically mixed tabs/spaces "
        "or an unexpected dedent inside a block.",
}

CONFIDENCE = {
    "guard_clause": 98, "key_error": 96, "zero_division": 99,
    "index_guard": 94,  "syntax_fix": 87, "generic_try_except": 80,
}

KPI_ICONS = {
    "guard_clause": "🐛", "key_error": "🔑", "zero_division": "➗",
    "index_guard": "📋",  "syntax_fix": "🔤", "generic_try_except": "⚠️",
}

ROOT_CAUSE_SHORT = {
    "guard_clause": "NoneType subscript",   "key_error": "Missing dict key",
    "zero_division": "Division by zero",     "index_guard": "Out-of-bounds index",
    "syntax_fix": "Syntax violation",        "generic_try_except": "Unknown exception",
}

ROOT_CAUSE_SUB = {
    "guard_clause": "No None-check before use",  "key_error": "Bare dict[ ] subscript",
    "zero_division": "No zero-guard condition",   "index_guard": "No bounds check",
    "syntax_fix": "Malformed statement",          "generic_try_except": "Unhandled path",
}

CONFIDENCE_LABEL = {98: "High", 99: "High", 96: "High", 94: "High", 87: "Medium", 80: "Medium"}


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
_r = st.session_state.get("result")
_step = 0
if st.session_state.get("parsed"):    _step = 1
if st.session_state.get("patch_diff"): _step = 2
if _r is not None:                     _step = 3
if _r and _r.get("exit_code") == 0:    _step = 4

def _step_cls(n): return "step active" if _step >= n else "step"

st.markdown(
    f"""
    <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:4px">
      <div>
        <div style="font-size:1.45rem;font-weight:800;color:#f0f6fc;letter-spacing:-0.3px">
          🔧 TraceFix · AI Debugger Studio
        </div>
        <div style="font-size:0.8rem;color:#8b949e;margin-top:2px">
          Autonomous defect triage · unified diff synthesis · live pytest verification
        </div>
      </div>
      <span style="background:#132c1b;border:1px solid #238636;border-radius:20px;
                   padding:4px 14px;font-size:0.75rem;font-weight:700;color:#3fb950;
                   white-space:nowrap;margin-top:4px">
        ● AI Ready
      </span>
    </div>
    <div class="stepper">
      <div class="{_step_cls(1)}"><span class="num">①</span><span>Analyze<br><small style="font-weight:400;color:inherit;opacity:.7">Detect &amp; Reason</small></span></div>
      <div class="step-arrow">➔</div>
      <div class="{_step_cls(2)}"><span class="num">②</span><span>Patch<br><small style="font-weight:400;color:inherit;opacity:.7">Generate Fix</small></span></div>
      <div class="step-arrow">➔</div>
      <div class="{_step_cls(3)}"><span class="num">③</span><span>Verify<br><small style="font-weight:400;color:inherit;opacity:.7">Run Tests</small></span></div>
      <div class="step-arrow">➔</div>
      <div class="{_step_cls(4)}"><span class="num">④</span><span>Complete<br><small style="font-weight:400;color:inherit;opacity:.7">View Summary</small></span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# COLUMNS  [1.1  |  0.9]
# ─────────────────────────────────────────────────────────────────────────────
left, right = st.columns([1.1, 0.9], gap="medium")

# ══════════════════════════════════════════════════════════════════════════════
# LEFT COLUMN — Code & Incident Studio
# ══════════════════════════════════════════════════════════════════════════════
with left:
    # ── Mode selector row ─────────────────────────────────────────────────
    input_mode = st.radio(
        "Input mode",
        ["📋 Paste Code", "📁 Select Project", "📂 Upload Logs", "💡 Example Cases"],
        horizontal=True,
        key="input_mode",
        label_visibility="collapsed",
    )

    paste_mode   = input_mode == "📋 Paste Code"
    project_mode = input_mode == "📁 Select Project"
    example_mode = input_mode == "💡 Example Cases"

    # ── Mode A: Paste Code ────────────────────────────────────────────────
    if paste_mode or input_mode == "📂 Upload Logs":

        # Editor chrome
        st.markdown(
            '<div class="editor-chrome">'
            '  <div class="editor-tab">🐍 main.py &nbsp;✕</div>'
            '  <div style="margin-left:auto;font-size:0.73rem;color:#8b949e">Python</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Load-sample button sits above the text area so on_click fires before render
        st.button("📋 Load Sample Broken Snippet", on_click=load_sample, use_container_width=False, key="load_btn")

        st.text_area(
            "code_editor",
            key="custom_code_input",
            height=260,
            placeholder="def my_func(): ...",
            label_visibility="collapsed",
        )

        active_file  = "<snippet>"
        active_code  = st.session_state.custom_code_input
        active_test  = None
        active_trace = None
        preset_meta  = None

    # ── Mode B: Select Project ────────────────────────────────────────────
    elif project_mode or example_mode:
        incident_label = st.selectbox(
            "Incident",
            options=list(INCIDENTS.keys()),
            key="incident_select",
            label_visibility="collapsed",
        )
        preset_meta  = INCIDENTS[incident_label]
        active_file  = preset_meta["file"]
        active_trace = preset_meta["trace"]
        active_test  = preset_meta["test"]
        active_code  = ""
        try:
            active_code = open(active_file, "r", encoding="utf-8").read()
        except FileNotFoundError:
            pass

        # Editor chrome with file name
        fname = active_file.split("/")[-1]
        st.markdown(
            f'<div class="editor-chrome">'
            f'  <div class="editor-tab">🐍 {_esc(fname)} &nbsp;✕</div>'
            f'  <div style="margin-left:auto;font-size:0.73rem;color:#8b949e">Python</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.code(active_code or "# file not found", language="python")

    else:
        active_file  = "<snippet>"
        active_code  = st.session_state.custom_code_input
        active_test  = None
        active_trace = None
        preset_meta  = None

    # ── Incident / Runtime Logs container ────────────────────────────────
    _stored_result = st.session_state.get("result")
    _stored_stdout = (_stored_result or {}).get("stdout", "")
    _active_trace_display = active_trace or st.session_state.get("active_trace_display", "")
    if active_trace:
        st.session_state["active_trace_display"] = active_trace

    log_content = ""
    log_classes = ""
    if _stored_stdout:
        # Colorise log lines
        lines = _stored_stdout.splitlines()
        colored = []
        for ln in lines:
            if "PASSED" in ln:
                colored.append(f'<span class="log-pass">{_esc(ln)}</span>')
            elif "FAILED" in ln or "ERROR" in ln or "error" in ln.lower():
                colored.append(f'<span class="log-fail">{_esc(ln)}</span>')
            elif ln.startswith("=") or ln.startswith("-"):
                colored.append(f'<span class="log-head">{_esc(ln)}</span>')
            else:
                colored.append(f'<span class="log-info">{_esc(ln)}</span>')
        log_content = "\n".join(colored)
    elif _active_trace_display:
        lines = _active_trace_display.splitlines()
        colored = []
        for ln in lines:
            if "Error" in ln and ":" in ln:
                colored.append(f'<span class="log-fail">{_esc(ln)}</span>')
            elif ln.strip().startswith("File"):
                colored.append(f'<span class="log-info">{_esc(ln)}</span>')
            else:
                colored.append(f'<span class="log-info">{_esc(ln)}</span>')
        log_content = "\n".join(colored)
    else:
        log_content = '<span class="log-info">No logs yet — run analysis to see pytest output.</span>'

    st.markdown(
        f'<div class="log-chrome">'
        f'  <span style="font-size:0.8rem;font-weight:600;color:#f85149">⊗ Runtime / Error Logs</span>'
        f'  <span style="font-size:0.73rem;color:#8b949e;cursor:pointer">Clear</span>'
        f'</div>'
        f'<div class="log-body">{log_content}</div>',
        unsafe_allow_html=True,
    )

    # ── Primary CTA ───────────────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    analyze_clicked = st.button(
        "▶  Analyze & Auto-Fix Code",
        type="primary",
        use_container_width=True,
        key="analyze_btn",
    )

    if analyze_clicked:
        t_start = time.monotonic()
        if not active_code or not active_code.strip():
            st.warning("Please provide some code before analyzing.")
        else:
            # ── Parse ────────────────────────────────────────────────────
            if active_trace:
                parsed = parse_traceback(active_trace)
            else:
                parsed = validate_and_parse_code(active_code, filename=active_file)

            fix_type = preset_meta["fix_type"] if preset_meta else infer_fix_type(parsed)

            # ── Patch ────────────────────────────────────────────────────
            patch_diff   = generate_unified_patch(active_file, active_code, fix_type)
            patched_code = apply_patch_in_memory(active_code, patch_diff)

            # ── Verify (preset only) ─────────────────────────────────────
            verify_result = None
            if active_test and active_file != "<snippet>":
                project_root = os.path.dirname(os.path.abspath(__file__))
                abs_target   = os.path.join(project_root, active_file)
                backup_path  = abs_target + ".tracefix_backup"
                try:
                    shutil.copy2(abs_target, backup_path)
                    with open(abs_target, "w", encoding="utf-8") as fh:
                        fh.write(patched_code)
                    verify_result = run_test_suite(active_test)
                finally:
                    if os.path.exists(backup_path):
                        shutil.copy2(backup_path, abs_target)
                        os.remove(backup_path)

            elapsed_ms = round((time.monotonic() - t_start) * 1000)

            st.session_state.update({
                "parsed":        parsed,
                "fix_type":      fix_type,
                "active_file":   active_file,
                "active_code":   active_code,
                "patch_diff":    patch_diff,
                "patched_code":  patched_code,
                "result":        verify_result,
                "elapsed_ms":    elapsed_ms,
                "preset_meta":   preset_meta,
            })
            st.rerun()

    # ── KPI metric cards ──────────────────────────────────────────────────
    parsed_s    = st.session_state.get("parsed")
    fix_type_s  = st.session_state.get("fix_type", "generic_try_except")
    exc_s       = (parsed_s or {}).get("exc_type", "—")
    fail_line_s = (parsed_s or {}).get("failing_line")
    conf_s      = CONFIDENCE.get(fix_type_s, 85)
    conf_lbl    = CONFIDENCE_LABEL.get(conf_s, "Medium")
    rc_short    = ROOT_CAUSE_SHORT.get(fix_type_s, "Unknown")
    rc_sub      = ROOT_CAUSE_SUB.get(fix_type_s, "")
    kpi_icon    = KPI_ICONS.get(fix_type_s, "⚠️")

    line_str = f"line {fail_line_s}" if fail_line_s else "—"
    files_str = "1 file" if parsed_s else "—"
    test_str  = "+ 1 test file" if st.session_state.get("result") else ""

    st.markdown(
        f"""
        <div class="kpi-grid">
          <div class="kpi-card">
            <div class="kpi-icon">🐞</div>
            <div class="kpi-label">Issue Detected</div>
            <div class="kpi-value" style="color:#f85149">{_esc(exc_s)}</div>
            <div class="kpi-sub">{line_str}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-icon">🔎</div>
            <div class="kpi-label">Root Cause</div>
            <div class="kpi-value">{_esc(rc_short)}</div>
            <div class="kpi-sub">{_esc(rc_sub)}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-icon">✅</div>
            <div class="kpi-label">Confidence</div>
            <div class="kpi-value" style="color:#3fb950">{conf_s}%</div>
            <div class="kpi-sub">{conf_lbl} · Deterministic AST Guard</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-icon">📁</div>
            <div class="kpi-label">Files Affected</div>
            <div class="kpi-value">{files_str}</div>
            <div class="kpi-sub">{test_str}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# RIGHT COLUMN — TraceFix AI Assistant & Patch Studio
# ══════════════════════════════════════════════════════════════════════════════
with right:
    # ── Panel header ──────────────────────────────────────────────────────
    st.markdown(
        '<div class="assistant-header">'
        '  <div>'
        '    <div class="assistant-title">🤖 TraceFix AI Assistant</div>'
        '    <div style="font-size:0.73rem;color:#8b949e;margin-top:1px">Ask questions, get explanations, or request changes.</div>'
        '  </div>'
        '  <span class="ibm-badge">⚡ Powered by IBM Bob 2.0</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Load results from session state
    parsed       = st.session_state.get("parsed")
    fix_type     = st.session_state.get("fix_type")
    patch_diff   = st.session_state.get("patch_diff")
    patched_code = st.session_state.get("patched_code")
    result       = st.session_state.get("result")
    elapsed_ms   = st.session_state.get("elapsed_ms", 0)
    preset_meta  = st.session_state.get("preset_meta")
    stored_file  = st.session_state.get("active_file", "<snippet>")

    if not parsed:
        # ── Idle chat bubble ──────────────────────────────────────────────
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(
                "**Here's how to get started:**\n\n"
                "1. Choose **📋 Paste Code** and paste any broken Python snippet, "
                "or pick **📁 Select Project** to load a pre-wired incident.\n"
                "2. Hit **▶ Analyze & Auto-Fix Code**.\n"
                "3. I'll detect the bug, generate a defensive patch, and run pytest — all automatically."
            )
        st.stop()

    # ── Resolved values ───────────────────────────────────────────────────
    exc_type   = parsed.get("exc_type", "Unknown")
    message    = parsed.get("message", "")
    fail_line  = parsed.get("failing_line")
    fail_file  = parsed.get("failing_file") or stored_file
    confidence = CONFIDENCE.get(fix_type, 85)
    safety     = FIX_SAFETY.get(fix_type, FIX_SAFETY["generic_try_except"])
    fix_label  = FIX_LABELS.get(fix_type, fix_type)
    root_cause_html = CHAT_ROOT_CAUSE.get(
        exc_type,
        "An unexpected exception was detected. A generic try/except wrapper has been applied."
    )
    chat_fix_html = (
        preset_meta["chat_fix"]
        if preset_meta and "chat_fix" in preset_meta
        else f"Applied <code class='inline'>{_esc(fix_label)}</code>."
    )

    loc_suffix = f" — line <code class='inline'>{fail_line}</code>" if fail_line else ""
    file_suffix = (f" in <code class='inline'>{_esc(fail_file)}</code>" if fail_file and fail_file != "<snippet>" else "")

    # ── Conversational diagnostic card ────────────────────────────────────
    ast_issues  = parsed.get("ast_issues", [])
    extra_warns = ""
    if ast_issues:
        items = "".join(f"<li style='margin:3px 0;color:#8b949e'>{_esc(i)}</li>" for i in ast_issues[:3])
        extra_warns = f"<div style='margin-top:8px'><strong style='color:#d29922'>⚠️ Static warnings:</strong><ul style='margin:4px 0 0 1rem;padding:0'>{items}</ul></div>"

    st.markdown(
        f"""
        <div class="diag-block">
          <div style="font-size:0.78rem;color:#8b949e;margin-bottom:10px">Here's the analysis and fix:</div>
          <div class="diag-row">
            <span class="diag-icon">🔍</span><span class="diag-key">What happened?</span>
            <div class="diag-val">
              A <code class="inline">{_esc(exc_type)}</code> was raised{file_suffix}{loc_suffix}.
              {(' — ' + _esc(message)) if message else ''}
            </div>
          </div>
          <div class="diag-row">
            <span class="diag-icon">💡</span><span class="diag-key">Why it happened?</span>
            <div class="diag-val">{root_cause_html}</div>
          </div>
          <div class="diag-row" style="margin-bottom:0">
            <span class="diag-icon">🛠️</span><span class="diag-key">How I fixed it:</span>
            <div class="diag-val">{chat_fix_html}</div>
          </div>
          {extra_warns}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Confidence / safety / time badges ─────────────────────────────────
    conf_bg    = "#132c1b" if confidence >= 95 else "#2d1f0f"
    conf_color = "#3fb950" if confidence >= 95 else "#d29922"
    st.markdown(
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">'
        f'<span style="background:{conf_bg};color:{conf_color};border:1px solid {conf_color}40;'
        f'border-radius:12px;padding:3px 11px;font-size:0.73rem;font-weight:700">'
        f'🎯 {confidence}% Confidence</span>'
        f'<span style="background:#21262d;color:{safety["color"]};border:1px solid #30363d;'
        f'border-radius:12px;padding:3px 11px;font-size:0.73rem;font-weight:700">'
        f'🛡 {_esc(safety["label"])}</span>'
        f'<span style="background:#21262d;color:#8b949e;border:1px solid #30363d;'
        f'border-radius:12px;padding:3px 11px;font-size:0.73rem;font-weight:700">'
        f'⏱ {elapsed_ms} ms</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Suggested Fix + tabs ──────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.88rem;font-weight:700;color:#f0f6fc;margin-bottom:6px">'
        '🔧 Suggested Fix</div>',
        unsafe_allow_html=True,
    )

    tab_patch, tab_diff, tab_logs = st.tabs(["✨ Patched Code", "🔍 Unified Diff", "📄 Verification Logs"])

    # Tab 1: Patched Code
    with tab_patch:
        if patched_code:
            st.code(patched_code, language="python")
        else:
            st.markdown('<div style="color:#8b949e;font-size:0.82rem;padding:8px 0">Patched code will appear here after analysis.</div>', unsafe_allow_html=True)

    # Tab 2: Unified Diff
    with tab_diff:
        if patch_diff:
            colored = []
            for line in patch_diff.splitlines():
                if line.startswith(("+++", "---")):
                    colored.append(f'<span class="diff-hdr">{_esc(line)}</span>')
                elif line.startswith("@@"):
                    colored.append(f'<span class="diff-hdr">{_esc(line)}</span>')
                elif line.startswith("+"):
                    colored.append(f'<span class="diff-add">{_esc(line)}</span>')
                elif line.startswith("-"):
                    colored.append(f'<span class="diff-del">{_esc(line)}</span>')
                else:
                    colored.append(f'<span class="diff-ctx">{_esc(line)}</span>')
            st.markdown(
                '<div class="fix-chrome">'
                '  <span style="font-size:0.75rem;color:#8b949e">🐍 patch.diff</span>'
                '  <div style="display:flex;gap:6px">'
                '    <span style="background:#1f3a5f;color:#388bfd;border:1px solid #388bfd;border-radius:5px;padding:2px 10px;font-size:0.7rem">Unified</span>'
                '  </div>'
                '</div>'
                '<div class="fix-body">' + "\n".join(colored) + "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div style="color:#8b949e;font-size:0.82rem;padding:8px 0">Diff will appear here after analysis.</div>', unsafe_allow_html=True)

    # Tab 3: Verification Logs
    with tab_logs:
        is_snippet = st.session_state.get("active_file", "<snippet>") == "<snippet>"
        if result is None and is_snippet:
            code_to_check = patched_code or ""
            try:
                _ast.parse(code_to_check)
                st.success("✅ Patched code passes AST compilation check.")
                st.code("AST parse OK — no syntax errors detected.", language="text")
            except SyntaxError as e:
                st.error(f"⚠️ Patched code still has a syntax issue: {e}")
        elif result:
            all_passed = result["exit_code"] == 0
            if all_passed:
                st.success(f"🎉 All tests passed — {result['passed']} / {result['total']}")
            else:
                st.error(f"❌ {result['failed']} failed, {result['passed']} passed ({result['total']} total)")

            m1, m2, m3 = st.columns(3)
            m1.metric("Passed",    result["passed"])
            m2.metric("Failed",    result["failed"])
            m3.metric("Exit Code", result["exit_code"])

            for tr in result.get("test_results", []):
                icon  = {"PASSED": "✅", "FAILED": "❌", "ERROR": "💥", "SKIPPED": "⏭"}.get(tr["status"], "❓")
                color = {"PASSED": "#3fb950", "FAILED": "#f85149", "ERROR": "#f85149"}.get(tr["status"], "#8b949e")
                st.markdown(
                    f'{icon} <span style="color:{color};font-family:monospace;font-size:0.82rem">'
                    f'{_esc(tr["node"])}</span> — '
                    f'<strong style="color:{color}">{tr["status"]}</strong>',
                    unsafe_allow_html=True,
                )
            with st.expander("Raw pytest output", expanded=False):
                st.code(result["stdout"], language="text")
        else:
            st.markdown(
                '<div style="color:#8b949e;font-size:0.82rem;padding:8px 0">'
                'pytest runs automatically for preset incidents. '
                'AST validation is used for custom pasted code.</div>',
                unsafe_allow_html=True,
            )

    # ── Prompt chips ──────────────────────────────────────────────────────
    st.markdown(
        '<div class="chip-row">'
        '  <span class="chip">🔍 Explain root cause</span>'
        '  <span class="chip">💡 Why this fix?</span>'
        '  <span class="chip">🧪 Generate test</span>'
        '  <span class="chip">📁 Check other files</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Chat input ────────────────────────────────────────────────────────
    st.text_input(
        "chat_q",
        placeholder="Ask anything about the code, error, or fix...",
        label_visibility="collapsed",
        key="chat_question",
    )
