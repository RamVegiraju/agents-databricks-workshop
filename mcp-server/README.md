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
├── test_mcp_server.py  # Test script for the deployed server
├── .env.example        # Environment variable template
├── README.md
└── server/
    ├── __init__.py
    ├── app.py           # FastAPI + FastMCP combined application
    ├── main.py          # Uvicorn entrypoint
    ├── tools.py         # MCP tool definitions
    └── utils.py         # Workspace client and header forwarding utilities
```

## Setup

See the [main README](../README.md) for full deployment instructions (Part 2).

Quick version:

```bash
cp .env.example .env       # Edit with your workspace details
databricks bundle deploy
databricks bundle run mcp_server
```

## Testing

After deploying, set `MCP_SERVER_URL` in `.env` to your deployed app URL + `/mcp`, then:

```bash
uv run python test_mcp_server.py
```

Or pass it directly: `uv run python test_mcp_server.py --url https://<your-mcp-app-url>/mcp`

This lists all available tools and calls each one (time, calculator, employee lookup).

## Test Locally

Start the server:

```bash
uv run start-server
```

The server runs on `http://localhost:8000` by default. Verify it's running:

```bash
curl http://localhost:8000/healthz
```
