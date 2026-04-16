"""
Test script for the agent deployed on Databricks Model Serving.

Demonstrates short-term memory (conversation context within a thread),
long-term memory (user facts across threads), and MCP tool usage.

Usage:
    python test_endpoint.py
    python test_endpoint.py --demo short-term
    python test_endpoint.py --demo long-term
    python test_endpoint.py --demo tools
"""

import argparse
import json
import time

import requests
from databricks.sdk import WorkspaceClient


DEFAULT_ENDPOINT = "mcp-agent-serving"


def get_client():
    """Return base URL, headers from WorkspaceClient."""
    w = WorkspaceClient()
    token = w.config.authenticate()
    return w.config.host, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def call_agent(base_url, headers, endpoint, message, user_id="demo-user", thread_id="demo-thread"):
    """Send a message and return the assistant's text response."""
    url = f"{base_url}/serving-endpoints/{endpoint}/invocations"
    payload = {
        "input": [{"role": "user", "content": message}],
        "custom_inputs": {"user_id": user_id, "thread_id": thread_id},
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    result = resp.json()

    for item in reversed(result.get("output", [])):
        if item.get("type") == "message" and item.get("role") == "assistant":
            content = item.get("content", [])
            texts = [c.get("text", "") for c in content if c.get("type") == "output_text"]
            return " ".join(texts).strip()
    return json.dumps(result, indent=2)


def p(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}\n")


def t(role, text):
    label = "User " if role == "user" else "Agent"
    print(f"  [{label}]: {text}\n")


# ---------------------------------------------------------------------------
# Demos
# ---------------------------------------------------------------------------


def demo_short_term(base_url, headers, endpoint):
    p("SHORT-TERM MEMORY (conversation context within a thread)")
    print("  Same thread recalls earlier turns; new thread starts fresh.\n")

    user = f"stm-user-{int(time.time())}"
    thread = f"stm-{int(time.time())}"

    msg1 = "I'm thinking of ordering pizza tonight. What toppings go well together?"
    t("user", msg1)
    t("agent", call_agent(base_url, headers, endpoint, msg1, user_id=user, thread_id=thread))

    msg2 = "What food was I thinking of ordering?"
    t("user", msg2)
    t("agent", call_agent(base_url, headers, endpoint, msg2, user_id=user, thread_id=thread))

    print("  --- Switching to a NEW thread (same user, fresh conversation) ---\n")
    new_thread = f"stm-new-{int(time.time())}"
    msg3 = "What food was I thinking of ordering?"
    t("user", msg3)
    t("agent", call_agent(base_url, headers, endpoint, msg3, user_id=user, thread_id=new_thread))


def demo_long_term(base_url, headers, endpoint):
    p("LONG-TERM MEMORY (user facts that persist across threads)")
    print("  User facts saved to Lakebase via memory tools, recalled across threads.\n")

    user = f"ltm-user-{int(time.time())}"
    t1 = f"ltm-t1-{int(time.time())}"
    t2 = f"ltm-t2-{int(time.time())}"
    t3 = f"ltm-t3-{int(time.time())}"

    print("  [Step 1] Save facts in thread 1\n")
    msg1 = "Remember that my name is Alice and I work on data engineering."
    t("user", msg1)
    t("agent", call_agent(base_url, headers, endpoint, msg1, user_id=user, thread_id=t1))

    print("  [Step 2] Recall in a NEW thread (proves cross-thread persistence)\n")
    msg2 = "What do you know about me?"
    t("user", msg2)
    t("agent", call_agent(base_url, headers, endpoint, msg2, user_id=user, thread_id=t2))

    print("  [Step 3] Delete all memories\n")
    msg3 = "Please forget everything you know about me."
    t("user", msg3)
    t("agent", call_agent(base_url, headers, endpoint, msg3, user_id=user, thread_id=t2))

    print("  [Step 4] Verify deletion in another NEW thread\n")
    msg4 = "What do you know about me?"
    t("user", msg4)
    t("agent", call_agent(base_url, headers, endpoint, msg4, user_id=user, thread_id=t3))


def demo_tools(base_url, headers, endpoint):
    p("MCP TOOL USAGE (time, calculator, employee lookup)")
    thread = f"tools-{int(time.time())}"

    msg1 = "What time is it right now?"
    t("user", msg1)
    t("agent", call_agent(base_url, headers, endpoint, msg1, thread_id=thread))

    msg2 = "Calculate 42 * 17 + 3."
    t("user", msg2)
    t("agent", call_agent(base_url, headers, endpoint, msg2, thread_id=thread))

    msg3 = "Look up Alice in the company directory."
    t("user", msg3)
    t("agent", call_agent(base_url, headers, endpoint, msg3, thread_id=thread))


DEMOS = {
    "short-term": demo_short_term,
    "long-term": demo_long_term,
    "tools": demo_tools,
}


def main():
    parser = argparse.ArgumentParser(description="Test the deployed Model Serving agent")
    parser.add_argument("--demo", choices=list(DEMOS.keys()), help="Run a specific demo (default: run all)")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Serving endpoint name")
    args = parser.parse_args()

    print("Authenticating with Databricks SDK...")
    base_url, headers = get_client()
    print(f"Endpoint: {args.endpoint}\n")

    if args.demo:
        DEMOS[args.demo](base_url, headers, args.endpoint)
    else:
        for fn in DEMOS.values():
            fn(base_url, headers, args.endpoint)

    p("ALL DEMOS COMPLETE")


if __name__ == "__main__":
    main()
