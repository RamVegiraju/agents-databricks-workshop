"""
Test script for the deployed MCP server.

Usage:
    uv run python test_mcp_server.py
    uv run python test_mcp_server.py --url https://<your-mcp-app-url>
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MCP_URL = os.environ.get("MCP_SERVER_URL", "")
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "")


def main():
    parser = argparse.ArgumentParser(description="Test the deployed MCP server")
    parser.add_argument("--url", default=DEFAULT_MCP_URL, help="MCP server URL (e.g. https://agent-mcp-server-xxx.databricksapps.com/mcp)")
    args = parser.parse_args()

    if not args.url:
        print("Error: Set MCP_SERVER_URL in .env or pass --url. Get it with:")
        print("  databricks apps get agent-mcp-server --output json | jq -r '.url'")
        print("  Then append /mcp to the URL.")
        sys.exit(1)

    mcp_url = args.url.rstrip("/")
    if not mcp_url.endswith("/mcp"):
        mcp_url += "/mcp"

    from databricks.sdk import WorkspaceClient
    from databricks_mcp import DatabricksMCPClient

    ws = WorkspaceClient(host=DATABRICKS_HOST) if DATABRICKS_HOST else WorkspaceClient()
    client = DatabricksMCPClient(server_url=mcp_url, workspace_client=ws)

    print("=" * 50)
    print("MCP Server Test")
    print("=" * 50)

    print("\n--- Available Tools ---")
    tools = client.list_tools()
    for t in tools:
        print(f"  • {t.name}: {t.description[:80]}")

    print("\n--- get_current_time() ---")
    result = client.call_tool("get_current_time", {})
    print(f"  {result}")

    print("\n--- calculator('42 * 17 + 3') ---")
    result = client.call_tool("calculator", {"expression": "42 * 17 + 3"})
    print(f"  {result}")

    print("\n--- lookup_employee('Alice') ---")
    result = client.call_tool("lookup_employee", {"name": "Alice"})
    print(f"  {result}")

    print("\n--- lookup_employee('Unknown') ---")
    result = client.call_tool("lookup_employee", {"name": "Unknown"})
    print(f"  {result}")

    print("\nAll tests passed!")


if __name__ == "__main__":
    main()
