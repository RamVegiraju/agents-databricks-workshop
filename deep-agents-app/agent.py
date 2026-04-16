"""
Research Assistant Agent using deep-agents framework.

Demonstrates:
- create_deep_agent with subagent delegation
- CompositeBackend for memory (StateBackend ephemeral + StoreBackend persistent)
- TodoListMiddleware for multi-step task planning
- MCP tool integration for utility tools
- Lakebase-backed persistence (AsyncCheckpointSaver + AsyncDatabricksStore)
- MLflow ResponsesAgent with @invoke and @stream handlers
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

from databricks_langchain import AsyncCheckpointSaver, AsyncDatabricksStore
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    create_text_delta,
    output_to_responses_items_stream,
    to_chat_completions_input,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration from environment variables
# ---------------------------------------------------------------------------

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "")
LAKEBASE_INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME", "")
EMBEDDING_ENDPOINT = os.environ.get("EMBEDDING_ENDPOINT", "databricks-gte-large-en")
EMBEDDING_DIMS = int(os.environ.get("EMBEDDING_DIMS", "1024"))
MODEL = "databricks-claude-opus-4-5"

# ---------------------------------------------------------------------------
# System Prompts — context engineering best practices
# ---------------------------------------------------------------------------

MAIN_SYSTEM_PROMPT = """You are an expert research assistant deployed on Databricks Apps.
Your role is to help users research topics, analyze information, and produce well-structured findings.

## Your Capabilities
1. **Research**: Delegate deep-dive research to the researcher subagent.
2. **Fact-Checking**: Delegate claims verification to the fact-checker subagent.
3. **Memory**: You persist user preferences and important findings to /memories/ for future sessions.
4. **Task Planning**: For complex research, create a todo list before starting.
5. **Utility Tools**: Use MCP tools for time, math, and employee lookups.

## Guidelines
- For multi-step research, create a todo list FIRST using write_todos, then work through items.
- Save important user preferences to /memories/preferences.txt (e.g., preferred format, topics of interest).
- Save key findings to /memories/findings.txt for cross-session reference.
- Read from /memories/ at the start of conversations to personalize responses.
- When presenting research, lead with key findings, then supporting details.
- Always distinguish between verified facts and opinions/speculation.

## Response Format
- Lead with the key finding or answer.
- Use bullet points for multiple items.
- Structure longer responses with headers.
- End complex research with "Next Steps" suggestions.

Current date: {current_date}
"""

RESEARCHER_PROMPT = """You are a research specialist. Your job is to:
1. Gather and synthesize information on requested topics.
2. Provide structured, factual summaries with clear headers.
3. Highlight key takeaways and actionable insights.
4. Distinguish between facts, opinions, and speculation.
Keep summaries concise but comprehensive.
"""

FACT_CHECKER_PROMPT = """You are a fact-checking specialist. Your job is to:
1. Verify claims by cross-referencing available information.
2. Rate each claim as Verified, Plausible, Unverified, or False.
3. Provide reasoning for each rating.
4. Flag any claims that need additional sources.
Be thorough and skeptical. Never confirm without evidence.
"""

# ---------------------------------------------------------------------------
# Subagent definitions
# ---------------------------------------------------------------------------

SUBAGENTS = [
    {
        "name": "researcher",
        "description": (
            "A research specialist that gathers and synthesizes information on "
            "requested topics. Delegate to this subagent for deep-dive research, "
            "topic summaries, and information gathering."
        ),
        "system_prompt": RESEARCHER_PROMPT,
    },
    {
        "name": "fact-checker",
        "description": (
            "A fact-checking specialist that verifies claims and rates them as "
            "Verified, Plausible, Unverified, or False. Delegate to this subagent "
            "when the user wants claims checked or verified."
        ),
        "system_prompt": FACT_CHECKER_PROMPT,
    },
]


# ---------------------------------------------------------------------------
# MCP tool loading
# ---------------------------------------------------------------------------


async def _load_mcp_tools():
    """Load tools from the shared MCP server."""
    if not MCP_SERVER_URL:
        return []
    try:
        from databricks.sdk import WorkspaceClient
        from databricks_langchain import (
            DatabricksMCPServer,
            DatabricksMultiServerMCPClient,
        )

        mcp_client = DatabricksMultiServerMCPClient(
            [
                DatabricksMCPServer(
                    name="shared_mcp",
                    url=MCP_SERVER_URL,
                    workspace_client=WorkspaceClient(),
                )
            ]
        )
        return await mcp_client.get_tools()
    except Exception as e:
        logger.warning("Failed to load MCP tools: %s", e)
        return []


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def _build_agent(store, checkpointer, mcp_tools):
    """Build the deep-agent with subagents, CompositeBackend memory, and MCP tools."""
    from databricks_langchain import ChatDatabricks
    from deepagents import create_deep_agent
    from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

    system_prompt = MAIN_SYSTEM_PROMPT.format(
        current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )

    llm = ChatDatabricks(endpoint=MODEL)

    return create_deep_agent(
        name="research-assistant",
        model=llm,
        system_prompt=system_prompt,
        subagents=SUBAGENTS,
        tools=mcp_tools,
        backend=lambda rt: CompositeBackend(
            default=StateBackend(rt),
            routes={"/memories/": StoreBackend(rt)},
        ),
        checkpointer=checkpointer,
        store=store,
    )


# ---------------------------------------------------------------------------
# Stream event helpers (from Part06 reference)
# ---------------------------------------------------------------------------


def _chunk_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "".join(parts)
    return ""


def _normalize_ai_message_content(msg: Any) -> None:
    if isinstance(msg, AIMessage) and not isinstance(msg.content, str):
        msg.content = _chunk_text_content(msg.content)


async def _process_agent_astream_events(
    async_stream,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    text_seen_by_item: dict[str, str] = {}

    async for event in async_stream:
        if len(event) == 2:
            mode, payload = event
        else:
            _, mode, payload = event

        if mode == "updates":
            for node_data in payload.values():
                if not node_data or not isinstance(node_data, dict):
                    continue
                messages = node_data.get("messages", [])
                # deep-agents middleware may wrap messages in an Overwrite object
                if hasattr(messages, "value"):
                    messages = messages.value
                if not messages or not isinstance(messages, list):
                    continue
                for msg in messages:
                    _normalize_ai_message_content(msg)
                    if isinstance(msg, ToolMessage) and not isinstance(msg.content, str):
                        msg.content = json.dumps(msg.content)
                for item in output_to_responses_items_stream(iter(messages)):
                    yield item

        elif mode == "messages":
            chunk = payload[0]
            if isinstance(chunk, AIMessageChunk):
                item_id = chunk.id or str(uuid4())
                content = _chunk_text_content(chunk.content)
                if content:
                    previous = text_seen_by_item.get(item_id, "")
                    if content.startswith(previous):
                        delta = content[len(previous) :]
                        text_seen_by_item[item_id] = content
                    else:
                        delta = content
                        text_seen_by_item[item_id] = previous + content
                    if not delta:
                        continue
                    yield ResponsesAgentStreamEvent(
                        **create_text_delta(delta=delta, item_id=item_id)
                    )


# ---------------------------------------------------------------------------
# Helper: extract user_id / thread_id from request
# ---------------------------------------------------------------------------


def _get_user_id(request: ResponsesAgentRequest) -> str:
    custom = dict(request.custom_inputs or {})
    if "user_id" in custom:
        return custom["user_id"]
    ctx = request.context or {}
    if hasattr(ctx, "user_id") and ctx.user_id:
        return ctx.user_id
    return "anonymous"


def _get_thread_id(request: ResponsesAgentRequest) -> str:
    custom = dict(request.custom_inputs or {})
    return custom.get("thread_id", str(uuid4()))


# ---------------------------------------------------------------------------
# AgentServer endpoints
# ---------------------------------------------------------------------------


@invoke()
async def non_streaming(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    outputs = [
        event.item
        async for event in streaming(request)
        if event.type == "response.output_item.done"
    ]
    return ResponsesAgentResponse(output=outputs, custom_outputs=request.custom_inputs)


@stream()
async def streaming(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    user_id = _get_user_id(request)
    thread_id = _get_thread_id(request)

    messages = {
        "messages": to_chat_completions_input(
            [item.model_dump() for item in request.input]
        )
    }

    async with AsyncDatabricksStore(
        instance_name=LAKEBASE_INSTANCE_NAME,
        embedding_endpoint=EMBEDDING_ENDPOINT,
        embedding_dims=EMBEDDING_DIMS,
    ) as store:
        async with AsyncCheckpointSaver(
            instance_name=LAKEBASE_INSTANCE_NAME,
        ) as checkpointer:

            config: dict[str, Any] = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                }
            }

            mcp_tools = await _load_mcp_tools()
            agent = _build_agent(store, checkpointer, mcp_tools)

            async for event in _process_agent_astream_events(
                agent.astream(
                    input=messages,
                    config=config,
                    stream_mode=["updates", "messages"],
                )
            ):
                yield event
