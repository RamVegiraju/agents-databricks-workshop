"""
LangGraph ReAct agent deployed to Databricks Model Serving.

Uses the same shared MCP server tools as the other agent samples,
wrapped in a ResponsesAgent with streaming and non-streaming support.

Includes both short-term memory (AsyncCheckpointSaver per thread_id) and
long-term memory (AsyncDatabricksStore with explicit memory tools per user_id),
backed by the shared Lakebase instance.
"""

import asyncio
import json
import os
from typing import AsyncGenerator, Generator
from uuid import uuid4

import mlflow
import nest_asyncio
from databricks.sdk import WorkspaceClient
from databricks_langchain import (
    AsyncCheckpointSaver,
    AsyncDatabricksStore,
    ChatDatabricks,
)
from databricks_mcp import DatabricksMCPClient
from langchain_core.messages import AIMessageChunk, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.store.base import BaseStore
from mlflow.models import set_model
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    output_to_responses_items_stream,
    to_chat_completions_input,
)

nest_asyncio.apply()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_ENDPOINT = "databricks-claude-opus-4-5"
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "")
LAKEBASE_INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME", "")
EMBEDDING_ENDPOINT = os.environ.get("EMBEDDING_ENDPOINT", "databricks-gte-large-en")
EMBEDDING_DIMS = int(os.environ.get("EMBEDDING_DIMS", "1024"))

SYSTEM_PROMPT = """You are a helpful assistant deployed on Databricks Model Serving.

## Memory Guidelines
- At the start of each conversation, call get_user_memory to check for relevant context about this user.
- When the user shares important preferences, facts, or decisions, call save_user_memory to persist them.
- If the user asks you to forget something, call delete_user_memory.
- Use retrieved memories to personalize your responses.

## Tool Use
- Use get_current_time for time/date questions.
- Use calculator for math expressions.
- Use lookup_employee for company directory lookups.
- Only call tools when necessary to answer accurately.
"""

# ---------------------------------------------------------------------------
# Explicit memory tools (same pattern as hello-world-agent)
# ---------------------------------------------------------------------------


@tool
async def get_user_memory(query: str, config: RunnableConfig) -> str:
    """Search for relevant information about the user from long-term memory.

    Uses semantic search so queries don't need to match stored text exactly.
    Call this at the start of every conversation to personalize responses.

    Args:
        query: What to search for (e.g. "user preferences", "past interactions").
    """
    user_id = config.get("configurable", {}).get("user_id")
    store: BaseStore | None = config.get("configurable", {}).get("store")
    if not user_id or not store:
        return "Memory not available."
    namespace = ("user_memories", user_id.replace(".", "-"))
    results = await store.asearch(namespace, query=query, limit=5)
    if not results:
        return "No memories found for this user."
    items = [f"- [{item.key}]: {json.dumps(item.value)}" for item in results]
    return f"Found {len(results)} memories:\n" + "\n".join(items)


@tool
async def save_user_memory(
    memory_key: str, memory_data_json: str, config: RunnableConfig
) -> str:
    """Save information about the user to long-term memory.

    Use this to remember user preferences, important details, or other
    information that should persist across conversations.

    Args:
        memory_key: A short identifier for this memory (e.g. "name", "fav-color").
        memory_data_json: A JSON object string with the data to store (e.g. '{"value": "blue"}').
    """
    user_id = config.get("configurable", {}).get("user_id")
    store: BaseStore | None = config.get("configurable", {}).get("store")
    if not user_id or not store:
        return "Cannot save - no user_id or store."
    namespace = ("user_memories", user_id.replace(".", "-"))
    try:
        data = json.loads(memory_data_json)
        if not isinstance(data, dict):
            return f"Failed: must be a JSON object, not {type(data).__name__}"
        await store.aput(namespace, memory_key, data)
        return f"Saved memory '{memory_key}'."
    except json.JSONDecodeError as e:
        return f"Failed: Invalid JSON - {e}"


@tool
async def delete_user_memory(memory_key: str, config: RunnableConfig) -> str:
    """Delete a specific memory from long-term storage.

    Use when the user asks you to forget something or correct stored information.

    Args:
        memory_key: The identifier of the memory to delete.
    """
    user_id = config.get("configurable", {}).get("user_id")
    store: BaseStore | None = config.get("configurable", {}).get("store")
    if not user_id or not store:
        return "Cannot delete - no user_id or store."
    namespace = ("user_memories", user_id.replace(".", "-"))
    await store.adelete(namespace, memory_key)
    return f"Deleted memory '{memory_key}'."


MEMORY_TOOLS = [get_user_memory, save_user_memory, delete_user_memory]

# ---------------------------------------------------------------------------
# MCP tools (loaded once at module init)
# ---------------------------------------------------------------------------


def _load_mcp_tools():
    """Load tools from the shared MCP server synchronously."""
    if not MCP_SERVER_URL:
        return []
    try:
        ws = WorkspaceClient()
        client = DatabricksMCPClient(server_url=MCP_SERVER_URL, workspace_client=ws)
        return client.get_langchain_tools()
    except Exception as e:
        print(f"Warning: Could not load MCP tools: {e}")
        return []


MCP_TOOLS = _load_mcp_tools()
LLM = ChatDatabricks(endpoint=MODEL_ENDPOINT)


# ---------------------------------------------------------------------------
# Helper: extract user_id / thread_id from request
# ---------------------------------------------------------------------------


def _get_user_id(request: ResponsesAgentRequest) -> str:
    custom = dict(request.custom_inputs or {})
    return custom.get("user_id", "anonymous")


def _get_thread_id(request: ResponsesAgentRequest) -> str:
    custom = dict(request.custom_inputs or {})
    return custom.get("thread_id", str(uuid4()))


# ---------------------------------------------------------------------------
# ResponsesAgent wrapper with per-request memory
# ---------------------------------------------------------------------------


class MCPResponsesAgent(ResponsesAgent):
    """Wraps a LangGraph agent as a ResponsesAgent for Model Serving.

    Each request creates fresh Lakebase connections for:
      - Short-term memory: AsyncCheckpointSaver (conversation history per thread_id)
      - Long-term memory: AsyncDatabricksStore (user facts per user_id via memory tools)

    Supports both streaming (predict_stream) and non-streaming (predict).
    """

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        """Non-streaming: collects all done-items from the stream."""
        outputs = [
            event.item
            for event in self.predict_stream(request)
            if event.type == "response.output_item.done" or event.type == "error"
        ]
        return ResponsesAgentResponse(output=outputs)

    async def _predict_stream_async(
        self, request: ResponsesAgentRequest
    ) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
        """Async streaming with per-request Lakebase connections."""
        user_id = _get_user_id(request)
        thread_id = _get_thread_id(request)
        cc_msgs = to_chat_completions_input([i.model_dump() for i in request.input])

        async with AsyncDatabricksStore(
            instance_name=LAKEBASE_INSTANCE_NAME,
            embedding_endpoint=EMBEDDING_ENDPOINT,
            embedding_dims=EMBEDDING_DIMS,
        ) as store:
            async with AsyncCheckpointSaver(
                instance_name=LAKEBASE_INSTANCE_NAME,
            ) as checkpointer:

                # Build agent per-request (checkpointer must be set at creation)
                all_tools = MCP_TOOLS + MEMORY_TOOLS
                agent = create_react_agent(
                    model=LLM,
                    tools=all_tools,
                    checkpointer=checkpointer,
                    store=store,
                    prompt=SYSTEM_PROMPT,
                )

                config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "user_id": user_id,
                        "store": store,
                    }
                }

                async for event in agent.astream(
                    {"messages": cc_msgs},
                    config=config,
                    stream_mode=["updates", "messages"],
                ):
                    if event[0] == "updates":
                        for node_data in event[1].values():
                            msgs = node_data.get("messages", [])
                            if msgs:
                                for msg in msgs:
                                    if isinstance(msg, ToolMessage) and not isinstance(
                                        msg.content, str
                                    ):
                                        msg.content = json.dumps(msg.content)
                                for item in output_to_responses_items_stream(msgs):
                                    yield item

                    elif event[0] == "messages":
                        try:
                            chunk = event[1][0]
                            if isinstance(chunk, AIMessageChunk) and (
                                content := chunk.content
                            ):
                                yield ResponsesAgentStreamEvent(
                                    **self.create_text_delta(
                                        delta=content, item_id=chunk.id
                                    ),
                                )
                        except Exception:
                            pass

    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        """Sync wrapper over the async stream for Model Serving compatibility."""
        agen = self._predict_stream_async(request)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        ait = agen.__aiter__()
        while True:
            try:
                item = loop.run_until_complete(ait.__anext__())
            except StopAsyncIteration:
                break
            else:
                yield item


mlflow.langchain.autolog()
agent = MCPResponsesAgent()
set_model(agent)
