"""
Test script for the deep-agents research assistant deployed on Databricks Apps.

Demonstrates subagent delegation, CompositeBackend memory (ephemeral + persistent),
and MCP tool usage.

Usage:
    uv run python test_agent.py
    uv run python test_agent.py --demo memory
    uv run python test_agent.py --demo research
    uv run python test_agent.py --demo tools
"""

import argparse
import json
import os
import subprocess
import sys
import time

from dotenv import load_dotenv

load_dotenv()

DEFAULT_APP_URL = os.environ.get("APP_URL", "")
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "")


def get_oauth_token() -> str:
    result = subprocess.run(
        ["databricks", "auth", "token", "--host", DATABRICKS_HOST],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Error getting token: {result.stderr}")
        sys.exit(1)
    return json.loads(result.stdout)["access_token"]


def call_agent(app_url, token, message, user_id="demo-user", thread_id="demo-thread"):
    import urllib.request

    payload = json.dumps({
        "input": [{"role": "user", "content": message}],
        "custom_inputs": {"user_id": user_id, "thread_id": thread_id},
    }).encode()

    req = urllib.request.Request(
        f"{app_url}/invocations", data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=180) as resp:
        body = json.loads(resp.read())

    # Show tool calls (subagent delegations, file ops, MCP tools)
    for item in body.get("output", []):
        if item.get("type") == "function_call":
            name = item.get("name", "")
            if name == "task":
                args = json.loads(item.get("arguments", "{}"))
                subagent = args.get("subagent_type", "unknown")
                print(f"    >> Delegated to subagent: {subagent}")
            else:
                print(f"    >> Tool call: {name}")

    # Extract final assistant message
    for item in reversed(body.get("output", [])):
        if item.get("type") == "message" and item.get("role") == "assistant":
            content = item.get("content", [])
            texts = [c.get("text", "") for c in content if c.get("type") == "output_text"]
            return " ".join(texts).strip()
    return json.dumps(body, indent=2)


def p(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}\n")


def t(role, text):
    label = "User " if role == "user" else "Agent"
    print(f"  [{label}]: {text}\n")


# ---------------------------------------------------------------------------
# Demos
# ---------------------------------------------------------------------------


def demo_memory(app_url, token):
    p("LONG-TERM MEMORY (CompositeBackend — /memories/ route)")
    print("  Files at /memories/ persist across threads via StoreBackend.\n")

    user = f"deep-demo-{int(time.time())}"
    t1 = f"mem-t1-{int(time.time())}"
    t2 = f"mem-t2-{int(time.time())}"
    t3 = f"mem-t3-{int(time.time())}"

    print("  [Step 1] Save a preference (thread 1)\n")
    msg1 = "Remember that I prefer bullet-point summaries over paragraphs."
    t("user", msg1)
    t("agent", call_agent(app_url, token, msg1, user_id=user, thread_id=t1))

    print("  [Step 2] Recall in a NEW thread (proves cross-thread persistence)\n")
    msg2 = "What do you know about my preferences?"
    t("user", msg2)
    t("agent", call_agent(app_url, token, msg2, user_id=user, thread_id=t2))

    print("  [Step 3] Verify short-term isolation — new thread forgets conversation\n")
    msg3 = "What was the first thing I said to you?"
    t("user", msg3)
    t("agent", call_agent(app_url, token, msg3, user_id=user, thread_id=t3))


def demo_research(app_url, token):
    p("SUBAGENT DELEGATION (researcher + fact-checker)")
    print("  The main agent delegates to specialized subagents.\n")

    thread = f"research-{int(time.time())}"

    msg1 = "Research the key benefits of lakehouse architecture in 3 bullet points."
    t("user", msg1)
    t("agent", call_agent(app_url, token, msg1, thread_id=thread))

    msg2 = "Fact-check: Delta Lake supports ACID transactions."
    t("user", msg2)
    t("agent", call_agent(app_url, token, msg2, thread_id=thread))


def demo_tools(app_url, token):
    p("MCP TOOL USAGE")
    thread = f"tools-{int(time.time())}"

    msg1 = "What time is it?"
    t("user", msg1)
    t("agent", call_agent(app_url, token, msg1, thread_id=thread))

    msg2 = "Calculate 2^10 - 24."
    t("user", msg2)
    t("agent", call_agent(app_url, token, msg2, thread_id=thread))


DEMOS = {"memory": demo_memory, "research": demo_research, "tools": demo_tools}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", choices=list(DEMOS.keys()))
    parser.add_argument("--app-url", default=DEFAULT_APP_URL)
    args = parser.parse_args()

    if not args.app_url:
        print("Error: Set APP_URL in .env or pass --app-url. Get it with:")
        print("  databricks apps get agent-research-assistant --output json | jq -r '.url'")
        sys.exit(1)
    if not DATABRICKS_HOST:
        print("Error: Set DATABRICKS_HOST in .env (e.g. https://your-workspace.cloud.databricks.com)")
        sys.exit(1)

    print("Authenticating...")
    token = get_oauth_token()
    print(f"App URL: {args.app_url}\n")

    if args.demo:
        DEMOS[args.demo](args.app_url, token)
    else:
        for fn in DEMOS.values():
            fn(args.app_url, token)

    p("ALL DEMOS COMPLETE")


if __name__ == "__main__":
    main()
