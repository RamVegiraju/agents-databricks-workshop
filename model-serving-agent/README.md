# Model Serving Agent

Deploys a LangGraph ReAct agent to **Databricks Model Serving** using the ResponsesAgent interface. Consumes the same shared MCP server tools and Lakebase instance as the other agent samples.

## How It Differs from the App-Based Agents

| Aspect | Model Serving (this sample) | Databricks Apps (hello-world / deep-agents) |
|--------|----------------------------|---------------------------------------------|
| **Deployment** | `agents.deploy()` to a serving endpoint | `databricks bundle deploy` + `bundle run` |
| **Scaling** | Auto-scaling with scale-to-zero | Fixed app compute |
| **Frontend** | API-only (REST endpoint, AI Playground) | Streamlit UI included |
| **Memory** | Same Lakebase (short-term + long-term) | Same Lakebase (short-term + long-term) |
| **Interface** | `ResponsesAgent` class with `predict`/`predict_stream` | `@invoke`/`@stream` decorators on AgentServer |
| **Agent creation** | Per-request (checkpointer needs fresh connection) | Per-request (same pattern) |
| **Best for** | Production API endpoints, AI Playground | Interactive apps with Streamlit UI |

## Memory Architecture

Both short-term and long-term memory use the same shared Lakebase instance:

- **Short-term** (`AsyncCheckpointSaver`): Conversation history per `thread_id`. Pass the same `thread_id` across requests to maintain context.
- **Long-term** (`AsyncDatabricksStore`): User facts per `user_id` via explicit memory tools (`get_user_memory`, `save_user_memory`, `delete_user_memory`). Uses semantic search (pgvector + embeddings).

Memory is passed via `custom_inputs` in the request:

```json
{
  "input": [{"role": "user", "content": "Remember my name is Alice"}],
  "custom_inputs": {"user_id": "alice@example.com", "thread_id": "session-1"}
}
```

## Files

| File | Purpose |
|------|---------|
| `agent.py` | Agent code — LangGraph + MCP tools + memory tools + ResponsesAgent wrapper |
| `log_and_deploy.py` | Log to MLflow, register to Unity Catalog, deploy to endpoint |
| `test_endpoint.py` | Test the deployed endpoint (non-streaming + streaming) |

## Prerequisites

- MCP server deployed and running (see `../mcp-server/`)
- Lakebase instance provisioned with tables initialized (see root `provision_lakebase.py` and `setup_lakebase_permissions.py`)
- Unity Catalog catalog and schema created
- Databricks workspace with Model Serving enabled

## Deploy

### Step 1: Create the catalog and schema (if needed)

From a Databricks notebook or SQL editor:

```sql
CREATE CATALOG IF NOT EXISTS main;
CREATE SCHEMA IF NOT EXISTS main.agents;
```

### Step 2: Update configuration

Edit `log_and_deploy.py` and set your values:

```python
CATALOG = "main"
SCHEMA = "agents"
MCP_SERVER_URL = "https://<your-mcp-app-url>/mcp"
LAKEBASE_INSTANCE_NAME = "agent-memory"
```

### Step 3: Log, register, and deploy

From a Databricks notebook with the required packages:

```python
%pip install -U mlflow databricks-agents databricks-langchain[memory] databricks-mcp langgraph nest_asyncio
dbutils.library.restartPython()
```

Then run:

```python
%run ./log_and_deploy
```

Deployment takes ~15 minutes. The script polls until the endpoint is READY.

### Step 4: Test the endpoint

```bash
python test_endpoint.py                    # Run all demos
python test_endpoint.py --demo short-term  # Short-term memory only
python test_endpoint.py --demo long-term   # Long-term memory only
python test_endpoint.py --demo tools       # MCP tools only
```

Demos cover short-term memory (conversation context within a thread), long-term memory (user facts that persist across threads), and MCP tool usage.

## Configuration

Update these values in `log_and_deploy.py` before running:

| Variable | Default | Description |
|----------|---------|-------------|
| `CATALOG` | `main` | Unity Catalog name |
| `SCHEMA` | `agents` | Schema name |
| `MODEL_NAME` | `mcp_agent` | Model name in UC |
| `ENDPOINT_NAME` | `mcp-agent-serving` | Serving endpoint name |
| `MODEL_ENDPOINT` | `databricks-claude-opus-4-5` | Foundation model endpoint |
| `MCP_SERVER_URL` | (your MCP app URL) | URL to the deployed MCP server |
| `LAKEBASE_INSTANCE_NAME` | `agent-memory` | Lakebase instance for memory |
| `EMBEDDING_ENDPOINT` | `databricks-gte-large-en` | Embedding model for semantic search |
| `EMBEDDING_DIMS` | `1024` | Embedding dimensions |
