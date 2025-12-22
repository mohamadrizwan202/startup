#!/usr/bin/env python3
"""
Seed Postgres database from local SQLite file.

This script reads data from the SQLite file (allergen_nutrition.db) and inserts it
into the Postgres database. It uses ON CONFLICT DO NOTHING to make it safe to re-run.

Usage:
    DB_URL="postgresql://..." python3 scripts/seed_postgres_from_sqlite.py

Or with custom SQLite path:
    SQLITE_PATH="path/to/db.db" DB_URL="postgresql://..." python3 scripts/seed_postgres_from_sqlite.py

Environment variables:
    SQLITE_PATH: Path to SQLite database file (default: "allergen_nutrition.db")
    DB_URL: PostgreSQL connection URL (required, also checks DATABASE_URL)
    DATABASE_URL: Fallback for DB_URL if DB_URL is not set
"""
import os
import sys
import sqlite3
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("ERROR: psycopg is required. Install it with: pip install psycopg[binary]", file=sys.stderr)
    sys.exit(1)


def normalize_pg_url(url: str) -> str:
    """
    Normalize PostgreSQL URL:
    - Convert postgres:// to postgresql://
    - Append sslmode=require if missing
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def main():
    # Read configuration from environment
    sqlite_path = os.getenv("SQLITE_PATH", "allergen_nutrition.db")
    pg_url = os.getenv("DB_URL") or os.getenv("DATABASE_URL")
    
    if not pg_url:
        print("ERROR: DB_URL or DATABASE_URL environment variable must be set", file=sys.stderr)
        sys.exit(1)
    
    # Resolve SQLite path relative to script directory if needed
    if not os.path.isabs(sqlite_path):
        script_dir = Path(__file__).parent.parent
        sqlite_path = script_dir / sqlite_path
    else:
        sqlite_path = Path(sqlite_path)
    
    if not sqlite_path.exists():
        print(f"ERROR: SQLite file not found: {sqlite_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Reading from SQLite: {sqlite_path}")
    print(f"Writing to Postgres: {pg_url.split('@')[1] if '@' in pg_url else '***'}")
    
    # Connect to SQLite
    try:
        sqlite_conn = sqlite3.connect(str(sqlite_path))
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
    except Exception as e:
        print(f"ERROR: Failed to connect to SQLite: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Connect to Postgres
    try:
        normalized_url = normalize_pg_url(pg_url)
        pg_conn = psycopg.connect(normalized_url, row_factory=dict_row, connect_timeout=10)
        pg_cursor = pg_conn.cursor()
    except Exception as e:
        print(f"ERROR: Failed to connect to Postgres: {e}", file=sys.stderr)
        sqlite_conn.close()
        sys.exit(1)
    
    try:
        # Table 1: ingredient_categories
        print("\n=== ingredient_categories ===")
        sqlite_cursor.execute("""
            SELECT ingredient, category, subcategory, health_benefits, key_nutrients, description
            FROM ingredient_categories
        """)
        rows = sqlite_cursor.fetchall()
        print(f"Found {len(rows)} rows in SQLite")
        
        if rows:
            # Convert SQLite rows to tuples for executemany
            data = []
            for row in rows:
                data.append((
                    row['ingredient'],
                    row['category'],
                    row['subcategory'],
                    row['health_benefits'],
                    row['key_nutrients'],
                    row['description']
                ))
            
            # Insert with ON CONFLICT DO NOTHING
            pg_cursor.executemany("""
                INSERT INTO ingredient_categories 
                (ingredient, category, subcategory, health_benefits, key_nutrients, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (ingredient, category, subcategory) DO NOTHING
            """, data)
            pg_conn.commit()
            inserted = pg_cursor.rowcount
            skipped = len(data) - inserted
            print(f"Inserted {inserted} rows, skipped {skipped} (already exist)")
        
        # Table 2: health_specific_serving_sizes
        print("\n=== health_specific_serving_sizes ===")
        sqlite_cursor.execute("""
            SELECT ingredient, health_benefit, nutrient_category, serving_size, serving_description, description
            FROM health_specific_serving_sizes
        """)
        rows = sqlite_cursor.fetchall()
        print(f"Found {len(rows)} rows in SQLite")
        
        if rows:
            data = []
            for row in rows:
                data.append((
                    row['ingredient'],
                    row['health_benefit'],
                    row['nutrient_category'],
                    row['serving_size'],
                    row['serving_description'],
                    row['description']
                ))
            
            pg_cursor.executemany("""
                INSERT INTO health_specific_serving_sizes
                (ingredient, health_benefit, nutrient_category, serving_size, serving_description, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (ingredient, health_benefit, nutrient_category) DO NOTHING
            """, data)
            pg_conn.commit()
            inserted = pg_cursor.rowcount
            skipped = len(data) - inserted
            print(f"Inserted {inserted} rows, skipped {skipped} (already exist)")
        
        # Table 3: allergens
        print("\n=== allergens ===")
        sqlite_cursor.execute("""
            SELECT name, aliases, severity, description, common_in
            FROM allergens
        """)
        rows = sqlite_cursor.fetchall()
        print(f"Found {len(rows)} rows in SQLite")
        
        if rows:
            data = []
            for row in rows:
                data.append((
                    row['name'],
                    row['aliases'],
                    row['severity'],
                    row['description'],
                    row['common_in']
                ))
            
            pg_cursor.executemany("""
                INSERT INTO allergens
                (name, aliases, severity, description, common_in)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (name) DO NOTHING
            """, data)
            pg_conn.commit()
            inserted = pg_cursor.rowcount
            skipped = len(data) - inserted
            print(f"Inserted {inserted} rows, skipped {skipped} (already exist)")
        
        print("\n✅ Seeding completed successfully!")
        
    except Exception as e:
        print(f"\nERROR: Failed to seed data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        pg_conn.rollback()
        sys.exit(1)
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main()

