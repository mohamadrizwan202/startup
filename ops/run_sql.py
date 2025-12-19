#!/usr/bin/env python3
"""
Execute a SQL file against PostgreSQL using ADMIN_DATABASE_URL.

Usage:
    python ops/run_sql.py ops/db_least_privilege.sql

Environment Variables:
    ADMIN_DATABASE_URL: PostgreSQL connection URL (must be set)
"""
import os
import sys
import argparse
from pathlib import Path


def normalize_pg_url(url: str) -> str:
    """
    Normalize PostgreSQL URL:
    - Convert postgres:// to postgresql://
    - Append sslmode=require if missing (for production safety)
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    # Only add sslmode if not already present and if it looks like a production URL
    if "sslmode=" not in url and ("amazonaws.com" in url or "render.com" in url or "herokuapp.com" in url):
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def run_sql_file(sql_file_path: str, verify: bool = False):
    """
    Execute a SQL file against PostgreSQL.
    
    Args:
        sql_file_path: Path to the SQL file to execute
        verify: If True, verify roles exist after execution
    """
    # Validate ADMIN_DATABASE_URL
    admin_db_url = os.getenv("ADMIN_DATABASE_URL")
    if not admin_db_url:
        print("❌ Error: ADMIN_DATABASE_URL environment variable is not set.", file=sys.stderr)
        print("   Set it to a PostgreSQL connection URL with admin privileges.", file=sys.stderr)
        sys.exit(1)
    
    # Validate SQL file exists
    sql_path = Path(sql_file_path)
    if not sql_path.exists():
        print(f"❌ Error: SQL file not found: {sql_file_path}", file=sys.stderr)
        sys.exit(1)
    
    # Read SQL file
    try:
        sql_content = sql_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"❌ Error reading SQL file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Import psycopg
    try:
        import psycopg  # pyright: ignore[reportMissingImports]
    except ImportError:
        print("❌ Error: psycopg (v3) is not installed.", file=sys.stderr)
        print("   Install it with: pip install psycopg[binary]", file=sys.stderr)
        sys.exit(1)
    
    # Normalize and connect
    normalized_url = normalize_pg_url(admin_db_url)
    try:
        # Use autocommit mode (required for CREATE ROLE, etc.)
        conn = psycopg.connect(normalized_url, autocommit=True, connect_timeout=10)
    except Exception as e:
        print(f"❌ Error connecting to database: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Execute SQL
    try:
        with conn.cursor() as cur:
            cur.execute(sql_content)
        print("✅ SQL executed successfully.")
    except Exception as e:
        print(f"❌ Error executing SQL: {e}", file=sys.stderr)
        conn.close()
        sys.exit(1)
    finally:
        conn.close()
    
    # Verify roles if requested
    if verify:
        verify_roles_internal(admin_db_url)


def verify_roles_internal(admin_db_url: str = None):
    """
    Internal function to verify roles exist.
    Used by both run_sql.py and verify_roles.py.
    """
    import psycopg  # pyright: ignore[reportMissingImports]
    
    if admin_db_url is None:
        admin_db_url = os.getenv("ADMIN_DATABASE_URL")
        if not admin_db_url:
            print("❌ Error: ADMIN_DATABASE_URL environment variable is not set.", file=sys.stderr)
            sys.exit(1)
    
    normalized_url = normalize_pg_url(admin_db_url)
    try:
        conn = psycopg.connect(normalized_url, autocommit=True, connect_timeout=10)
    except Exception as e:
        print(f"❌ Error connecting to database: {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        with conn.cursor() as cur:
            # Check if roles exist
            cur.execute("""
                SELECT rolname 
                FROM pg_roles 
                WHERE rolname IN ('app_runtime', 'app_migrate')
                ORDER BY rolname
            """)
            found_roles = {row[0] for row in cur.fetchall()}
            
            print("\n📋 Role Verification:")
            print("=" * 50)
            
            for role_name in ['app_runtime', 'app_migrate']:
                if role_name in found_roles:
                    print(f"✅ {role_name}: EXISTS")
                else:
                    print(f"❌ {role_name}: NOT FOUND")
            
            print("=" * 50)
            
            if len(found_roles) == 2:
                print("✅ All required roles exist.")
            elif len(found_roles) == 1:
                print("⚠️  Only one role exists. Run the SQL file to create missing roles.")
            else:
                print("❌ No required roles found. Run the SQL file to create them.")
    except Exception as e:
        print(f"❌ Error verifying roles: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Execute a SQL file against PostgreSQL using ADMIN_DATABASE_URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ops/run_sql.py ops/db_least_privilege.sql
  python ops/run_sql.py ops/db_least_privilege.sql --verify
        """
    )
    parser.add_argument("sql_file", help="Path to the SQL file to execute")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify roles exist after execution"
    )
    
    args = parser.parse_args()
    run_sql_file(args.sql_file, verify=args.verify)


if __name__ == "__main__":
    main()

