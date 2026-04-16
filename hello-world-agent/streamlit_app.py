"""
Streamlit chat frontend for the hello-world agent.

Demonstrates user-session isolation via user_id and thread_id, with both
short-term (checkpointer) and long-term (store) memory.
"""

import asyncio
import os
import sys
import uuid

# ---------------------------------------------------------------------------
# Resolve auth conflict BEFORE any SDK import.
# Databricks Apps inject both DATABRICKS_TOKEN (PAT) and OAuth SP creds
# (CLIENT_ID / CLIENT_SECRET).  The SDK rejects dual auth, so we drop the
# PAT when OAuth creds are present — the app should use OAuth only.
# ---------------------------------------------------------------------------
if os.environ.get("DATABRICKS_CLIENT_ID") and os.environ.get("DATABRICKS_CLIENT_SECRET"):
    os.environ.pop("DATABRICKS_TOKEN", None)

import streamlit as st
from dotenv import load_dotenv

# Ensure the project root is on the path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

load_dotenv()

from agent.agent import init_agent
from agent.memory import get_checkpointer, get_store

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Hello World Agent", page_icon="🤖", layout="wide")
st.title("Hello World Agent")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Session Settings")

    user_id = st.text_input("User ID", value="user-alice")
    thread_id = st.text_input(
        "Thread ID (conversation)",
        value=st.session_state.get("thread_id", str(uuid.uuid4())),
    )
    st.session_state["thread_id"] = thread_id

    if st.button("Clear Chat"):
        st.session_state["messages"] = []
        st.session_state["thread_id"] = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.subheader("How Memory Works")
    st.markdown(
        """
**Short-term memory** (conversation context) is tied to the
*Thread ID*. Change the thread ID to start a fresh conversation.
The agent remembers what was said earlier in the same thread.

**Long-term memory** is tied to the *User ID* and persists across
threads. The agent can save, recall, and delete facts about you
using explicit memory tools backed by Lakebase.
"""
    )

# ---------------------------------------------------------------------------
# Chat state
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Display history
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# Suggested prompts
# ---------------------------------------------------------------------------

suggestions = [
    "Remember my name is Alice",
    "What do you know about me?",
    "What time is it?",
    "Look up Bob's profile",
]

if not st.session_state["messages"]:
    cols = st.columns(len(suggestions))
    for col, suggestion in zip(cols, suggestions):
        if col.button(suggestion, use_container_width=True):
            st.session_state["pending_prompt"] = suggestion
            st.rerun()

# ---------------------------------------------------------------------------
# Handle input
# ---------------------------------------------------------------------------


async def _run_agent(user_input: str, user_id: str, thread_id: str) -> str:
    """Run the agent with per-request context managers and return the reply."""
    async with get_store() as store:
        async with get_checkpointer() as checkpointer:
            agent = await init_agent(store, checkpointer)

            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "store": store,
                }
            }

            from langchain_core.messages import HumanMessage

            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
            )
            return result["messages"][-1].content


def handle_input(user_input: str):
    """Process user input, call the agent, and update chat history."""
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = asyncio.run(
                _run_agent(
                    user_input,
                    user_id=user_id,
                    thread_id=st.session_state["thread_id"],
                )
            )
            st.markdown(reply)

    st.session_state["messages"].append({"role": "assistant", "content": reply})


# Check for pending prompt from suggestion buttons
if "pending_prompt" in st.session_state:
    prompt = st.session_state.pop("pending_prompt")
    handle_input(prompt)

# Normal chat input
if prompt := st.chat_input("Type your message..."):
    handle_input(prompt)
