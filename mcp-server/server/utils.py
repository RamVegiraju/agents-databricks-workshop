"""Utilities for workspace client and request header forwarding."""
import contextvars
import os
from databricks.sdk import WorkspaceClient

header_store = contextvars.ContextVar("header_store")


def get_workspace_client():
    return WorkspaceClient()


def get_user_authenticated_workspace_client():
    if "DATABRICKS_APP_NAME" not in os.environ:
        return WorkspaceClient()
    headers = header_store.get({})
    token = headers.get("x-forwarded-access-token")
    if not token:
        raise ValueError("Missing x-forwarded-access-token header")
    return WorkspaceClient(token=token, auth_type="pat")
