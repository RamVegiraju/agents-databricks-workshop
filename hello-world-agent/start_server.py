"""Entrypoint for the MLflow AgentServer."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

# Resolve oauth+pat auth conflict before any SDK import.
if os.environ.get("DATABRICKS_CLIENT_ID") and os.environ.get("DATABRICKS_CLIENT_SECRET"):
    os.environ.pop("DATABRICKS_TOKEN", None)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from agent import server  # noqa: F401
from agent.memory import get_checkpointer, get_store
from mlflow.genai.agent_server import AgentServer, setup_mlflow_git_based_version_tracking

logger = logging.getLogger(__name__)


async def _run_lakebase_setup():
    """Initialize Lakebase tables once at startup (DDL only)."""
    try:
        async with get_store() as store:
            await store.setup()
        async with get_checkpointer() as checkpointer:
            await checkpointer.setup()
        logger.info("Lakebase tables initialized.")
    except Exception as e:
        logger.warning("Lakebase setup skipped (tables may already exist): %s", e)


@asynccontextmanager
async def lifespan(app):
    """Run one-time setup at server startup."""
    await _run_lakebase_setup()
    yield


agent_server = AgentServer("ResponsesAgent")
app = agent_server.app
app.router.lifespan_context = lifespan

try:
    setup_mlflow_git_based_version_tracking()
except Exception:
    pass


def main():
    agent_server.run(app_import_string="start_server:app")


if __name__ == "__main__":
    main()
