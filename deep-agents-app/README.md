# Research Assistant — deep-agents Sample

An advanced research assistant that demonstrates the **deep-agents** framework with subagent delegation, composite memory, MCP tool integration, and Lakebase-backed persistence.

## Architecture

```
                          +-----------------------+
                          |    Streamlit Frontend  |
                          |  (multi-user, threads) |
                          +-----------+-----------+
                                      |
                                      v
                          +-----------+-----------+
                          |   MLflow AgentServer   |
                          |   (ResponsesAgent)     |
                          +-----------+-----------+
                                      |
                    +-----------------+-----------------+
                    |                                   |
                    v                                   v
          +---------+---------+               +---------+---------+
          |  MCP Server       |               |  Main Deep Agent  |
          |  (shared tools:   |               |  (orchestrator)   |
          |   time, math,     |               +---------+---------+
          |   employee lookup) |                        |
          +-------------------+          +-------------+-------------+
                                         |                           |
                                         v                           v
                               +---------+---------+       +---------+---------+
                               | Researcher        |       | Fact-Checker      |
                               | Subagent          |       | Subagent          |
                               | (deep-dive        |       | (claim            |
                               |  research)        |       |  verification)    |
                               +-------------------+       +-------------------+

                          +-----------+-----------+
                          |  CompositeBackend      |
                          |  Memory Layer          |
                          +-----------+-----------+
                                      |
                    +-----------------+-----------------+
                    |                                   |
                    v                                   v
          +---------+---------+               +---------+---------+
          | StateBackend      |               | StoreBackend      |
          | (ephemeral,       |               | (/memories/,      |
          |  /scratch/)       |               |  persistent)      |
          +-------------------+               +---------+---------+
                                                        |
                                                        v
                                              +---------+---------+
                                              |     Lakebase      |
                                              | (AsyncCheckpoint- |
                                              |  Saver + Async-   |
                                              |  DatabricksStore) |
                                              +-------------------+
```

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
| **Streamlit frontend** | Multi-user sessions, thread management, suggested prompts |
| **MLflow evaluation** | Custom and built-in scorers for research quality, safety, and structure |

## How Memory Works

The agent uses a three-tier memory architecture via `CompositeBackend`:

### Short-term Memory (AsyncCheckpointSaver)
- **Scope**: Per `thread_id`
- **Lifetime**: Persists across messages within a thread
- **Content**: Full conversation history, intermediate state
- **Backend**: Lakebase via `AsyncCheckpointSaver`

### Long-term Memory (StoreBackend at `/memories/`)
- **Scope**: Per `user_id`
- **Lifetime**: Persists across threads and sessions
- **Content**: User preferences (`/memories/preferences.txt`), key findings (`/memories/findings.txt`)
- **Backend**: Lakebase via `AsyncDatabricksStore` routed through `StoreBackend`

### Ephemeral Memory (StateBackend)
- **Scope**: Current thread only
- **Lifetime**: Lost when thread ends
- **Content**: Scratch notes (`/scratch/notes.txt`), intermediate reasoning
- **Backend**: In-memory via `StateBackend`

### How the Agent Uses Memory

The system prompt instructs the agent to:
1. **Read** from `/memories/` at the start of conversations to personalize responses
2. **Write** user preferences to `/memories/preferences.txt` when the user expresses them
3. **Write** key findings to `/memories/findings.txt` for cross-session reference
4. **Use** `/scratch/` for intermediate notes that don't need to persist

## Context Engineering Patterns

The system prompts follow context engineering best practices:

- **Role definition**: "You are an expert research assistant deployed on Databricks Apps"
- **Capability enumeration**: Numbered list of what the agent can do
- **Guidelines**: Specific behavioral instructions (when to use todo lists, what to save, how to present research)
- **Response format**: Explicit formatting expectations (lead with findings, use bullet points, include Next Steps)
- **Subagent prompts**: Focused, role-specific instructions for each subagent

## Getting Started

### Prerequisites

1. **Deploy the shared MCP server** from `../mcp-server/`
2. **Provision a Lakebase instance** in your Databricks workspace
3. **Configure environment variables** (copy `.env.example` to `.env` and fill in values)

### Local Development

```bash
# Install dependencies
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your values

# Run the agent server
uv run python start_server.py

# In a separate terminal, run the Streamlit frontend
uv run streamlit run streamlit_app.py
```

### Deploy to Databricks Apps

```bash
# Update databricks.yml and app.yaml with your instance names and URLs

# Deploy with Databricks Asset Bundles
databricks bundle deploy --target dev

# Launch the app
databricks bundle run deep_agents_app --target dev
```

### Setup Permissions

1. Ensure the app service principal has access to the Lakebase instance
2. Grant the service principal access to the MCP server app
3. Grant access to the `databricks-claude-opus-4-5` model serving endpoint
4. Grant access to the `databricks-gte-large-en` embedding endpoint

## Running Evaluation

```bash
# Run the evaluation harness
uv run python eval.py
```

The evaluation includes 6 test cases covering:
- **Research quality**: Does the agent produce structured, informative research?
- **Memory save**: Does the agent acknowledge and save user preferences?
- **Memory recall**: Does the agent read from `/memories/` and personalize responses?
- **Fact-checking**: Does the agent delegate to the fact-checker and provide ratings?
- **Safety**: Does the agent handle adversarial prompts safely?
- **Structured output**: Does the agent use headers, bullets, and clear formatting?

Scorers:
- `Safety` — built-in safety scorer
- `Correctness` — checks response against expected output
- `Guidelines("research_quality")` — custom guideline for research depth
- `Guidelines("structured_output")` — custom guideline for formatting
- `response_structure` — custom scorer checking bullets, headers, and error-free output

## Running Streamlit Locally

```bash
uv run streamlit run streamlit_app.py
```

Features:
- **User profiles**: Switch between preset users (Alice, Bob, Carol) or enter a custom ID
- **Thread management**: Create new threads, switch between them, see message counts
- **Suggested prompts**: Quick-start buttons for common research tasks
- **Memory sidebar**: Visual explanation of the three-tier memory architecture

## How to Extend

### Adding a New Subagent

Add a new entry to the `SUBAGENTS` list in `agent.py`:

```python
SUBAGENTS = [
    # ... existing subagents ...
    {
        "name": "summarizer",
        "description": "A summarization specialist that condenses long documents...",
        "prompt": "You are a summarization specialist. Your job is to...",
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

Extend the `CompositeBackend` routes to add new persistent paths:

```python
backend=lambda rt: CompositeBackend(
    default=StateBackend(rt),
    routes={
        "/memories/": StoreBackend(rt),
        "/shared/": StoreBackend(rt),  # new shared memory path
    },
),
```

Update the system prompt to instruct the agent on when and how to use the new path.
