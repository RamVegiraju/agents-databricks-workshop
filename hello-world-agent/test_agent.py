"""
Test script for the hello-world agent deployed on Databricks Apps.

Demonstrates both short-term memory (conversation context within a thread)
and long-term memory (user facts that persist across threads), plus MCP tool usage.

Usage:
    # Run all demos
    uv run python test_agent.py

    # Run a specific demo
    uv run python test_agent.py --demo short-term
    uv run python test_agent.py --demo long-term
    uv run python test_agent.py --demo tools

    # Custom app URL
    uv run python test_agent.py --app-url https://your-app.databricksapps.com
"""

import argparse
import json
import os
import subprocess
import sys
import time

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_APP_URL = os.environ.get("APP_URL", "")
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "")


def get_oauth_token() -> str:
    """Get an OAuth token via the Databricks CLI."""
    result = subprocess.run(
        ["databricks", "auth", "token", "--host", DATABRICKS_HOST],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Error getting token: {result.stderr}")
        sys.exit(1)
    return json.loads(result.stdout)["access_token"]


def call_agent(
    app_url: str,
    token: str,
    message: str,
    user_id: str = "demo-user",
    thread_id: str = "demo-thread",
) -> str:
    """Call the deployed agent and return the text response."""
    import urllib.request

    payload = json.dumps({
        "input": [{"role": "user", "content": message}],
        "custom_inputs": {"user_id": user_id, "thread_id": thread_id},
    }).encode()

    req = urllib.request.Request(
        f"{app_url}/invocations",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read())

    # Extract the final assistant message text
    for item in reversed(body.get("output", [])):
        if item.get("type") == "message" and item.get("role") == "assistant":
            content = item.get("content", [])
            texts = [c.get("text", "") for c in content if c.get("type") == "output_text"]
            return " ".join(texts).strip()

    return json.dumps(body, indent=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_turn(role: str, text: str):
    label = "User " if role == "user" else "Agent"
    print(f"  [{label}]: {text}\n")


# ---------------------------------------------------------------------------
# Demo 1: Short-term memory (same thread remembers context)
# ---------------------------------------------------------------------------


def demo_short_term_memory(app_url: str, token: str):
    print_section("SHORT-TERM MEMORY (conversation context within a thread)")
    print("  Short-term memory = conversation history stored per thread_id.")
    print("  Same thread recalls earlier turns; new thread starts fresh.")
    print("  (Uses a unique user_id with no long-term memories saved.)\n")

    # Use a unique user so long-term memory can't interfere
    user = f"stm-user-{int(time.time())}"
    thread = f"stm-demo-{int(time.time())}"

    # Turn 1: Say something ephemeral that the agent won't save to long-term memory
    msg1 = "I'm thinking of ordering pizza tonight. What toppings go well together?"
    print_turn("user", msg1)
    reply1 = call_agent(app_url, token, msg1, user_id=user, thread_id=thread)
    print_turn("agent", reply1)

    # Turn 2: Reference it — same thread should recall from conversation history
    msg2 = "What food was I thinking of ordering?"
    print_turn("user", msg2)
    reply2 = call_agent(app_url, token, msg2, user_id=user, thread_id=thread)
    print_turn("agent", reply2)

    # Turn 3: New thread, same user — should NOT recall (ephemeral, not saved)
    print("  --- Switching to a NEW thread (same user, fresh conversation) ---\n")
    new_thread = f"stm-demo-new-{int(time.time())}"
    msg3 = "What food was I thinking of ordering?"
    print_turn("user", msg3)
    reply3 = call_agent(app_url, token, msg3, user_id=user, thread_id=new_thread)
    print_turn("agent", reply3)


# ---------------------------------------------------------------------------
# Demo 2: Long-term memory (persists across threads)
# ---------------------------------------------------------------------------


def demo_long_term_memory(app_url: str, token: str):
    print_section("LONG-TERM MEMORY (user facts that persist across threads)")
    print("  Long-term memory = user facts saved to Lakebase via memory tools.")
    print("  Persists across threads for the same user_id.")
    print("  The agent explicitly saves/recalls/deletes with tool calls.\n")

    user = f"ltm-demo-user-{int(time.time())}"
    thread1 = f"ltm-thread1-{int(time.time())}"
    thread2 = f"ltm-thread2-{int(time.time())}"
    thread3 = f"ltm-thread3-{int(time.time())}"

    # Step 1 — Save facts (thread 1)
    print("  [Step 1] Save facts in thread 1\n")
    msg1 = "Remember that my name is Alice and I work on data engineering."
    print_turn("user", msg1)
    reply1 = call_agent(app_url, token, msg1, user_id=user, thread_id=thread1)
    print_turn("agent", reply1)

    # Step 2 — Recall in a completely different thread (thread 2)
    print("  [Step 2] Recall in a NEW thread (proves cross-thread persistence)\n")
    msg2 = "What do you know about me?"
    print_turn("user", msg2)
    reply2 = call_agent(app_url, token, msg2, user_id=user, thread_id=thread2)
    print_turn("agent", reply2)

    # Step 3 — Delete memories
    print("  [Step 3] Delete all memories\n")
    msg3 = "Please forget everything you know about me."
    print_turn("user", msg3)
    reply3 = call_agent(app_url, token, msg3, user_id=user, thread_id=thread2)
    print_turn("agent", reply3)

    # Step 4 — Verify deletion in yet another thread (thread 3)
    print("  [Step 4] Verify deletion in another NEW thread\n")
    msg4 = "What do you know about me?"
    print_turn("user", msg4)
    reply4 = call_agent(app_url, token, msg4, user_id=user, thread_id=thread3)
    print_turn("agent", reply4)


# ---------------------------------------------------------------------------
# Demo 3: MCP tool usage
# ---------------------------------------------------------------------------


def demo_tools(app_url: str, token: str):
    print_section("MCP TOOL USAGE (time, calculator, employee lookup)")
    print("  The agent calls tools hosted on the shared MCP server.\n")

    thread = f"tools-demo-{int(time.time())}"

    # Tool 1: Time
    msg1 = "What time is it right now?"
    print_turn("user", msg1)
    reply1 = call_agent(app_url, token, msg1, thread_id=thread)
    print_turn("agent", reply1)

    # Tool 2: Calculator
    msg2 = "Calculate 42 * 17 + 3."
    print_turn("user", msg2)
    reply2 = call_agent(app_url, token, msg2, thread_id=thread)
    print_turn("agent", reply2)

    # Tool 3: Employee lookup
    msg3 = "Look up Alice in the company directory."
    print_turn("user", msg3)
    reply3 = call_agent(app_url, token, msg3, thread_id=thread)
    print_turn("agent", reply3)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DEMOS = {
    "short-term": demo_short_term_memory,
    "long-term": demo_long_term_memory,
    "tools": demo_tools,
}


def main():
    parser = argparse.ArgumentParser(description="Test the deployed hello-world agent")
    parser.add_argument(
        "--demo",
        choices=list(DEMOS.keys()),
        help="Run a specific demo (default: run all)",
    )
    parser.add_argument(
        "--app-url",
        default=DEFAULT_APP_URL,
        help="Deployed app URL",
    )
    args = parser.parse_args()

    if not args.app_url:
        print("Error: Set APP_URL in .env or pass --app-url. Get it with:")
        print("  databricks apps get agent-hello-world --output json | jq -r '.url'")
        sys.exit(1)
    if not DATABRICKS_HOST:
        print("Error: Set DATABRICKS_HOST in .env (e.g. https://your-workspace.cloud.databricks.com)")
        sys.exit(1)

    print("Authenticating with Databricks CLI...")
    token = get_oauth_token()
    print(f"App URL: {args.app_url}\n")

    if args.demo:
        DEMOS[args.demo](args.app_url, token)
    else:
        demo_short_term_memory(args.app_url, token)
        demo_long_term_memory(args.app_url, token)
        demo_tools(args.app_url, token)

    print_section("ALL DEMOS COMPLETE")


if __name__ == "__main__":
    main()
