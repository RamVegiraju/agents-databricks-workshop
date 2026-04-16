"""
Provision a Lakebase (managed PostgreSQL) instance for agent memory.

This creates a Lakebase instance that both the hello-world-agent and
deep-agents-app samples use for conversation checkpointing and
long-term memory storage.

Requirements:
    pip install databricks-sdk python-dotenv

Usage:
    python provision_lakebase.py
    python provision_lakebase.py --name my-agent-memory --capacity CU_1
"""
import argparse
import os
import uuid

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import DatabaseInstance
from dotenv import load_dotenv

load_dotenv()


def parse_args():
    p = argparse.ArgumentParser(description="Provision a Lakebase instance for agent memory")
    p.add_argument("--name", default="agent-memory", help="Instance name (letters/hyphens, max 63 chars)")
    p.add_argument("--capacity", default="CU_1", help="Compute size: CU_1 | CU_2 | CU_4")
    p.add_argument("--retention", default=7, type=int, help="Point-in-time recovery window in days (2-35)")
    return p.parse_args()


def main():
    args = parse_args()

    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    print(f"\n[1/2] Creating Lakebase instance '{args.name}' ({args.capacity}) ...")
    print("      This may take a few minutes.")

    instance = w.database.create_database_instance_and_wait(
        DatabaseInstance(
            name=args.name,
            capacity=args.capacity,
            retention_window_in_days=args.retention,
        )
    )

    print(f"      Instance ready")
    print(f"        Read/Write DNS : {instance.read_write_dns}")

    print(f"\n[2/2] Verifying database credentials ...")
    w.database.generate_database_credential(
        request_id=str(uuid.uuid4()),
        instance_names=[args.name],
    )
    print(f"      Credentials verified for user '{w.current_user.me().user_name}'")

    print("\n" + "=" * 60)
    print("Add this to your .env files:")
    print("=" * 60)
    print(f"LAKEBASE_INSTANCE_NAME={args.name}")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Set LAKEBASE_INSTANCE_NAME in hello-world-agent/.env")
    print("     and/or deep-agents-app/.env")
    print("  2. Update the same value in app.yaml and databricks.yml")
    print("     for each sample you want to deploy")
    print("  3. Deploy your agent app(s)")
    print("  4. Run setup_lakebase_permissions.py to grant SP access")


if __name__ == "__main__":
    main()
