"""
Test script for the deployed MCP server.

Usage:
    pip install databricks-sdk databricks-mcp
    python test_mcp_server.py --url https://<your-mcp-app-url> --profile oauth
"""

import argparse

from databricks.sdk import WorkspaceClient
from databricks_mcp import DatabricksMCPClient


def main():
    parser = argparse.ArgumentParser(description="Test the deployed MCP server")
    parser.add_argument("--url", required=True, help="MCP server app URL (e.g. https://agent-mcp-server-xxx.databricksapps.com)")
    parser.add_argument("--profile", default="oauth", help="Databricks CLI profile with OAuth auth (default: oauth)")
    args = parser.parse_args()

    mcp_url = args.url.rstrip("/") + "/mcp"

    ws = WorkspaceClient(profile=args.profile)
    client = DatabricksMCPClient(server_url=mcp_url, workspace_client=ws)

    print("=== Available tools ===")
    print(client.list_tools())

    print("\n=== get_current_time() ===")
    print(client.call_tool("get_current_time", {}))

    print("\n=== calculator('42 * 17 + 3') ===")
    print(client.call_tool("calculator", {"expression": "42 * 17 + 3"}))

    print("\n=== lookup_employee('Alice') ===")
    print(client.call_tool("lookup_employee", {"name": "Alice"}))

    print("\n=== lookup_employee('Unknown') ===")
    print(client.call_tool("lookup_employee", {"name": "Unknown"}))


if __name__ == "__main__":
    main()
