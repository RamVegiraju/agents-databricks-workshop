# Hello World Agent

A basic introductory agent that demonstrates core Databricks agentic patterns: consuming MCP tools from a deployed server, explicit long-term memory tools backed by Lakebase, short-term conversation memory via checkpointing, and deployment as a Databricks App using DABs.

## What This Demonstrates

- **MCP tool consumption** -- connects to an MCP server deployed as a separate Databricks App and loads its tools (calculator, time, employee lookup) at runtime.
- **Explicit memory tools** -- `get_user_memory`, `save_user_memory`, and `delete_user_memory` give the agent read/write/delete access to per-user long-term memory stored in Lakebase.
- **Short-term conversation memory** -- `AsyncCheckpointSaver` persists conversation state per `thread_id`, so the agent remembers earlier messages in the same thread.
- **MLflow ResponsesAgent** -- the agent is wrapped in an MLflow `ResponsesAgent` with `@invoke` and `@stream` handlers served by `AgentServer`.
- **Streamlit frontend** -- a chat UI with user/thread ID inputs demonstrating session isolation.
- **MLflow GenAI evaluation** -- a simple eval harness with Safety, Correctness, and Guidelines scorers.
- **DABs deployment** -- `databricks.yml` and `app.yaml` for one-command deployment.

## Architecture

```
MCP Server App          Agent App (this)            Lakebase
(tools: calc,      -->  LangGraph ReAct Agent   --> AsyncDatabricksStore  (long-term memory)
 time, employee)        + ChatDatabricks            AsyncCheckpointSaver  (short-term memory)
                        + Memory Tools
                        + AgentServer / Streamlit
```

## Prerequisites

1. A Databricks workspace with Foundation Model APIs enabled.
2. An MCP server deployed as a Databricks App (provides `get_current_time`, `calculator`, `lookup_employee` tools).
3. A provisioned Lakebase instance for memory storage.
4. Python 3.11+ and `uv` (or `pip`).

## Getting Started

### 1. Deploy the MCP server

Deploy the shared MCP server app first (see the `mcp-server/` sample in this repo). Note its URL.

### 2. Provision Lakebase

Create a Lakebase instance in your workspace. Note the instance name.

### 3. Configure environment

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
# Edit .env with your values
```

Update `app.yaml` and `databricks.yml` with your Lakebase instance name and MCP server URL.

### 4. Deploy the agent

```bash
databricks bundle deploy -t dev
databricks bundle run -t dev hello_world_agent
```

### 5. Set up permissions

Grant the app's service principal `CAN_QUERY` on the MCP server app and `CAN_CONNECT_AND_CREATE` on the Lakebase instance.

### 6. Test

Open the deployed app URL in your browser. Try:
- "Remember my name is Alice"
- "What do you know about me?"
- "What time is it?"
- "Calculate 123 * 456"

## Project Structure

```
hello-world-agent/
  agent/
    __init__.py          # Package marker
    memory.py            # Memory tools + factory functions
    agent.py             # Agent construction (init_agent)
    server.py            # MLflow ResponsesAgent handlers
  start_server.py        # AgentServer entrypoint
  streamlit_app.py       # Streamlit chat frontend
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

## Running Evaluation

```bash
# From the hello-world-agent directory
uv run python eval.py
```

This runs 5 test cases covering memory operations, tool usage, and safety, scoring with MLflow's Safety, Correctness, and Guidelines scorers.

## Running Streamlit Locally

```bash
# From the hello-world-agent directory
uv run streamlit run streamlit_app.py
```

Make sure your `.env` file is configured with valid credentials and URLs.
