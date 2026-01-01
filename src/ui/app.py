import asyncio
import json
import logging
import sqlite3
import os
import streamlit as st
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
from src.workflow.workflow import EmailWorkflow
from src.utils.logging import setup_logging

logger = setup_logging()

# Check for debug mode via query parameter
debug_mode = st.query_params.get("debug", "0") == "1"

# Hide header IMMEDIATELY before anything else renders (if not in debug mode)
if not debug_mode:
    st.markdown("""
    <style>
        /* Hide Streamlit header and menu */
        header {display: none !important;}
        #MainMenu {display: none !important;}
        footer {display: none !important;}
        .stDeployButton {display: none !important;}
        div[data-testid="stToolbar"] {display: none !important;}
        div[data-testid="stDecoration"] {display: none !important;}
        div[data-testid="stStatusWidget"] {display: none !important;}
        div[data-testid="stSidebarHeader"] {display: none !important;}
        section[data-testid="stSidebar"] > div:first-child {padding-top: 2rem;}
        .main .block-container {padding-top: 1rem !important;}
        
        /* Target the header more specifically */
        header[data-testid="stHeader"] {
            display: none !important;
            height: 0 !important;
            visibility: hidden !important;
        }
        
        /* Remove any top spacing from the app */
        .stApp > header {
            display: none !important;
        }
        .appview-container {
            padding-top: 0 !important;
        }
        .block-container {
            padding-top: 1rem !important;
        }
    </style>
    """, unsafe_allow_html=True)

# Silence noisy libraries
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.INFO)
logging.getLogger("langgraph").setLevel(logging.INFO)
logging.getLogger("LiteLLM").setLevel(logging.INFO)
logging.getLogger("LiteLLM Router").setLevel(logging.INFO)

# Avoid repeating this on every Streamlit rerun
if "logger_announced" not in st.session_state:
    logger.info("UI logger is configured (should appear in terminal).")
    st.session_state["logger_announced"] = True


# ----------------------------
# Database helper functions
# ----------------------------
def get_db_path():
    """Get the path to the SQLite database."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "data", "email_assist.db")


def load_user_profiles():
    """Load user profiles from the database."""
    db_path = get_db_path()
    profiles = {}
    
    if not os.path.exists(db_path):
        logger.warning(f"Database not found at {db_path}")
        return profiles
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, profile_json FROM user_profiles ORDER BY user_id;")
        rows = cursor.fetchall()
        conn.close()
        
        for user_id, profile_json in rows:
            try:
                profile = json.loads(profile_json)
                profiles[user_id] = profile
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON for user_id {user_id}")
                continue
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
    
    return profiles


# ----------------------------
# PDF Generation
# ----------------------------
def generate_pdf(text):
    """Generate a PDF from the email draft text."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1*inch, bottomMargin=1*inch)
    styles = getSampleStyleSheet()
    
    # Custom style for email content
    email_style = ParagraphStyle(
        'EmailStyle',
        parent=styles['Normal'],
        fontSize=11,
        leading=16,
        spaceAfter=12,
    )
    
    story = []
    
    # Split text into paragraphs and add to document
    paragraphs = text.split('\n')
    for para in paragraphs:
        if para.strip():
            # Escape special characters for ReportLab
            safe_para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(safe_para, email_style))
        else:
            story.append(Spacer(1, 12))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


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
# UI Setup & Custom Styling
# ----------------------------
st.set_page_config(
    page_title="EMaiL Assist: AI-Powered Email Generator",
    page_icon="✉️",
    layout="wide"
)

# Custom CSS for polished look (header hiding is handled above)
st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* Header styling */
    h1 {
        color: #5D2E3D;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    h2, h3 {
        color: #6B3A4A;
        font-weight: 600;
    }
    
    /* Sidebar styling - maroon theme */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #FAF5F7 0%, #F0E4E8 100%);
    }
    
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stTextArea label {
        font-weight: 600;
        color: #5D2E3D;
    }
    
    /* Button styling - maroon theme with WHITE text */
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #8B4557 0%, #6B3A4A 100%);
        border: none;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
        color: white !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(90deg, #6B3A4A 0%, #5D2E3D 100%);
        box-shadow: 0 4px 12px rgba(107, 58, 74, 0.4);
        color: white !important;
    }
    
    .stButton > button[kind="primary"] p {
        color: white !important;
    }
    
    /* Text area styling - maroon theme */
    .stTextArea textarea {
        border-radius: 8px;
        border: 2px solid #E8D8DD;
        background-color: #FDF9FA;
        transition: border-color 0.3s ease;
    }
    
    .stTextArea textarea:focus {
        border-color: #8B4557;
        box-shadow: 0 0 0 3px rgba(139, 69, 87, 0.1);
    }
    
    /* Card-like containers */
    .output-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        border: 1px solid #E8D8DD;
    }
    
    /* Preview section - maroon theme */
    .preview-content {
        background: #FDF9FA;
        border-radius: 8px;
        padding: 1.5rem;
        border-left: 4px solid #8B4557;
        min-height: 340px;
        font-family: 'Georgia', serif;
        line-height: 1.6;
        color: #4A3540;
    }
    
    .preview-placeholder {
        color: #A08890;
        font-style: italic;
        text-align: center;
        padding: 2rem;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    
    .status-success {
        background: #C6F6D5;
        color: #22543D;
    }
    
    .status-warning {
        background: #FEEBC8;
        color: #744210;
    }
    
    .status-error {
        background: #FED7D7;
        color: #822727;
    }
    
    /* Divider */
    hr {
        margin: 2rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #D4C4C9, transparent);
    }
    
    /* Tips expander */
    .streamlit-expanderHeader {
        font-weight: 600;
        color: #5D2E3D;
    }
    
    /* Download button - maroon theme */
    .stDownloadButton > button {
        border-radius: 8px;
        border: 2px solid #8B4557;
        color: #8B4557;
        background: transparent;
        transition: all 0.3s ease;
    }
    
    .stDownloadButton > button:hover {
        background: #8B4557;
        color: white;
    }
    
    /* Error message box */
    .error-message {
        background: #FED7D7;
        border: 1px solid #FC8181;
        border-radius: 8px;
        padding: 1rem;
        color: #822727;
        margin-top: 0.5rem;
    }
    
    /* Warning message box */
    .warning-message {
        background: #FEEBC8;
        border: 1px solid #F6AD55;
        border-radius: 8px;
        padding: 1rem;
        color: #744210;
        margin-top: 0.5rem;
    }
    
    /* Subtitle */
    .subtitle {
        color: #7A5A65;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Profile details box - maroon theme */
    .profile-details {
        background: #FAF0F3;
        border-radius: 8px;
        padding: 0.75rem;
        margin-top: 0.5rem;
        font-size: 0.9rem;
    }
    
    /* Preview container styling */
    [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #FDF9FA;
        border-left: 4px solid #8B4557 !important;
        border-radius: 8px;
        min-height: 340px;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("✉️ EMaiL Assist")
st.markdown('<p class="subtitle">AI-Powered Professional Email Generator</p>', unsafe_allow_html=True)

# Keep workflow instance stable
if "workflow" not in st.session_state:
    st.session_state.workflow = EmailWorkflow(logger)

# Canonical session state
if "draft_editor" not in st.session_state:
    st.session_state["draft_editor"] = ""
if "validation_report" not in st.session_state:
    st.session_state["validation_report"] = None
if "last_response" not in st.session_state:
    st.session_state["last_response"] = None
if "validation_status" not in st.session_state:
    st.session_state["validation_status"] = None


# ----------------------------
# Sidebar controls
# ----------------------------
st.sidebar.markdown("## ⚙️ Settings")
st.sidebar.markdown('<div style="margin-bottom: 1rem;"></div>', unsafe_allow_html=True)

# User Profile Dropdown
st.sidebar.markdown("### 👤 User Profile")
user_profiles = load_user_profiles()

# Build options with (default) as first choice
user_options = {"(default)": "default"}
for user_id, profile in user_profiles.items():
    display_name = profile.get("name", f"User {user_id}")
    user_options[display_name] = user_id

selected_user_display = st.sidebar.selectbox(
    "Select User",
    options=list(user_options.keys()),
    index=0,
    help="Select a user profile to personalize the email"
)

selected_user_id = user_options.get(selected_user_display)

# Show selected user details only if not default - with expand/contract animation
if selected_user_display != "(default)" and selected_user_id in user_profiles:
    profile = user_profiles[selected_user_id]
    st.sidebar.markdown(f"""
    <style>
        @keyframes expandIn {{
            from {{
                max-height: 0;
                opacity: 0;
                padding: 0 0.75rem;
            }}
            to {{
                max-height: 200px;
                opacity: 1;
                padding: 0.75rem;
            }}
        }}
        .profile-details-animated {{
            animation: expandIn 0.3s ease-out forwards;
            overflow: hidden;
        }}
    </style>
    <div class="profile-details profile-details-animated">
        <strong>Name:</strong> {profile.get('name', 'N/A')}<br>
        <strong>Title:</strong> {profile.get('title', 'N/A')}<br>
        <strong>Organization:</strong> {profile.get('org', 'N/A')}
        {"<br><strong>Email:</strong> " + profile.get('email') if profile.get('email') else ""}
    </div>
    """, unsafe_allow_html=True)
else:
    # Empty placeholder to ensure profile details are cleared when switching back to default
    st.sidebar.empty()

st.sidebar.markdown('<div style="margin-top: 3rem;"></div>', unsafe_allow_html=True)
st.sidebar.markdown("### 📝 Email Options")

tone = st.sidebar.selectbox(
    "Tone",
    options=["(auto)", "formal", "friendly", "assertive", "apologetic", "concise"],
    index=0,
    help="Choose the tone for your email"
)

intent = st.sidebar.selectbox(
    "Intent",
    options=["(auto)", "outreach", "follow_up", "apology", "info", "request", "scheduling", "thank_you", "other"],
    index=0,
    help="Specify the purpose of your email"
)

st.sidebar.markdown('<div style="margin-top: 3rem;"></div>', unsafe_allow_html=True)
with st.sidebar.expander("💡 Tips", expanded=False):
    st.caption("• Select a user profile to include your details automatically")
    st.caption("• Use 'auto' for tone/intent to let AI decide")
    st.caption("• Press **Cmd/Ctrl + Enter** to generate quickly")
    st.caption("• Edit the draft directly in the editor")


# ----------------------------
# Main input section
# ----------------------------
st.markdown("### 📧 Compose Your Email")

tone_override = None if tone == "(auto)" else tone
intent_override = None if intent == "(auto)" else intent

# Build metadata from selected user
metadata = {"user_id": selected_user_id}

user_query = st.text_area(
    "What email would you like to write?",
    placeholder="Example: Ask my manager for a meeting next week to discuss project priorities and deadlines...",
    height=150,
    key="user_query",
)

# Settings summary
settings_parts = []
settings_parts.append(f"**Tone:** {tone_override or 'auto'}")
settings_parts.append(f"**Intent:** {intent_override or 'auto'}")
if selected_user_id and selected_user_id != "default":
    settings_parts.append(f"**User:** {selected_user_display}")

st.caption(" · ".join(settings_parts))

col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    generate_clicked = st.button(
        "✨ Generate Email",
        type="primary",
        disabled=not bool(user_query.strip()),
        use_container_width=True
    )

# Cmd/Ctrl+Enter shortcut
st.components.v1.html(
    """
    <script>
    const streamlitDoc = window.parent.document;
    streamlitDoc.addEventListener('keydown', function(e) {
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        const metaOrCtrl = isMac ? e.metaKey : e.ctrlKey;
        if (metaOrCtrl && e.key === 'Enter') {
            const btns = Array.from(streamlitDoc.querySelectorAll('button'));
            const target = btns.find(b => (b.innerText || '').includes('Generate Email'));
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
    with st.spinner("🔄 Generating your email..."):
        response = run_async(
            st.session_state.workflow.run_query(
                user_input=user_query,
                tone=tone_override,
                intent=intent_override,
                metadata=metadata,
            )
        )

    logger.info(f"UI received draft length: {len((response.get('draft') or ''))}")

    st.session_state["last_response"] = response
    st.session_state["validation_report"] = response.get("validation_report")
    
    vr = response.get("validation_report") or {}
    status = (vr.get("status") or "").upper()
    st.session_state["validation_status"] = status

    # Handle BLOCKED status - clear the draft
    if status == "BLOCKED":
        st.session_state["draft_editor"] = ""
    else:
        draft = response.get("draft") or ""
        st.session_state["draft_editor"] = draft

    # If input_parser ended early, show guidance
    messages = response.get("messages", [])
    if not response.get("draft") and messages:
        last = messages[-1]
        content = getattr(last, "content", "")
        if content:
            st.info(content)

st.divider()


# ----------------------------
# Output section
# ----------------------------
left, right = st.columns(2)

with left:
    st.markdown("### ✏️ Editable Draft")
    
    vr = st.session_state.get("validation_report") or {}
    status = st.session_state.get("validation_status") or ""
    
    # Apply error styling if FAIL or BLOCKED
    if status in ["FAIL", "BLOCKED"]:
        st.markdown("""
        <style>
            div[data-testid="stTextArea"] textarea {
                border: 2px solid #E53E3E !important;
                background-color: #FFF5F5 !important;
            }
        </style>
        """, unsafe_allow_html=True)
    
    st.text_area(
        "Edit your email below:",
        height=340,
        key="draft_editor",
        label_visibility="collapsed"
    )
    
    # Display suggested fix for FAIL or BLOCKED
    if status == "FAIL":
        suggested_fix = vr.get("suggested_fix", "")
        if suggested_fix:
            st.markdown(f"""
            <div class="warning-message">
                <strong>⚠️ Suggested Fix:</strong><br>{suggested_fix}
            </div>
            """, unsafe_allow_html=True)
    
    if status == "BLOCKED":
        suggested_fix = vr.get("suggested_fix", "")
        if suggested_fix:
            st.markdown(f"""
            <div class="error-message">
                <strong>🚫 Blocked:</strong><br>{suggested_fix}
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    draft_content = st.session_state["draft_editor"] or ""
    has_content = bool(draft_content.strip())
    
    col_a, col_b, col_c = st.columns([1, 1, 2])
    
    with col_a:
        if has_content:
            pdf_buffer = generate_pdf(draft_content)
            st.download_button(
                "📥 Export PDF",
                data=pdf_buffer,
                file_name="email_draft.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        else:
            st.download_button(
                "📥 Export PDF",
                data="",
                file_name="email_draft.pdf",
                mime="application/pdf",
                disabled=True,
                use_container_width=True
            )

    with col_b:
        # Use st.components.v1.html for proper HTML button rendering with clipboard functionality
        if has_content:
            # Escape content for JavaScript - handle backslashes, backticks, and template literals
            escaped_content = draft_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${").replace("\n", "\\n").replace("\r", "\\r")
            
            st.components.v1.html(f"""
            <style>
                html, body {{
                    margin: 0 !important;
                    padding: 0 !important;
                    overflow: hidden;
                }}
            </style>
            <button id="copyBtn" style="
                width: 100%;
                padding: 0.5rem 1rem;
                border-radius: 8px;
                border: 1px solid rgba(49, 57, 66, 0.2);
                background: white;
                color: rgb(49, 51, 63);
                cursor: pointer;
                font-weight: 400;
                font-size: 0.875rem;
                font-family: 'Source Sans Pro', sans-serif;
                line-height: 1.6;
                height: 38px;
                transition: all 0.2s ease;
                box-sizing: border-box;
                margin: 0;
            "
            onmouseover="this.style.borderColor='#8B4557'; this.style.color='#8B4557';"
            onmouseout="if(this.innerText !== '✓ Copied!') {{ this.style.borderColor='rgba(49, 57, 66, 0.2)'; this.style.color='rgb(49, 51, 63)'; }}"
            onclick="
                const content = `{escaped_content}`;
                navigator.clipboard.writeText(content).then(() => {{
                    this.innerText = '✓ Copied!';
                    this.style.background = '#C6F6D5';
                    this.style.borderColor = '#22543D';
                    this.style.color = '#22543D';
                    setTimeout(() => {{
                        this.innerText = '📋 Copy';
                        this.style.background = 'white';
                        this.style.borderColor = 'rgba(49, 57, 66, 0.2)';
                        this.style.color = 'rgb(49, 51, 63)';
                    }}, 1500);
                }});
            ">
                📋 Copy
            </button>
            """, height=38)
        else:
            st.components.v1.html("""
            <style>
                html, body {
                    margin: 0 !important;
                    padding: 0 !important;
                    overflow: hidden;
                }
            </style>
            <button style="
                width: 100%;
                padding: 0.5rem 1rem;
                border-radius: 8px;
                border: 1px solid rgba(49, 57, 66, 0.2);
                background: white;
                color: rgb(49, 51, 63);
                font-weight: 400;
                font-size: 0.875rem;
                font-family: 'Source Sans Pro', sans-serif;
                line-height: 1.6;
                height: 38px;
                opacity: 0.5;
                cursor: not-allowed;
                box-sizing: border-box;
                margin: 0;
            " disabled>
                📋 Copy
            </button>
            """, height=38)

    if debug_mode:
        with st.expander("🔍 Agent Trace (Debug)", expanded=False):
            resp = st.session_state.get("last_response") or {}
            vr = st.session_state.get("validation_report")

            if not resp:
                st.caption("No debug data yet. Generate an email to populate the trace.")
            else:
                st.caption(f"**Response keys:** {', '.join(sorted(resp.keys()))}")

                # Intent debug
                intent_val = resp.get("intent")
                intent_conf = resp.get("intent_confidence")
                intent_src = resp.get("intent_source")

                if intent_val:
                    st.markdown("#### Intent Detection")
                    cols = st.columns(3)
                    cols[0].markdown(f"**Intent:** `{intent_val}`")
                    if intent_conf is not None:
                        try:
                            cols[1].markdown(f"**Confidence:** `{float(intent_conf):.2f}`")
                        except Exception:
                            cols[1].markdown(f"**Confidence:** `{intent_conf}`")
                    if intent_src:
                        cols[2].markdown(f"**Source:** `{intent_src}`")

                st.divider()

                # Validation report
                if isinstance(vr, dict):
                    st.markdown("#### Validation Report")
                    
                    status = (vr.get("status") or "").upper()
                    if status == "PASS":
                        st.markdown('<span class="status-badge status-success">✓ PASS</span>', unsafe_allow_html=True)
                    elif status == "FAIL":
                        st.markdown('<span class="status-badge status-warning">⚠ FAIL</span>', unsafe_allow_html=True)
                    elif status == "BLOCKED":
                        st.markdown('<span class="status-badge status-error">✗ BLOCKED</span>', unsafe_allow_html=True)
                    
                    st.json(vr)
                elif vr is not None:
                    st.markdown("#### Validation Report")
                    st.code(str(vr))

with right:
    st.markdown("### 👁️ Real-time Preview")
    
    draft_text = st.session_state.get("draft_editor") or ""
    
    if draft_text.strip():
        # Use st.container for the preview with custom CSS applied via class
        preview_container = st.container(border=True)
        with preview_container:
            st.markdown(draft_text)
        
        # Word/character count
        word_count = len(draft_text.split())
        char_count = len(draft_text)
        st.caption(f"📊 **{word_count}** words · **{char_count}** characters")
    else:
        st.markdown("""
        <div class="preview-content">
            <div class="preview-placeholder">
                📝 Your email preview will appear here once generated...
            </div>
        </div>
        """, unsafe_allow_html=True)