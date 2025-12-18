#!/usr/bin/env python3
"""
Verify that app_runtime and app_migrate roles exist in PostgreSQL.

Usage:
    python ops/verify_roles.py

Environment Variables:
    ADMIN_DATABASE_URL: PostgreSQL connection URL (must be set)
"""
import os
import sys


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


def main():
    # Validate ADMIN_DATABASE_URL
    admin_db_url = os.getenv("ADMIN_DATABASE_URL")
    if not admin_db_url:
        print("❌ Error: ADMIN_DATABASE_URL environment variable is not set.", file=sys.stderr)
        print("   Set it to a PostgreSQL connection URL with admin privileges.", file=sys.stderr)
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
            
            print("📋 Role Verification:")
            print("=" * 50)
            
            for role_name in ['app_runtime', 'app_migrate']:
                if role_name in found_roles:
                    print(f"✅ {role_name}: EXISTS")
                else:
                    print(f"❌ {role_name}: NOT FOUND")
            
            print("=" * 50)
            
            if len(found_roles) == 2:
                print("✅ All required roles exist.")
                sys.exit(0)
            elif len(found_roles) == 1:
                print("⚠️  Only one role exists. Run the SQL file to create missing roles.")
                sys.exit(1)
            else:
                print("❌ No required roles found. Run the SQL file to create them.")
                sys.exit(1)
    except Exception as e:
        print(f"❌ Error verifying roles: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

