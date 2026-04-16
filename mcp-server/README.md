# Shared MCP Server

A standalone Databricks App that hosts MCP (Model Context Protocol) tools consumed by both the `hello-world-agent` and `deep-agents-app` samples. Built with FastAPI and FastMCP.

## Tools

| Tool | Description |
|------|-------------|
| `get_current_time` | Returns the current date and time in UTC |
| `calculator` | Evaluates a mathematical expression (supports `+`, `-`, `*`, `/`, `**`, `()`) |
| `lookup_employee` | Looks up an employee profile from a sample company directory (Alice, Bob, Carol) |

## Project Structure

```
mcp-server/
├── app.yaml            # Databricks App launch command
├── databricks.yml      # Databricks Asset Bundle config
├── pyproject.toml      # Python project metadata and dependencies
├── README.md
└── server/
    ├── __init__.py
    ├── app.py           # FastAPI + FastMCP combined application
    ├── main.py          # Uvicorn entrypoint
    ├── tools.py         # MCP tool definitions
    └── utils.py         # Workspace client and header forwarding utilities
```

## Deploy to Databricks

```bash
databricks bundle deploy && databricks bundle run mcp_server
```

After deploying, note the app URL (e.g. `https://<workspace>.databricks.com/apps/agent-mcp-server`). Both agent samples need this as their `MCP_SERVER_URL` environment variable.

## Test Locally

Start the server:

```bash
uv run start-server
```

The server runs on `http://localhost:8000` by default. You can specify a different port with `--port`.

To verify the server is running:

```bash
curl http://localhost:8000/healthz
```

To test the MCP tools, use the `test_local.py` pattern from the agent samples, pointing at `http://localhost:8000/mcp/`.
