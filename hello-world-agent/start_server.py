"""Entrypoint for the MLflow AgentServer."""

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from agent import server  # noqa: F401
from mlflow.genai.agent_server import AgentServer, setup_mlflow_git_based_version_tracking

agent_server = AgentServer("ResponsesAgent")
app = agent_server.app

try:
    setup_mlflow_git_based_version_tracking()
except Exception:
    pass


def main():
    agent_server.run(app_import_string="start_server:app")


if __name__ == "__main__":
    main()
