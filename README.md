# Databricks Agentic AI Samples

End-to-end samples demonstrating the modern agentic stack on Databricks Apps.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Databricks Apps                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  MCP Server  │  │  Hello World │  │  Deep Agents     │  │
│  │  (shared)    │◄─│  Agent       │  │  Research Asst   │  │
│  │              │◄─│              │  │                  │  │
│  └──────────────┘  └──────┬───────┘  └────────┬─────────┘  │
│                           │                    │            │
│                    ┌──────▼────────────────────▼─────┐      │
│                    │         Lakebase (Postgres)     │      │
│                    │  Short-term: AsyncCheckpointSaver│      │
│                    │  Long-term:  AsyncDatabricksStore│      │
│                    └────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## What's Included

| Directory | Description | Complexity |
|-----------|-------------|------------|
| `mcp-server/` | Shared MCP tool server (time, calculator, employee lookup) | Setup |
| `hello-world-agent/` | Basic agent with explicit memory tools, MCP integration | Introductory |
| `deep-agents-app/` | Research assistant with subagents, CompositeBackend memory, task planning | Advanced |

## Concepts Demonstrated

| Concept | hello-world-agent | deep-agents-app |
|---------|-------------------|-----------------|
| **MCP Tools** | Consumed from shared server | Consumed from shared server |
| **Short-term Memory** | `AsyncCheckpointSaver` (per thread) | `AsyncCheckpointSaver` (per thread) |
| **Long-term Memory** | Explicit tools (`get/save/delete_user_memory`) with semantic search | `CompositeBackend` routing `/memories/` to `StoreBackend` |
| **System Prompts** | Role, capabilities, guidelines | Role, capabilities, guidelines, response format |
| **Subagents** | - | Researcher + Fact-checker via `SubAgentMiddleware` |
| **Task Planning** | - | `TodoListMiddleware` for multi-step research |
| **Serving** | MLflow AgentServer (`@invoke`/`@stream`) | MLflow AgentServer (`@invoke`/`@stream`) |
| **Frontend** | Streamlit chat UI | Streamlit chat UI with multi-user presets |
| **Evaluation** | MLflow GenAI (Safety, Correctness, Guidelines) | MLflow GenAI + custom `response_structure` scorer |

---

## Prerequisites

Before deploying any sample, ensure you have:

- Databricks workspace with **Apps enabled**
- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/index.html) installed and configured (`databricks auth login`)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

---

## Part 1: Provision Lakebase

Both agent samples use Lakebase (managed PostgreSQL) for memory. Create a shared instance first.

### Step 1: Install dependencies

```bash
pip install databricks-sdk python-dotenv
```

### Step 2: Set environment variables

```bash
export DATABRICKS_HOST=https://<your-workspace>.cloud.databricks.com
export DATABRICKS_TOKEN=<your-pat-token>
```

### Step 3: Create the Lakebase instance

```bash
python provision_lakebase.py --name agent-memory
```

This takes a few minutes. When complete, note the instance name (`agent-memory`) — you'll use it in every subsequent step.

### Step 4: Initialize tables

The tables are created when you run `setup_lakebase_permissions.py` later (after deploying each app). No action needed here yet.

---

## Part 2: Deploy the MCP Server

The MCP server hosts shared tools (time, calculator, employee lookup) consumed by both agent apps.

### Step 1: Navigate to the MCP server directory

```bash
cd mcp-server
```

### Step 2: Deploy and start the app

```bash
databricks bundle deploy
databricks bundle run mcp_server
```

### Step 3: Get the app URL

```bash
databricks apps get agent-mcp-server --output json | jq -r '.url'
```

Save this URL — both agent apps need it. The MCP endpoint will be `<app-url>/mcp`.

### Step 4: Verify it's running

```bash
databricks apps logs agent-mcp-server
```

Look for `App started successfully` in the logs.

---

## Part 3: Deploy the Hello World Agent

A basic agent demonstrating MCP tool consumption, explicit long-term memory tools with semantic search, and short-term conversation memory.

### Step 1: Navigate to the hello-world directory

```bash
cd hello-world-agent
```

### Step 2: Configure your Lakebase instance name

Update `databricks.yml` — replace `<your-lakebase-instance-name>` with your instance name (e.g., `agent-memory`):

```yaml
resources:
  apps:
    hello_world_agent:
      name: "agent-hello-world"
      ...
      resources:
        - name: "database"
          database:
            instance_name: "agent-memory"  # <-- your instance name
```

Update `app.yaml` — replace the placeholder values:

```yaml
env:
  - name: MCP_SERVER_URL
    value: "https://<your-mcp-app-url>/mcp"  # <-- from Part 2
  - name: LAKEBASE_INSTANCE_NAME
    value: "agent-memory"  # <-- your instance name
```

### Step 3: Create a local `.env` file (for local development)

```bash
cp .env.example .env
# Edit .env with your values:
#   DATABRICKS_HOST=https://<workspace>.cloud.databricks.com
#   DATABRICKS_TOKEN=<your-token>
#   MCP_SERVER_URL=https://<mcp-app-url>/mcp
#   LAKEBASE_INSTANCE_NAME=agent-memory
```

### Step 4: Deploy and start the app

```bash
databricks bundle deploy
databricks bundle run hello_world_agent
```

### Step 5: Grant Lakebase permissions to the app's service principal

Go back to the repo root and run:

```bash
cd ..
python setup_lakebase_permissions.py \
  --app-name agent-hello-world \
  --instance agent-memory
```

This does three things:
1. Looks up the app's service principal
2. Creates the store and checkpoint tables (if not already created)
3. Grants the SP read/write access to those tables

### Step 6: Verify the deployment

Get the app URL:
```bash
databricks apps get agent-hello-world --output json | jq -r '.url'
```

Open the URL in your browser to access the Streamlit chat UI. Try:
- "What time is it?" (tests MCP tool)
- "Remember my name is Alice" (tests long-term memory save)
- Switch to a new thread, then ask "What do you know about me?" (tests cross-thread memory retrieval)

### Step 7: Run evaluation (optional)

```bash
cd hello-world-agent
uv run python eval.py
```

---

## Part 4: Deploy the Deep Agents Research Assistant

An advanced agent with subagent delegation (researcher, fact-checker), CompositeBackend memory (ephemeral + persistent), task planning, and MCP tools.

### Step 1: Navigate to the deep-agents directory

```bash
cd deep-agents-app
```

### Step 2: Configure your Lakebase instance name

Update `databricks.yml` — replace `<your-lakebase-instance-name>`:

```yaml
resources:
  apps:
    deep_agents_app:
      name: "agent-research-assistant"
      ...
      resources:
        - name: "database"
          database:
            instance_name: "agent-memory"  # <-- your instance name
```

Update `app.yaml` — replace the placeholder values:

```yaml
env:
  - name: MCP_SERVER_URL
    value: "https://<your-mcp-app-url>/mcp"  # <-- from Part 2
  - name: LAKEBASE_INSTANCE_NAME
    value: "agent-memory"  # <-- your instance name
```

### Step 3: Create a local `.env` file (for local development)

```bash
cp .env.example .env
# Edit .env with your values (same as hello-world)
```

### Step 4: Deploy and start the app

```bash
databricks bundle deploy
databricks bundle run deep_agents_app
```

### Step 5: Grant Lakebase permissions to the app's service principal

```bash
cd ..
python setup_lakebase_permissions.py \
  --app-name agent-research-assistant \
  --instance agent-memory \
  --skip-init  # Tables already created in Part 3
```

> **Note:** Use `--skip-init` if you already initialized tables when deploying the hello-world agent. Both apps share the same Lakebase tables.

### Step 6: Verify the deployment

Get the app URL:
```bash
databricks apps get agent-research-assistant --output json | jq -r '.url'
```

Open the Streamlit UI. Try:
- "Research the benefits of lakehouse architecture" (tests researcher subagent)
- "Fact-check: Delta Lake supports ACID transactions" (tests fact-checker subagent)
- "Remember I prefer bullet-point summaries" (tests long-term memory at `/memories/`)
- Switch users in the sidebar to verify memory isolation

### Step 7: Run evaluation (optional)

```bash
cd deep-agents-app
uv run python eval.py
```

---

## Redeploying After Code Changes

When you make changes to any app, redeploy with the same two commands:

```bash
cd <app-directory>
databricks bundle deploy    # Syncs updated files to the workspace
databricks bundle run <resource_key>  # Restarts the app with new code
```

| App | Directory | Resource Key |
|-----|-----------|-------------|
| MCP Server | `mcp-server/` | `mcp_server` |
| Hello World Agent | `hello-world-agent/` | `hello_world_agent` |
| Deep Agents Research Assistant | `deep-agents-app/` | `deep_agents_app` |

> **Important:** `bundle deploy` uploads files but does **not** restart the app. You must also run `bundle run` or the app continues running old code.

No need to re-run `setup_lakebase_permissions.py` — permissions persist across redeployments.

---

## Querying the Agent API Directly

Both agents expose an API at `<app-url>/invocations`. You **must** use an OAuth token (not a PAT):

```bash
# Get OAuth token
TOKEN=$(databricks auth token | jq -r '.access_token')

# Query the agent
curl -X POST <app-url>/invocations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "What time is it?"}],
    "custom_inputs": {"user_id": "user@example.com", "thread_id": "my-thread"}
  }'
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Failed to connect to Lakebase` | Verify `LAKEBASE_INSTANCE_NAME` in `app.yaml` matches your instance |
| `permission denied for table store` | Re-run `setup_lakebase_permissions.py` for the app |
| `Could not load MCP tools` | Verify `MCP_SERVER_URL` in `app.yaml` and that the MCP server app is running |
| App not updating after deploy | Run `databricks bundle run <resource_key>` — deploy alone doesn't restart |
| 302 redirect when querying API | Use OAuth token (`databricks auth token`), not a PAT |
| App logs show import errors | Check `databricks apps logs <app-name>` for missing dependencies |

---

## Cleanup

To tear down all resources:

```bash
# Destroy apps (in any order)
cd mcp-server && databricks bundle destroy --auto-approve
cd hello-world-agent && databricks bundle destroy --auto-approve
cd deep-agents-app && databricks bundle destroy --auto-approve

# Delete Lakebase instance (optional — via Databricks UI)
# Navigate to Compute > Lakebase > Delete instance
```
