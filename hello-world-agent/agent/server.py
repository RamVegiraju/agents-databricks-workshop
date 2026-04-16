"""
MLflow ResponsesAgent server handlers for the hello-world agent.

Implements @invoke and @stream endpoints. Each request opens its own
AsyncDatabricksStore and AsyncCheckpointSaver context managers (per-request
pattern), constructs the agent, and streams results back.
"""

import json
import logging
from typing import Any, AsyncGenerator
from uuid import uuid4

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

from agent.agent import init_agent
from agent.memory import get_checkpointer, get_store

logger = logging.getLogger(__name__)


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
                messages = node_data.get("messages", [])
                if not messages:
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
# Helper: extract user_id / thread_id
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

    async with get_store() as store:
        async with get_checkpointer() as checkpointer:

            config: dict[str, Any] = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "store": store,
                }
            }

            agent = await init_agent(store=store, checkpointer=checkpointer)

            async for event in _process_agent_astream_events(
                agent.astream(
                    input=messages,
                    config=config,
                    stream_mode=["updates", "messages"],
                )
            ):
                yield event
