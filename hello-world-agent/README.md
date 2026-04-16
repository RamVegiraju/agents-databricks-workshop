# Hello World Agent

A basic introductory agent that demonstrates core Databricks agentic patterns: consuming MCP tools from a deployed server, explicit long-term memory tools backed by Lakebase, short-term conversation memory via checkpointing, and deployment as a Databricks App using DABs.

## What This Demonstrates

- **MCP tool consumption** -- connects to an MCP server deployed as a separate Databricks App and loads its tools (calculator, time, employee lookup) at runtime.
- **Explicit memory tools** -- `get_user_memory`, `save_user_memory`, and `delete_user_memory` give the agent read/write/delete access to per-user long-term memory stored in Lakebase.
- **Short-term conversation memory** -- `AsyncCheckpointSaver` persists conversation state per `thread_id`, so the agent remembers earlier messages in the same thread.
- **MLflow ResponsesAgent** -- the agent is wrapped in an MLflow `ResponsesAgent` with `@invoke` and `@stream` handlers served by `AgentServer`.
- **MLflow GenAI evaluation** -- a simple eval harness with Safety, Correctness, and Guidelines scorers.
- **DABs deployment** -- `databricks.yml` and `app.yaml` for one-command deployment.

## Architecture

```
MCP Server App          Agent App (this)            Lakebase
(tools: calc,      -->  LangGraph ReAct Agent   --> AsyncDatabricksStore  (long-term memory)
 time, employee)        + ChatDatabricks            AsyncCheckpointSaver  (short-term memory)
                        + Memory Tools
                        + AgentServer
```

## Project Structure

```
hello-world-agent/
  agent/
    __init__.py          # Package marker
    memory.py            # Memory tools + factory functions
    agent.py             # Agent construction (init_agent)
    server.py            # MLflow ResponsesAgent handlers
  start_server.py        # AgentServer entrypoint
  test_agent.py          # Test script with memory + tools demos
  eval.py                # MLflow GenAI evaluation harness
  pyproject.toml         # Python project config
  app.yaml               # Databricks App config
  databricks.yml         # DABs bundle config
  .env.example           # Environment variable template
```

## How Memory Works

### Short-term memory (conversation context)

Backed by `AsyncCheckpointSaver`. Keyed by `thread_id`. The agent remembers what was said earlier in the same conversation thread. Changing the thread ID starts a fresh conversation.

### Long-term memory (user facts)

Backed by `AsyncDatabricksStore` with embedding-based search. Keyed by `user_id`. The agent uses three explicit tools:

| Tool | Purpose |
|------|---------|
| `get_user_memory` | Search stored facts about the user |
| `save_user_memory` | Persist a key-value fact |
| `delete_user_memory` | Remove a stored fact |

Memories persist across conversations and threads for the same user.

## Setup

See the [main README](../README.md) for full deployment instructions (Part 3).

Quick version:

```bash
cp .env.example .env       # Edit with your workspace details
databricks bundle deploy
databricks bundle run hello_world_agent

# Grant permissions (from this directory)
uv run python ../setup_lakebase_permissions.py --app-name agent-hello-world --instance agent-memory
uv run python ../grant_mcp_permissions.py --agent-app agent-hello-world --mcp-app agent-mcp-server
```

## Testing

```bash
uv run python test_agent.py                  # Run all demos
uv run python test_agent.py --demo short-term  # Short-term memory only
uv run python test_agent.py --demo long-term   # Long-term memory only
uv run python test_agent.py --demo tools       # MCP tools only
```

## Running Evaluation

```bash
uv run python eval.py
```

Runs 5 test cases covering memory operations, tool usage, and safety.
