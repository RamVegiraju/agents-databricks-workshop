"""
Agent construction for the hello-world agent.

Creates a LangGraph ReAct agent backed by ChatDatabricks, MCP tools loaded
from a deployed Databricks App, and explicit memory tools.
"""

import os

from databricks_langchain import (
    ChatDatabricks,
    DatabricksMCPServer,
    DatabricksMultiServerMCPClient,
)
from langgraph.prebuilt import create_react_agent

from databricks.sdk import WorkspaceClient

from agent.memory import get_memory_tools

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a friendly assistant deployed on Databricks Apps.

## Memory Guidelines
- At the start of each conversation, call get_user_memory to check for relevant context about this user.
- When the user shares important preferences, facts, or decisions, call save_user_memory to persist them.
- If the user asks you to forget something, call delete_user_memory.
- Use retrieved memories to personalize your responses.

## Tool Use
- Use get_current_time for time/date questions.
- Use calculator for math.
- Use lookup_employee for company directory lookups.
- Only call tools when necessary to answer accurately.
"""


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


async def init_agent(store, checkpointer):
    """Build and return the ReAct agent.

    Args:
        store: An initialized AsyncDatabricksStore instance.
        checkpointer: An initialized AsyncCheckpointSaver instance.

    Returns:
        A compiled LangGraph agent ready for invocation.
    """
    # --- LLM ---
    model = ChatDatabricks(endpoint="databricks-claude-opus-4-5")

    # --- MCP tools from deployed server ---
    mcp_server_url = os.environ.get("MCP_SERVER_URL", "")
    mcp_tools = []
    if mcp_server_url:
        mcp_client = DatabricksMultiServerMCPClient(
            [
                DatabricksMCPServer(
                    name="shared_mcp",
                    url=mcp_server_url,
                    workspace_client=WorkspaceClient(),
                )
            ]
        )
        mcp_tools = await mcp_client.get_tools()

    # --- Memory tools ---
    memory_tools = get_memory_tools()

    # --- Combine all tools ---
    all_tools = mcp_tools + memory_tools

    # --- Create agent ---
    agent = create_react_agent(
        model=model,
        tools=all_tools,
        checkpointer=checkpointer,
        store=store,
        prompt=SYSTEM_PROMPT,
    )

    return agent
