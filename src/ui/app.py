import streamlit as st
import asyncio
import logging
from src.workflow.workflow import EmailWorkflow

def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# Setup simple logging for the UI
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EMaiL Assist")

st.set_page_config(page_title="Finnie AI Debugger", page_icon="✉️")
st.title("✉️ EMaiL Assist: Simple Email Agent")

# Keep the workflow in session state so it doesn't reload every click
if "workflow" not in st.session_state:
    st.session_state.workflow = EmailWorkflow(logger)

user_query = st.text_input("What email do you want to write?", placeholder="Ask my boss for a meeting...")

if st.button("Generate"):
    if user_query:
        with st.spinner("Agent is drafting..."):
            response = run_async(
                st.session_state.workflow.run_query(user_query)
            )

            st.markdown("### Final Draft")
            st.info(response.get("draft", "Oops!"))
    else:
        st.warning("Please enter a topic.")