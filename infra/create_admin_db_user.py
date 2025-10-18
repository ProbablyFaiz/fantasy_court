#!/usr/bin/env python3

import argparse
import subprocess
import sys
import base64
import os


def run_psql(database, command, capture_output=False):
    """Run a psql command."""
    cmd = ["psql", database, "-t", "-c", command]
    if capture_output:
        result = subprocess.run(cmd, capture_output=True, text=True)
    else:
        result = subprocess.run(cmd, stderr=subprocess.DEVNULL)
    return result


def user_exists(username):
    """Check if a PostgreSQL user exists."""
    result = run_psql(
        "postgres",
        f"SELECT 1 FROM pg_user WHERE usename = '{username}';",
        capture_output=True,
    )
    return result.returncode == 0 and result.stdout.strip().startswith("1")


def database_exists(database):
    """Check if a PostgreSQL database exists."""
    result = run_psql(
        "postgres",
        f"SELECT 1 FROM pg_database WHERE datname = '{database}';",
        capture_output=True,
    )
    return result.returncode == 0 and result.stdout.strip().startswith("1")


def main():
    parser = argparse.ArgumentParser(description="Create PostgreSQL admin user")
    parser.add_argument("username", help="Username to create")
    parser.add_argument("database", help="Database to grant privileges on")
    parser.add_argument(
        "--skip-create",
        "-s",
        action="store_true",
        help="Skip user creation and just assign privileges",
    )

    args = parser.parse_args()

    # Check if database exists
    if not database_exists(args.database):
        print(f"Error: Database '{args.database}' does not exist")
        sys.exit(1)

    password = None

    # Handle user creation or validation
    if not args.skip_create:
        # Check if user already exists
        if user_exists(args.username):
            print(
                f"Error: User '{args.username}' already exists. Use --skip-create to just assign privileges."
            )
            sys.exit(1)

        # Create user
        print(f"Creating user '{args.username}'...")
        password = base64.b64encode(os.urandom(24)).decode("utf-8")
        result = run_psql(
            "postgres", f"CREATE USER {args.username} WITH PASSWORD '{password}';"
        )
        if result.returncode != 0:
            print(f"Error creating user '{args.username}'")
            sys.exit(1)
        print(f"User '{args.username}' created successfully")
    else:
        # Verify user exists when skipping creation
        if not user_exists(args.username):
            print(
                f"Error: User '{args.username}' does not exist. Remove --skip-create to create the user."
            )
            sys.exit(1)
        print(f"User '{args.username}' exists, assigning privileges...")

    # Grant privileges
    print(
        f"Granting admin privileges to user '{args.username}' on database '{args.database}'..."
    )

    privilege_commands = f"""
GRANT CONNECT ON DATABASE "{args.database}" to {args.username};

GRANT ALL PRIVILEGES ON SCHEMA public TO {args.username};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {args.username};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {args.username};

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO {args.username};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO {args.username};

ALTER USER {args.username} BYPASSRLS;
"""

    result = run_psql(args.database, privilege_commands)
    if result.returncode != 0:
        print(f"Error granting privileges to user '{args.username}'")
        sys.exit(1)

    if password:
        print(f"✓ Created admin user '{args.username}' with password: {password}")
    else:
        print(f"✓ Assigned admin privileges to user '{args.username}'")


if __name__ == "__main__":
    main()
