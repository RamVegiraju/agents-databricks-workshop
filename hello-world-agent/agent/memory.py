"""
Memory tools and factory functions for the hello-world agent.

Provides explicit long-term memory tools (get/save/delete) that operate on
a per-user namespace in Lakebase, plus factory helpers for creating
AsyncDatabricksStore and AsyncCheckpointSaver instances.
"""

import json
import os

from databricks_langchain import AsyncCheckpointSaver, AsyncDatabricksStore
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.store.base import BaseStore


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def resolve_lakebase_instance_name() -> str:
    """Return the Lakebase instance name from environment variables."""
    name = os.environ.get("LAKEBASE_INSTANCE_NAME")
    if not name:
        raise RuntimeError(
            "LAKEBASE_INSTANCE_NAME environment variable is not set. "
            "Please set it to your Lakebase instance name."
        )
    return name


def get_store() -> AsyncDatabricksStore:
    """Create an AsyncDatabricksStore (use as async context manager)."""
    instance_name = resolve_lakebase_instance_name()
    embedding_endpoint = os.environ.get("EMBEDDING_ENDPOINT", "databricks-gte-large-en")
    embedding_dims = int(os.environ.get("EMBEDDING_DIMS", "1024"))

    return AsyncDatabricksStore(
        instance_name=instance_name,
        embedding_endpoint=embedding_endpoint,
        embedding_dims=embedding_dims,
    )


def get_checkpointer() -> AsyncCheckpointSaver:
    """Create an AsyncCheckpointSaver (use as async context manager)."""
    instance_name = resolve_lakebase_instance_name()
    return AsyncCheckpointSaver(instance_name=instance_name)


# ---------------------------------------------------------------------------
# Explicit memory tools
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


def get_memory_tools() -> list:
    """Return the list of explicit memory tools."""
    return [get_user_memory, save_user_memory, delete_user_memory]
