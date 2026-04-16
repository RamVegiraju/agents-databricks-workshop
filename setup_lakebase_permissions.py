"""
Initialize Lakebase tables and grant the agent app's service principal permissions.

Run this ONCE per app after deploying (so the SP exists) and before using the agent.

Usage:
    python setup_lakebase_permissions.py --app-name agent-hello-world --instance agent-memory
    python setup_lakebase_permissions.py --app-name agent-research-assistant --instance agent-memory
"""
import argparse
import asyncio
import os

from databricks.sdk import WorkspaceClient
from databricks_ai_bridge.lakebase import LakebaseClient, SchemaPrivilege, TablePrivilege
from databricks_langchain import AsyncCheckpointSaver, DatabricksStore
from dotenv import load_dotenv

load_dotenv()

STORE_TABLES = [
    "public.store",
    "public.store_vectors",
    "public.store_migrations",
    "public.vector_migrations",
]
CHECKPOINT_TABLES = [
    "public.checkpoints",
    "public.checkpoint_blobs",
    "public.checkpoint_writes",
    "public.checkpoint_migrations",
]
ALL_TABLES = STORE_TABLES + CHECKPOINT_TABLES


def parse_args():
    p = argparse.ArgumentParser(
        description="Initialize Lakebase tables and grant SP permissions"
    )
    p.add_argument("--app-name", required=True, help="Databricks App name (e.g. agent-hello-world)")
    p.add_argument("--instance", default="agent-memory", help="Lakebase instance name")
    p.add_argument("--skip-init", action="store_true", help="Skip table initialization (if already done)")
    return p.parse_args()


def get_sp_client_id(w, app_name):
    """Get the service principal's client ID for a Databricks App."""
    app = w.apps.get(app_name)
    sp_client_id = getattr(app, "service_principal_client_id", None)
    if not sp_client_id:
        sp = w.service_principals.get(app.service_principal_id)
        sp_client_id = str(sp.application_id)
    print(f"  SP display name : {getattr(app, 'service_principal_name', 'n/a')}")
    print(f"  SP client ID    : {sp_client_id}")
    return sp_client_id


def init_tables(instance_name, embedding_endpoint, embedding_dims):
    """Create store and checkpoint tables as admin."""
    print("  Initializing DatabricksStore tables ...")
    store = DatabricksStore(
        instance_name=instance_name,
        embedding_endpoint=embedding_endpoint,
        embedding_dims=embedding_dims,
    )
    store.setup()
    print("  DatabricksStore tables ready.")

    print("  Initializing AsyncCheckpointSaver tables ...")
    asyncio.run(_init_checkpointer(instance_name))
    print("  AsyncCheckpointSaver tables ready.")


async def _init_checkpointer(instance_name):
    async with AsyncCheckpointSaver(instance_name=instance_name) as cp:
        await cp.setup()


def grant_sp_permissions(instance_name, sp_client_id):
    """Grant the SP schema and table permissions via LakebaseClient."""
    client = LakebaseClient(instance_name=instance_name)

    print(f"  Creating Postgres role for SP '{sp_client_id}' ...")
    client.create_role(sp_client_id, "SERVICE_PRINCIPAL")

    print("  Granting USAGE + CREATE on schema public ...")
    client.grant_schema(
        grantee=sp_client_id,
        schemas=["public"],
        privileges=[SchemaPrivilege.USAGE, SchemaPrivilege.CREATE],
    )

    print(f"  Granting DML on {len(ALL_TABLES)} tables ...")
    client.grant_table(
        grantee=sp_client_id,
        tables=ALL_TABLES,
        privileges=[
            TablePrivilege.SELECT,
            TablePrivilege.INSERT,
            TablePrivilege.UPDATE,
            TablePrivilege.DELETE,
        ],
    )
    print("  Permissions granted.")


def main():
    args = parse_args()
    instance = args.instance
    embedding_endpoint = os.getenv("EMBEDDING_ENDPOINT", "databricks-gte-large-en")
    embedding_dims = int(os.getenv("EMBEDDING_DIMS", "1024"))

    host = os.environ.get("DATABRICKS_HOST", "")
    if not host:
        print("Error: Set DATABRICKS_HOST in .env (e.g. https://your-workspace.cloud.databricks.com)")
        raise SystemExit(1)

    w = WorkspaceClient(host=host)

    print(f"\n[1/3] Resolving SP for app '{args.app_name}' ...")
    sp_client_id = get_sp_client_id(w, args.app_name)

    if not args.skip_init:
        print(f"\n[2/3] Initializing Lakebase tables on '{instance}' ...")
        init_tables(instance, embedding_endpoint, embedding_dims)
    else:
        print("\n[2/3] Skipping table initialization (--skip-init).")

    print(f"\n[3/3] Granting permissions to SP on '{instance}' ...")
    grant_sp_permissions(instance, sp_client_id)

    print("\nDone! The agent app can now read/write memory tables.")


if __name__ == "__main__":
    main()
