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
- Python 3.11+
- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/index.html)
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### macOS / Linux

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Databricks CLI
brew install databricks/tap/databricks   # macOS (Homebrew)
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh  # Linux

# Install root Python dependencies
pip install -r requirements.txt

# Verify installations
python --version        # Should be 3.11+
uv --version
databricks --version
```

### Windows (PowerShell)

```powershell
# Install uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install Databricks CLI
winget install Databricks.DatabricksCLI

# Install root Python dependencies
pip install -r requirements.txt

# Verify installations
python --version        # Should be 3.11+
uv --version
databricks --version
```

### Authenticate

See **Step 0** below for full authentication and profile setup instructions.

---

## Step 0 — One-Time Configuration

Before deploying anything, configure your workspace details. All commands below assume you're in the **repo root** directory.

### 1. Authenticate with the Databricks CLI

```bash
databricks auth login --host https://<your-workspace-url>
```

When prompted for a profile name, either press Enter to accept the default or type a custom name. **Note the profile name** — you'll need it next.

To verify your profiles at any time:

```bash
# macOS/Linux
cat ~/.databrickscfg

# Windows
type %USERPROFILE%\.databrickscfg
```

Each `[section-name]` is a profile. For example:

```ini
[DEFAULT]
host  = https://adb-1234567.11.azuredatabricks.net
token = dapiXXXXXXXX

[adb-1234567]
host      = https://adb-1234567.11.azuredatabricks.net
auth_type = databricks-cli
```

### 2. Set CLI profile in all three `databricks.yml` files

Each app has a `databricks.yml` with a `profile` field that tells `databricks bundle` which workspace to deploy to. By default this is set to `DEFAULT`. **If your profile has a different name, update it in all three files:**

- `mcp-server/databricks.yml`
- `hello-world-agent/databricks.yml`
- `deep-agents-app/databricks.yml`

The line to change in each file:

```yaml
targets:
  dev:
    workspace:
      profile: DEFAULT  # ← Change this to your profile name from step 1
```

> If you used the default profile name during `databricks auth login` and it saved as `DEFAULT`, no changes are needed.

### 3. Create `.env` files from templates

```bash
cp .env.example .env
cp mcp-server/.env.example mcp-server/.env
cp hello-world-agent/.env.example hello-world-agent/.env
cp deep-agents-app/.env.example deep-agents-app/.env
```

Edit each `.env` and set `DATABRICKS_HOST` to your workspace URL (e.g. `https://adb-123456789.11.azuredatabricks.net`).

> The other values (`MCP_SERVER_URL`, `APP_URL`) get filled in after deployment — the README tells you when.

---

## Part 1 — Provision Lakebase

Create a shared Lakebase instance for agent memory. This provides PostgreSQL-backed storage for both short-term memory (conversation checkpoints per thread) and long-term memory (user facts with semantic search via pgvector).

**Option A — Via the Databricks UI:**

1. Go to **Compute > Lakebase** and click **Create**
2. Name it `agent-memory` and wait for it to become active

**Option B — Via the CLI script:**

```bash
# Requires DATABRICKS_HOST in .env (set in Step 0) and CLI auth configured
python provision_lakebase.py
```

This creates an instance named `agent-memory` with default settings (`CU_1` capacity). Customize with `--name`, `--capacity CU_2`, or `--retention 14`.

> If you use a name other than `agent-memory`, update `instance_name` in `databricks.yml` and `LAKEBASE_INSTANCE_NAME` in `app.yaml` for each agent app.

---

## Part 2 — Deploy the MCP Server

The MCP (Model Context Protocol) server is a **shared tool server** that all agents connect to. It exposes utility tools — time, calculator, and employee lookup — over a standardized protocol. Instead of each agent implementing its own tools, they all call the same MCP server, keeping tool logic centralized and reusable.

The server runs as a Databricks App and exposes an `/mcp` endpoint that agents connect to at runtime using `DatabricksMCPServer`.

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
| `mcp-server/.env` | `MCP_SERVER_URL` value |
| `hello-world-agent/app.yaml` | `MCP_SERVER_URL` value |
| `deep-agents-app/app.yaml` | `MCP_SERVER_URL` value |

Example: if the URL is `https://agent-mcp-server-123.databricksapps.com`, set the value to `https://agent-mcp-server-123.databricksapps.com/mcp`.

### Test the MCP server

Verify the tools are working before moving on:

```bash
cd mcp-server
uv run python test_mcp_server.py
cd ..
```

This lists the available tools and calls each one (time, calculator, employee lookup). You can also pass `--url` directly: `uv run python test_mcp_server.py --url https://<your-mcp-app-url>/mcp`.

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
cd ..
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
| Step 0 | `*/.env` (×4) | `DATABRICKS_HOST` → workspace URL |
| After Part 2 | `mcp-server/.env` | `MCP_SERVER_URL` → MCP app URL + `/mcp` |
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
| CLI profile not found | Run `cat ~/.databrickscfg` to see available profiles, then update `profile:` in all three `databricks.yml` files (see Step 0) |
| `401 Unauthorized` on `bundle deploy` | Your token expired or `profile:` in `databricks.yml` points to the wrong profile. Re-run `databricks auth login` and verify the profile name matches |

---

## Resources

- [Agents on Databricks Apps (YouTube playlist)](https://www.youtube.com/watch?v=ynwq6QIzQqg&list=PLThJtS7RDkOe18wsscifG80moTZIck-EM)
- [Agents on Model Serving (YouTube)](https://www.youtube.com/watch?v=bFE29k9tBRI&list=PLThJtS7RDkOe18wsscifG80moTZIck-EM&index=8)
- [Custom Agents Documentation](https://docs.databricks.com/aws/en/generative-ai/agent-framework/author-agent)

---

## Cleanup

```bash
cd mcp-server && databricks bundle destroy --auto-approve && cd ..
cd hello-world-agent && databricks bundle destroy --auto-approve && cd ..
cd deep-agents-app && databricks bundle destroy --auto-approve && cd ..

# Model Serving (if deployed)
databricks serving-endpoints delete mcp-agent-serving
```
