# Research Assistant — deep-agents Sample

An advanced research assistant that demonstrates the **deep-agents** framework with subagent delegation, composite memory, MCP tool integration, and Lakebase-backed persistence.

## What This Demonstrates

| Feature | Implementation |
|---------|---------------|
| **deep-agents framework** | `create_deep_agent` with model, instructions, subagents, tools, and backend |
| **Subagent delegation** | Researcher subagent for deep-dive research; Fact-checker subagent for claim verification |
| **Context engineering** | Detailed system prompts with role, capabilities, guidelines, and response format |
| **CompositeBackend memory** | `StateBackend` for ephemeral scratch space + `StoreBackend` for persistent `/memories/` |
| **MCP tool integration** | Shared MCP server for utility tools (time, math, employee lookups) |
| **Lakebase persistence** | `AsyncCheckpointSaver` for conversation history + `AsyncDatabricksStore` for long-term memory |
| **TodoListMiddleware** | Multi-step task planning for complex research queries |
| **MLflow ResponsesAgent** | `@invoke` and `@stream` handlers with tracing |
| **MLflow evaluation** | Custom and built-in scorers for research quality, safety, and structure |

## Architecture

```
                      +---------------------+
                      |  MLflow AgentServer  |
                      |  (ResponsesAgent)    |
                      +---------+-----------+
                                |
                  +-------------+-------------+
                  |                           |
                  v                           v
        +---------+---------+       +---------+---------+
        |  MCP Server       |       |  Main Deep Agent  |
        |  (shared tools:   |       |  (orchestrator)   |
        |   time, math,     |       +---------+---------+
        |   employee lookup) |                |
        +-------------------+    +-----------+-----------+
                                 |                       |
                                 v                       v
                       +---------+-------+     +---------+-------+
                       | Researcher      |     | Fact-Checker    |
                       | Subagent        |     | Subagent        |
                       +-----------------+     +-----------------+

                      +---------------------+
                      |  CompositeBackend    |
                      +---------+-----------+
                                |
                  +-------------+-------------+
                  |                           |
                  v                           v
        +---------+---------+       +---------+---------+
        | StateBackend      |       | StoreBackend      |
        | (ephemeral,       |       | (/memories/,      |
        |  /scratch/)       |       |  persistent)      |
        +-------------------+       +---------+---------+
                                              |
                                              v
                                    +---------+---------+
                                    |     Lakebase      |
                                    +-------------------+
```

## How Memory Works

The agent uses a three-tier memory architecture via `CompositeBackend`:

| Tier | Backend | Scope | Lifetime | Example |
|------|---------|-------|----------|---------|
| **Short-term** | AsyncCheckpointSaver | Per `thread_id` | Within a thread | Conversation history |
| **Long-term** | StoreBackend at `/memories/` | Per `user_id` | Across threads/sessions | User preferences, findings |
| **Ephemeral** | StateBackend at `/scratch/` | Current thread | Lost when thread ends | Intermediate reasoning |

## Project Structure

```
deep-agents-app/
  agent.py               # Agent: deep-agents + subagents + CompositeBackend
  start_server.py        # AgentServer entrypoint
  test_agent.py          # Test script with memory, research, tools demos
  eval.py                # MLflow GenAI evaluation harness
  pyproject.toml         # Python project config
  app.yaml               # Databricks App config
  databricks.yml         # DABs bundle config
  .env.example           # Environment variable template
```

## Setup

See the [main README](../README.md) for full deployment instructions (Part 4).

Quick version:

```bash
cp .env.example .env       # Edit with your workspace details
databricks bundle deploy
databricks bundle run deep_agents_app

# Grant permissions (from this directory)
uv run python ../setup_lakebase_permissions.py --app-name agent-research-assistant --instance agent-memory --skip-init
uv run python ../grant_mcp_permissions.py --agent-app agent-research-assistant --mcp-app agent-mcp-server
```

## Testing

```bash
uv run python test_agent.py                # Run all demos
uv run python test_agent.py --demo memory    # Long-term memory persistence
uv run python test_agent.py --demo research  # Subagent delegation
uv run python test_agent.py --demo tools     # MCP tools
```

The research demo shows subagent delegation — look for `>> Delegated to subagent: researcher` in the output.

## Running Evaluation

```bash
uv run python eval.py
```

6 test cases covering research quality, memory operations, fact-checking, safety, and structured output.

## How to Extend

### Adding a New Subagent

Add a new entry to the `SUBAGENTS` list in `agent.py`:

```python
SUBAGENTS = [
    # ... existing subagents ...
    {
        "name": "summarizer",
        "description": "A summarization specialist that condenses long documents...",
        "system_prompt": "You are a summarization specialist. Your job is to...",
    },
]
```

### Adding Custom Tools

Add tools alongside MCP tools in the `_build_agent` function:

```python
from langchain_core.tools import tool

@tool
def my_custom_tool(query: str) -> str:
    """Description of what this tool does."""
    return "result"

agent = create_deep_agent(
    ...
    tools=mcp_tools + [my_custom_tool],
    ...
)
```

### Adding New Memory Paths

Extend the `CompositeBackend` routes:

```python
backend=lambda rt: CompositeBackend(
    default=StateBackend(rt),
    routes={
        "/memories/": StoreBackend(rt),
        "/shared/": StoreBackend(rt),  # new persistent path
    },
),
```

Update the system prompt to instruct the agent on when to use the new path.
