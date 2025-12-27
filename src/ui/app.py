import asyncio
import json
import logging
import sys
import streamlit as st

from src.workflow.workflow import EmailWorkflow


# ----------------------------
# Logging (terminal)
# ----------------------------
root = logging.getLogger()
root.setLevel(logging.DEBUG)

if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s:%(name)s:%(message)s"))
    root.addHandler(sh)

logger = logging.getLogger("EmailAssist")
logger.setLevel(logging.DEBUG)
logger.propagate = True

# Silence noisy libraries
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.INFO)
logging.getLogger("langgraph").setLevel(logging.INFO)

# Avoid repeating this on every Streamlit rerun
if "logger_announced" not in st.session_state:
    logger.info("UI logger is configured (should appear in terminal).")
    st.session_state["logger_announced"] = True


# ----------------------------
# Async runner (Streamlit-safe for Python 3.11)
# ----------------------------
def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ----------------------------
# UI Setup
# ----------------------------
st.set_page_config(page_title="AI-Powered Email Assistant", page_icon="✉️", layout="wide")
st.title("✉️ AI-Powered Email Assistant")

# Keep workflow instance stable
if "workflow" not in st.session_state:
    st.session_state.workflow = EmailWorkflow(logger)

# Canonical session state
if "draft_editor" not in st.session_state:
    st.session_state["draft_editor"] = ""  # source of truth for editable draft
if "validation_report" not in st.session_state:
    st.session_state["validation_report"] = None
if "last_response" not in st.session_state:
    st.session_state["last_response"] = None


# ----------------------------
# Sidebar controls (parameters only)
# ----------------------------
st.sidebar.header("Email Settings")

tone = st.sidebar.selectbox(
    "Tone",
    options=["(auto)", "formal", "friendly", "assertive", "apologetic", "concise"],
    index=0,
)

intent = st.sidebar.selectbox(
    "Intent",
    options=["(auto)", "outreach", "follow_up", "apology", "info", "internal_update", "request", "other"],
    index=0,
)

metadata_text = st.sidebar.text_area(
    "Optional metadata (JSON)",
    value="",
    placeholder='e.g., {"recipient_name": "Alex", "company": "Oracle", "deadline": "today"}',
    height=140,
)

with st.sidebar.expander("Tips", expanded=False):
    st.caption("Use metadata for recipient/context fields you want the system to treat as authoritative.")
    st.caption("Keyboard shortcut: Cmd/Ctrl+Enter in the prompt box to generate.")


# ----------------------------
# Main input + action (keep together)
# ----------------------------
st.subheader("Email Request")

tone_override = None if tone == "(auto)" else tone
intent_override = None if intent == "(auto)" else intent

# Parse metadata JSON safely
metadata = None
if metadata_text.strip():
    try:
        metadata = json.loads(metadata_text)
        if not isinstance(metadata, dict):
            st.sidebar.error('Metadata must be a JSON object (e.g., {"key": "value"}).')
            metadata = None
    except Exception as e:
        st.sidebar.error(f"Invalid JSON: {e}")
        metadata = None

user_query = st.text_area(
    "What email do you want to write?",
    placeholder="Ask my boss for a meeting next week to discuss priorities...",
    height=170,
    key="user_query",
)

st.caption(
    f"Effective settings — Tone: {tone_override or 'auto'} · Intent: {intent_override or 'auto'}"
    + (" · Metadata: provided" if isinstance(metadata, dict) and metadata else " · Metadata: none")
)

generate_clicked = st.button(
    "Generate Email",
    type="primary",
    disabled=not bool(user_query.strip()),
)

# Cmd/Ctrl+Enter shortcut -> click the button
st.components.v1.html(
    """
    <script>
    const streamlitDoc = window.parent.document;
    streamlitDoc.addEventListener('keydown', function(e) {
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        const metaOrCtrl = isMac ? e.metaKey : e.ctrlKey;
        if (metaOrCtrl && e.key === 'Enter') {
            const btns = Array.from(streamlitDoc.querySelectorAll('button'));
            const target = btns.find(b => (b.innerText || '').trim() === 'Generate Email');
            if (target) target.click();
        }
    });
    </script>
    """,
    height=0,
)


# ----------------------------
# Generate via workflow
# ----------------------------
if generate_clicked:
    with st.spinner("Generating..."):
        response = run_async(
            st.session_state.workflow.run_query(
                user_input=user_query,
                tone=tone_override,
                intent=intent_override,
                metadata=metadata,
            )
        )

    # Diagnostics
    logger.info(f"UI received draft length: {len((response.get('draft') or ''))}")

    # Persist response artifacts
    st.session_state["last_response"] = response
    st.session_state["validation_report"] = response.get("validation_report")

    # IMPORTANT: set the widget key directly (no value= on the widget)
    draft = response.get("draft") or ""
    st.session_state["draft_editor"] = draft

    # If input_parser ended early, show guidance
    messages = response.get("messages", [])
    if not draft and messages:
        last = messages[-1]
        content = getattr(last, "content", "")
        if content:
            st.info(content)

st.divider()


# ----------------------------
# Output: Editable draft + real-time preview
# ----------------------------
left, right = st.columns(2)

with left:
    st.subheader("Editable Draft")

    # DO NOT pass value= when using key and setting session_state programmatically
    st.text_area(
        "Edit the email below:",
        height=360,
        key="draft_editor",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "Export (.txt)",
            data=st.session_state["draft_editor"] or "",
            file_name="email_draft.txt",
            mime="text/plain",
            disabled=not bool((st.session_state["draft_editor"] or "").strip()),
        )

    with col_b:
        copy_payload = (st.session_state["draft_editor"] or "").replace("\\", "\\\\").replace("`", "\\`")
        st.components.v1.html(
            f"""
            <button style="padding:0.5rem 0.75rem; border-radius:6px; border:1px solid #ccc; cursor:pointer;"
                onclick="navigator.clipboard.writeText(`{copy_payload}`)">
                Copy to clipboard
            </button>
            """,
            height=50,
        )

    with st.expander("Agent Trace (debug)", expanded=False):
        resp = st.session_state.get("last_response") or {}
        vr = st.session_state.get("validation_report")

        if isinstance(vr, dict):
            status = (vr.get("status") or "").upper()
            if status:
                st.markdown(f"**Validation status:** {status}")
            st.json(vr)
        elif vr:
            st.code(str(vr))

        msgs = resp.get("messages", [])
        if msgs:
            st.markdown("**Last message:**")
            last_msg = msgs[-1]
            st.code(getattr(last_msg, "content", str(last_msg)))

with right:
    st.subheader("Real-time Preview")
    draft_text = st.session_state.get("draft_editor") or ""
    if draft_text.strip():
        st.markdown(draft_text)
    else:
        st.caption("Generate an email to see a preview here.")
