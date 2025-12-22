#!/usr/bin/env python3
"""
Seed Postgres nutrition_facts table from local SQLite file.

This script reads nutrition_facts data from the SQLite file (allergen_nutrition.db) and
upserts it into the Postgres database. Missing columns are added automatically if needed.

Usage:
    DB_URL="postgresql://..." python3 scripts/seed_nutrition_facts_from_sqlite.py

Or with custom SQLite path:
    SQLITE_PATH="path/to/db.db" DB_URL="postgresql://..." python3 scripts/seed_nutrition_facts_from_sqlite.py

Or with DATABASE_URL_RUNTIME:
    DATABASE_URL_RUNTIME="postgresql://..." python3 scripts/seed_nutrition_facts_from_sqlite.py

Environment variables:
    SQLITE_PATH: Path to SQLite database file (default: "allergen_nutrition.db")
    DB_URL: PostgreSQL connection URL (preferred, also checks DATABASE_URL, DATABASE_URL_RUNTIME)
    DATABASE_URL: Fallback for DB_URL if DB_URL is not set
    DATABASE_URL_RUNTIME: Additional fallback option
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


def ensure_columns_exist(pg_cursor, pg_conn):
    """
    Ensure required columns exist in Postgres nutrition_facts table.
    Adds columns if they don't exist (idempotent).
    """
    columns_to_add = [
        ("fiber_g", "numeric"),
        ("sugar_g", "numeric"),
        ("sodium_g", "numeric"),
        ("serving_size_g", "numeric"),
        ("vitamins", "text"),
        ("minerals", "text"),
    ]
    
    for column_name, column_type in columns_to_add:
        try:
            pg_cursor.execute(f"""
                ALTER TABLE nutrition_facts 
                ADD COLUMN IF NOT EXISTS {column_name} {column_type}
            """)
            pg_conn.commit()
            print(f"  ✅ Column {column_name} exists or was added")
        except Exception as e:
            print(f"  ⚠️  Warning: Could not add column {column_name}: {e}", file=sys.stderr)
            pg_conn.rollback()


def main():
    # Read configuration from environment
    sqlite_path = os.getenv("SQLITE_PATH", "allergen_nutrition.db")
    pg_url = os.getenv("DB_URL") or os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_RUNTIME")
    
    if not pg_url:
        print("ERROR: DB_URL, DATABASE_URL, or DATABASE_URL_RUNTIME environment variable must be set", file=sys.stderr)
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
        # Ensure required columns exist in Postgres table
        print("\n=== Ensuring Postgres columns exist ===")
        ensure_columns_exist(pg_cursor, pg_conn)
        
        # Read nutrition_facts from SQLite
        print("\n=== nutrition_facts ===")
        sqlite_cursor.execute("""
            SELECT 
                ingredient,
                calories_per_100g,
                protein,
                carbs,
                fat,
                fiber,
                sugar,
                sodium,
                serving_size,
                vitamins,
                minerals
            FROM nutrition_facts
        """)
        rows = sqlite_cursor.fetchall()
        print(f"Found {len(rows)} rows in SQLite")
        
        if not rows:
            print("No rows to migrate")
            return
        
        # Convert SQLite rows to tuples for executemany
        data = []
        for row in rows:
            data.append((
                row['ingredient'],
                row['calories_per_100g'],
                row['protein'],
                row['carbs'],
                row['fat'],
                row['fiber'],
                row['sugar'],
                row['sodium'],
                row['serving_size'],
                row['vitamins'],
                row['minerals']
            ))
        
        print(f"Attempting to upsert {len(data)} rows into Postgres...")
        
        # Upsert with ON CONFLICT DO UPDATE
        # Note: Postgres has UNIQUE constraint/index on lower(ingredient)
        # If using expression-based unique index, may need ON CONFLICT ON CONSTRAINT constraint_name instead
        pg_cursor.executemany("""
            INSERT INTO nutrition_facts 
            (ingredient, calories, protein_g, carbs_g, fat_g, 
             fiber_g, sugar_g, sodium_g, serving_size_g, vitamins, minerals)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lower(ingredient)) 
            DO UPDATE SET
                calories = EXCLUDED.calories,
                protein_g = EXCLUDED.protein_g,
                carbs_g = EXCLUDED.carbs_g,
                fat_g = EXCLUDED.fat_g,
                fiber_g = EXCLUDED.fiber_g,
                sugar_g = EXCLUDED.sugar_g,
                sodium_g = EXCLUDED.sodium_g,
                serving_size_g = EXCLUDED.serving_size_g,
                vitamins = EXCLUDED.vitamins,
                minerals = EXCLUDED.minerals
        """, data)
        pg_conn.commit()
        
        # Note: executemany returns rowcount for the last executed statement only
        # So we report the number attempted
        print(f"✅ Upserted {len(data)} rows (new inserts + updates)")
        print(f"   (Postgres rowcount may vary; re-run to verify all rows are present)")
        
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

