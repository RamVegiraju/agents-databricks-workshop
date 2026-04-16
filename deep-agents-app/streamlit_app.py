"""
Streamlit frontend for the Research Assistant.

Features:
- Preset user dropdown with custom option
- Thread management (create new threads, switch between them)
- Sidebar explaining the memory architecture
- Chat interface calling the agent via per-request context managers
- Suggested prompts for quick exploration
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone

# Resolve oauth+pat auth conflict before any SDK import.
if os.environ.get("DATABRICKS_CLIENT_ID") and os.environ.get("DATABRICKS_CLIENT_SECRET"):
    os.environ.pop("DATABRICKS_TOKEN", None)

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Research Assistant",
    page_icon="🔬",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Preset users
# ---------------------------------------------------------------------------

PRESET_USERS = {
    "researcher-alice": "Alice (Researcher)",
    "analyst-bob": "Bob (Analyst)",
    "manager-carol": "Carol (Manager)",
}

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "user_id" not in st.session_state:
    st.session_state.user_id = "researcher-alice"

if "threads" not in st.session_state:
    st.session_state.threads = {}

if "active_thread_id" not in st.session_state:
    thread_id = str(uuid.uuid4())[:8]
    st.session_state.active_thread_id = thread_id
    st.session_state.threads[thread_id] = {
        "name": f"Thread {thread_id}",
        "messages": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

if "custom_user_id" not in st.session_state:
    st.session_state.custom_user_id = ""


# ---------------------------------------------------------------------------
# Agent invocation
# ---------------------------------------------------------------------------


async def call_agent(user_message: str, user_id: str, thread_id: str) -> str:
    """Call the research assistant agent with per-request context managers."""
    from databricks_langchain import AsyncCheckpointSaver, AsyncDatabricksStore

    LAKEBASE_INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME", "")
    EMBEDDING_ENDPOINT = os.environ.get("EMBEDDING_ENDPOINT", "databricks-gte-large-en")
    EMBEDDING_DIMS = int(os.environ.get("EMBEDDING_DIMS", "1024"))

    from agent import _build_agent, _load_mcp_tools

    async with AsyncDatabricksStore(
        instance_name=LAKEBASE_INSTANCE_NAME,
        embedding_endpoint=EMBEDDING_ENDPOINT,
        embedding_dims=EMBEDDING_DIMS,
    ) as store:
        async with AsyncCheckpointSaver(
            instance_name=LAKEBASE_INSTANCE_NAME,
        ) as checkpointer:

            mcp_tools = await _load_mcp_tools()
            deep_agent = _build_agent(store, checkpointer, mcp_tools)

            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                }
            }

            result = await deep_agent.ainvoke(
                {"messages": [{"role": "user", "content": user_message}]},
                config=config,
            )

    # Extract assistant response
    output_messages = result.get("messages", [])
    for msg in reversed(output_messages):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            return msg.content
        elif isinstance(msg, dict) and msg.get("role") == "assistant":
            return msg.get("content", "")

    return "I was unable to generate a response. Please try again."


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("Research Assistant")
    st.caption("Powered by deep-agents + Lakebase")

    st.divider()

    # User selection
    st.subheader("User Profile")
    user_options = list(PRESET_USERS.keys()) + ["custom"]
    user_labels = list(PRESET_USERS.values()) + ["Custom User ID"]

    selected_idx = st.selectbox(
        "Select user",
        range(len(user_options)),
        format_func=lambda i: user_labels[i],
        key="user_selector",
    )

    if user_options[selected_idx] == "custom":
        custom_id = st.text_input("Enter custom user ID", value=st.session_state.custom_user_id)
        st.session_state.custom_user_id = custom_id
        st.session_state.user_id = custom_id if custom_id else "custom-user"
    else:
        st.session_state.user_id = user_options[selected_idx]

    st.info(f"Active user: **{st.session_state.user_id}**")

    st.divider()

    # Thread management
    st.subheader("Threads")

    if st.button("New Thread", use_container_width=True):
        new_id = str(uuid.uuid4())[:8]
        st.session_state.threads[new_id] = {
            "name": f"Thread {new_id}",
            "messages": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        st.session_state.active_thread_id = new_id
        st.rerun()

    thread_ids = list(st.session_state.threads.keys())
    if thread_ids:
        active_idx = (
            thread_ids.index(st.session_state.active_thread_id)
            if st.session_state.active_thread_id in thread_ids
            else 0
        )
        selected_thread = st.radio(
            "Select thread",
            thread_ids,
            index=active_idx,
            format_func=lambda tid: (
                f"{st.session_state.threads[tid]['name']} "
                f"({len(st.session_state.threads[tid]['messages'])} msgs)"
            ),
        )
        st.session_state.active_thread_id = selected_thread

    st.divider()

    # Memory architecture explanation
    st.subheader("Memory Architecture")
    st.markdown(
        """
    **Short-term** (AsyncCheckpointSaver)
    - Per `thread_id` conversation history
    - Survives page refreshes within a thread
    - Stored in Lakebase

    **Long-term** (StoreBackend at `/memories/`)
    - Per `user_id` preferences and findings
    - Persists across threads and sessions
    - Written to `/memories/preferences.txt`
      and `/memories/findings.txt`

    **Ephemeral** (StateBackend)
    - Scratch space at `/scratch/`
    - Lost when thread ends
    - Used for intermediate reasoning
    """
    )

# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------

st.header("Research Assistant")

# Get active thread
active_thread = st.session_state.threads.get(st.session_state.active_thread_id, None)
if active_thread is None:
    st.error("No active thread. Create a new one from the sidebar.")
    st.stop()

# Display chat history
for msg in active_thread["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Suggested prompts (only show when thread is empty)
if not active_thread["messages"]:
    st.markdown("**Try one of these prompts:**")
    suggested_prompts = [
        "Research the benefits of lakehouse architecture",
        "Remember I prefer bullet-point summaries",
        "What do you know about me from past sessions?",
        "Fact-check: Delta Lake supports ACID transactions",
    ]

    cols = st.columns(2)
    for i, prompt in enumerate(suggested_prompts):
        col = cols[i % 2]
        if col.button(prompt, key=f"suggested_{i}", use_container_width=True):
            active_thread["messages"].append({"role": "user", "content": prompt})
            st.rerun()

# Chat input
user_input = st.chat_input("Ask a research question...")

if user_input:
    active_thread["messages"].append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Researching..."):
            try:
                response = asyncio.run(
                    call_agent(
                        user_message=user_input,
                        user_id=st.session_state.user_id,
                        thread_id=st.session_state.active_thread_id,
                    )
                )
                st.markdown(response)
                active_thread["messages"].append({"role": "assistant", "content": response})
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                st.error(error_msg)
                active_thread["messages"].append({"role": "assistant", "content": error_msg})

# Also handle suggested prompt clicks that added a message
elif active_thread["messages"] and active_thread["messages"][-1]["role"] == "user":
    last_user_msg = active_thread["messages"][-1]["content"]
    # Check if there's already a response
    if len(active_thread["messages"]) < 2 or active_thread["messages"][-2]["role"] != "assistant":
        with st.chat_message("assistant"):
            with st.spinner("Researching..."):
                try:
                    response = asyncio.run(
                        call_agent(
                            user_message=last_user_msg,
                            user_id=st.session_state.user_id,
                            thread_id=st.session_state.active_thread_id,
                        )
                    )
                    st.markdown(response)
                    active_thread["messages"].append({"role": "assistant", "content": response})
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    active_thread["messages"].append({"role": "assistant", "content": error_msg})
