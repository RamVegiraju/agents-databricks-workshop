# Databricks Agentic AI Samples

End-to-end samples demonstrating agents with MCP tools and Lakebase memory on Databricks.

## What's Included

| Directory | Description | Deployment |
|-----------|-------------|------------|
| `mcp-server/` | Shared MCP tool server (time, calculator, employee lookup) | Databricks Apps |
| `hello-world-agent/` | Agent with explicit memory tools + MCP integration | Databricks Apps |
| `deep-agents-app/` | Research assistant with subagents, CompositeBackend memory, task planning | Databricks Apps |
| `model-serving-agent/` | Agent with MCP tools + memory on a serving endpoint | Model Serving |

## Prerequisites

- Databricks workspace with **Apps** and **Lakebase** enabled
- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/index.html) installed and authenticated
- Python 3.11+ and [uv](https://docs.astral.sh/uv/)

```bash
# Authenticate — this creates a CLI profile
databricks auth login --host https://<your-workspace-url>
```

Note your **CLI profile name** — you'll need it in Step 0. Run `cat ~/.databrickscfg` to see your profiles. The section name (e.g. `DEFAULT`, `my-workspace`) is what you'll use.

---

## Step 0 — One-Time Configuration

Before deploying anything, configure your workspace details. All commands below assume you're in the **repo root** directory.

### 1. Set CLI profile in all three `databricks.yml` files

Open each file and set `profile:` to your CLI profile name:

- `mcp-server/databricks.yml`
- `hello-world-agent/databricks.yml`
- `deep-agents-app/databricks.yml`

### 2. Create `.env` files from templates

```bash
cp .env.example .env
cp hello-world-agent/.env.example hello-world-agent/.env
cp deep-agents-app/.env.example deep-agents-app/.env
```

Edit each `.env` and set `DATABRICKS_HOST` to your workspace URL (e.g. `https://adb-123456.7.azuredatabricks.net`).

> The other values (`MCP_SERVER_URL`, `APP_URL`) get filled in after deployment — the README tells you when.

---

## Part 1 — Provision Lakebase

Create a shared Lakebase instance for agent memory via the Databricks UI:

1. Go to **Compute > Lakebase** and click **Create**
2. Name it `agent-memory` and wait for it to become active

> If you use a different name, update `instance_name` in `databricks.yml` and `LAKEBASE_INSTANCE_NAME` in `app.yaml` for each agent app.

---

## Part 2 — Deploy the MCP Server

```bash
cd mcp-server
databricks bundle deploy
databricks bundle run mcp_server
cd ..
```

Get the app URL — you'll need it for the agent apps:

```bash
databricks apps get agent-mcp-server --output json | jq -r '.url'
```

**Now update the MCP URL** (append `/mcp` to the URL you just got):

| File | Field to update |
|------|-----------------|
| `hello-world-agent/app.yaml` | `MCP_SERVER_URL` value |
| `deep-agents-app/app.yaml` | `MCP_SERVER_URL` value |

Example: if the URL is `https://agent-mcp-server-123.databricksapps.com`, set the value to `https://agent-mcp-server-123.databricksapps.com/mcp`.

---

## Part 3 — Deploy the Hello World Agent

### 1. Deploy

```bash
cd hello-world-agent
databricks bundle deploy
databricks bundle run hello_world_agent
```

### 2. Grant permissions

Still from `hello-world-agent/`:

```bash
# Initialize Lakebase tables + grant access to the app's service principal
uv run python ../setup_lakebase_permissions.py --app-name agent-hello-world --instance agent-memory

# Grant the app CAN_USE on the MCP server
uv run python ../grant_mcp_permissions.py --agent-app agent-hello-world --mcp-app agent-mcp-server
```

### 3. Test

Get the deployed app URL and add it to your `.env`:

```bash
databricks apps get agent-hello-world --output json | jq -r '.url'
```

Set `APP_URL` in `hello-world-agent/.env` to this URL, then:

```bash
uv run python test_agent.py
```

Or pass it directly: `uv run python test_agent.py --app-url https://<your-app-url>`

Runs three demos:
- **Short-term memory** — conversation context within a thread, lost in a new thread
- **Long-term memory** — user facts saved to Lakebase, recalled across threads, deletable
- **MCP tools** — time, calculator, employee lookup via the shared server

Pick one with `--demo short-term`, `--demo long-term`, or `--demo tools`.

```bash
cd ..
```

---

## Part 4 — Deploy the Deep Agents Research Assistant

### 1. Deploy

```bash
cd deep-agents-app
databricks bundle deploy
databricks bundle run deep_agents_app
```

### 2. Grant permissions

Still from `deep-agents-app/`:

```bash
# --skip-init because tables were already created in Part 3
uv run python ../setup_lakebase_permissions.py --app-name agent-research-assistant --instance agent-memory --skip-init

uv run python ../grant_mcp_permissions.py --agent-app agent-research-assistant --mcp-app agent-mcp-server
```

### 3. Test

Get the deployed app URL:

```bash
databricks apps get agent-research-assistant --output json | jq -r '.url'
```

Set `APP_URL` in `deep-agents-app/.env`, then:

```bash
uv run python test_agent.py
```

Demos: `--demo memory`, `--demo research`, `--demo tools`.

The research demo shows subagent delegation — look for `>> Delegated to subagent: researcher` in the output.

```bash
cd ..
```

---

## Part 5 — Deploy the Model Serving Agent

### 1. Configure

Edit `model-serving-agent/log_and_deploy.py` — update the variables at the top:

```python
CATALOG = "main"                              # Your Unity Catalog
SCHEMA = "agents"                             # Your schema
MCP_SERVER_URL = "https://<your-mcp-url>/mcp" # From Part 2
LAKEBASE_INSTANCE_NAME = "agent-memory"       # From Part 1
```

### 2. Create the UC schema (if it doesn't exist)

From a Databricks notebook or SQL editor:

```sql
CREATE SCHEMA IF NOT EXISTS main.agents;
```

### 3. Upload and run

Upload both `model-serving-agent/agent.py` and `model-serving-agent/log_and_deploy.py` to the same directory in your Databricks workspace. Then from a notebook in that directory:

```python
%pip install -U mlflow databricks-agents databricks-langchain databricks-mcp langgraph nest_asyncio
dbutils.library.restartPython()
%run ./log_and_deploy
```

This logs the agent to MLflow, registers it to Unity Catalog, and deploys to a Model Serving endpoint. Wait for the endpoint to become `READY` (can take a few minutes).

### 4. Test

From your local machine (requires `databricks-sdk` and `requests` installed):

```bash
cd model-serving-agent
python test_endpoint.py
```

Runs three demos:
- **Short-term memory** — conversation context within a thread, lost in a new thread
- **Long-term memory** — user facts saved to Lakebase, recalled across threads, deletable
- **MCP tools** — time, calculator, employee lookup via the shared server

Pick one with `--demo short-term`, `--demo long-term`, or `--demo tools`.

---

## Redeploying After Code Changes

```bash
cd <app-directory>
databricks bundle deploy
databricks bundle run <resource_key>   # hello_world_agent | deep_agents_app | mcp_server
```

`bundle deploy` uploads files. `bundle run` restarts the app. **Both are required.**

---

## Querying the API Directly

Apps require an **OAuth token** (not a PAT):

```bash
TOKEN=$(databricks auth token --host https://<your-workspace-url> | jq -r '.access_token')

curl -X POST <app-url>/invocations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "What time is it?"}],
    "custom_inputs": {"user_id": "alice", "thread_id": "thread-1"}
  }'
```

---

## Configuration Reference

All files you need to edit, and when:

| When | File | What to set |
|------|------|-------------|
| Step 0 | `*/databricks.yml` (×3) | `profile:` → your CLI profile name |
| Step 0 | `*/.env` (×3) | `DATABRICKS_HOST` → workspace URL |
| After Part 2 | `hello-world-agent/app.yaml` | `MCP_SERVER_URL` → MCP app URL + `/mcp` |
| After Part 2 | `deep-agents-app/app.yaml` | `MCP_SERVER_URL` → MCP app URL + `/mcp` |
| After Part 3 | `hello-world-agent/.env` | `APP_URL` → deployed app URL |
| After Part 4 | `deep-agents-app/.env` | `APP_URL` → deployed app URL |
| Before Part 5 | `model-serving-agent/log_and_deploy.py` | `MCP_SERVER_URL`, `CATALOG`, `SCHEMA` |

Default values that work without changes (if you follow the naming in this guide):
- Lakebase instance: `agent-memory`
- Embedding endpoint: `databricks-gte-large-en`
- LLM endpoint: `databricks-claude-opus-4-5`

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `more than one authorization method configured: oauth and pat` | Already handled in `start_server.py` — removes `DATABRICKS_TOKEN` when OAuth creds are present |
| `permission denied for table store` | Re-run `setup_lakebase_permissions.py` for the app |
| `Failed to load MCP tools` | Re-run `grant_mcp_permissions.py` and verify MCP server is running |
| App not updating after deploy | Run `databricks bundle run <key>` after deploy |
| 302 redirect querying API | Use OAuth token, not PAT |
| `Error: Set APP_URL in .env` | Get URL with `databricks apps get <app-name> --output json \| jq -r '.url'` |
| `Error: Set DATABRICKS_HOST` | Add your workspace URL to the `.env` file |
| CLI profile not found | Run `cat ~/.databrickscfg` and update `profile:` in `databricks.yml` |

---

## Cleanup

```bash
cd mcp-server && databricks bundle destroy --auto-approve && cd ..
cd hello-world-agent && databricks bundle destroy --auto-approve && cd ..
cd deep-agents-app && databricks bundle destroy --auto-approve && cd ..

# Model Serving (if deployed)
databricks serving-endpoints delete mcp-agent-serving
```
