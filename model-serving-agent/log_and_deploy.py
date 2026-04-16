"""
Log the agent to MLflow, register to Unity Catalog, and deploy to Model Serving.

Usage (from a Databricks notebook or cluster):
    %run ./log_and_deploy

Or as a standalone script:
    python log_and_deploy.py
"""

import argparse
import datetime

import mlflow
from databricks import agents
from databricks.sdk import WorkspaceClient
from mlflow.models.resources import DatabricksLakebase, DatabricksServingEndpoint

# ---------------------------------------------------------------------------
# Configuration — update these for your workspace
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# UPDATE THESE for your workspace before running
# ---------------------------------------------------------------------------
CATALOG = "main"                           # Unity Catalog name
SCHEMA = "agents"                          # Schema name (create if needed)
MODEL_NAME = "mcp_agent"                   # Model name in UC
ENDPOINT_NAME = "mcp-agent-serving"        # Serving endpoint name
MODEL_ENDPOINT = "databricks-claude-opus-4-5"  # LLM endpoint
MCP_SERVER_URL = "<your-mcp-app-url>/mcp"  # From: databricks apps get agent-mcp-server --output json | jq -r '.url'
LAKEBASE_INSTANCE_NAME = "agent-memory"    # Lakebase instance name
EMBEDDING_ENDPOINT = "databricks-gte-large-en"
EMBEDDING_DIMS = "1024"


def log_and_register():
    """Log the agent to MLflow and register it to Unity Catalog."""
    mlflow.set_registry_uri("databricks-uc")

    uc_model_name = f"{CATALOG}.{SCHEMA}.{MODEL_NAME}"

    resources = [
        DatabricksServingEndpoint(endpoint_name=MODEL_ENDPOINT),
        DatabricksLakebase(instance_name=LAKEBASE_INSTANCE_NAME),
    ]

    input_example = {
        "input": [{"role": "user", "content": "What time is it?"}]
    }

    with mlflow.start_run():
        model_info = mlflow.pyfunc.log_model(
            name="mcp-agent",
            python_model="agent.py",
            input_example=input_example,
            resources=resources,
            pip_requirements=[
                "mlflow>=3.0.0",
                "databricks-agents",
                "databricks-langchain[memory]",
                "databricks-mcp",
                "langgraph",
                "nest_asyncio",
            ],
        )

    print(f"Model logged: {model_info.model_uri}")

    registered = mlflow.register_model(
        model_uri=model_info.model_uri,
        name=uc_model_name,
    )
    print(f"Registered: {registered.name} v{registered.version}")
    return registered


def deploy(registered_model):
    """Deploy the registered model to a Model Serving endpoint."""
    uc_model_name = f"{CATALOG}.{SCHEMA}.{MODEL_NAME}"

    deployment = agents.deploy(
        model_name=uc_model_name,
        model_version=registered_model.version,
        workload_size="Small",
        scale_to_zero=True,
        endpoint_name=ENDPOINT_NAME,
        environment_vars={
            "MCP_SERVER_URL": MCP_SERVER_URL,
            "LAKEBASE_INSTANCE_NAME": LAKEBASE_INSTANCE_NAME,
            "EMBEDDING_ENDPOINT": EMBEDDING_ENDPOINT,
            "EMBEDDING_DIMS": EMBEDDING_DIMS,
        },
        tags={
            "project": "agentic-samples",
            "agent": "mcp-model-serving",
        },
        description="LangGraph agent with MCP tools deployed to Model Serving",
    )

    print(f"\nEndpoint: {deployment.endpoint_name}")
    print(f"URL: {deployment.endpoint_url}")
    print("Waiting for endpoint to become READY...")

    w = WorkspaceClient()
    endpoint = w.serving_endpoints.wait_get_serving_endpoint_not_updating(
        name=deployment.endpoint_name,
        timeout=datetime.timedelta(minutes=30),
    )

    state = endpoint.state.ready
    print(f"Endpoint state: {state}")
    return deployment


def main():
    parser = argparse.ArgumentParser(description="Log and deploy agent to Model Serving")
    parser.add_argument("--catalog", default=CATALOG, help="Unity Catalog name")
    parser.add_argument("--schema", default=SCHEMA, help="Schema name")
    parser.add_argument("--model-name", default=MODEL_NAME, help="Model name")
    parser.add_argument("--endpoint-name", default=ENDPOINT_NAME, help="Serving endpoint name")
    parser.add_argument("--skip-deploy", action="store_true", help="Only log and register, skip deployment")
    args = parser.parse_args()

    global CATALOG, SCHEMA, MODEL_NAME, ENDPOINT_NAME
    CATALOG = args.catalog
    SCHEMA = args.schema
    MODEL_NAME = args.model_name
    ENDPOINT_NAME = args.endpoint_name

    registered = log_and_register()

    if not args.skip_deploy:
        deploy(registered)
    else:
        print("Skipping deployment (--skip-deploy)")


if __name__ == "__main__":
    main()
