# TraceFix — Autonomous AI Code Debugger Studio
> Autonomous defect triage · unified diff synthesis · live pytest verification

![TraceFix Studio Preview](assets/ui_reference.png)

🚀 **Live Application:** [Deploying on Streamlit Cloud](https://share.streamlit.io)

---

## ⚡ Key Highlights
- **Deterministic AST Guard Clauses:** Detects and patches unhandled `ZeroDivisionError`, `KeyError`, and `IndexError` at the AST level in 0ms.
- **Context-Aware Windowed Triage:** Isolates failing stack frames without mutating global codebase logic.
- **In-Memory Regression Verification:** Automatically executes targeted test assertions before outputting patches to preserve production happy paths.
- **Unified Diff Engine:** Synthesizes copyable Git-native diffs highlighting safe additions and deletions.

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/SAJIENDIRAN21/TraceFix.git
cd TraceFix
