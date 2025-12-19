#!/usr/bin/env python3
"""
Run database schema migration using migrate credentials.

This script safely executes schema creation using the migrate role (app_migrate)
instead of the runtime role (app_runtime), preventing DDL permission errors.

Usage:
    python ops/migrate.py

Environment Variables:
    DATABASE_URL_MIGRATE: PostgreSQL connection URL with migrate role (preferred)
    ADMIN_DATABASE_URL: PostgreSQL connection URL with admin privileges (fallback)
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import db module
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    """Run schema migration using migrate credentials."""
    # Read migrate URL (preferred) or admin URL (fallback)
    migrate_url = os.getenv("DATABASE_URL_MIGRATE")
    if not migrate_url:
        migrate_url = os.getenv("ADMIN_DATABASE_URL")
    
    if not migrate_url:
        print("❌ Error: Neither DATABASE_URL_MIGRATE nor ADMIN_DATABASE_URL is set.", file=sys.stderr)
        print("   Set one of these environment variables to a PostgreSQL connection URL.", file=sys.stderr)
        sys.exit(1)
    
    # Set DATABASE_URL_MIGRATE so db.get_migrate_conn() uses it
    # This must be set before importing db module
    os.environ["DATABASE_URL_MIGRATE"] = migrate_url
    
    # Also set DATABASE_URL as fallback for db module initialization
    if not os.getenv("DATABASE_URL"):
        os.environ["DATABASE_URL"] = migrate_url
    
    try:
        # Import db module after setting environment variables
        import db
        
        # Verify we can connect
        print("Connecting to database...")
        conn = db.get_migrate_conn()
        conn.close()
        print("✓ Database connection successful")
        
        # Run schema creation
        print("Running schema migration...")
        db.ensure_schema()
        
        print("✅ OK migrated")
        sys.exit(0)
        
    except ImportError as e:
        print(f"❌ Error: Failed to import db module: {e}", file=sys.stderr)
        print("   Make sure you're running this from the project root directory.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: Migration failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

