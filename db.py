"""
Database connection and schema management.
Supports both PostgreSQL (production) and SQLite (local dev).
"""
import os
import sqlite3
from pathlib import Path

# Detect database type
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))

# SQLite path (local dev only)
if not USE_POSTGRES:
    BASE_DIR = Path(__file__).parent
    DB_PATH = BASE_DIR / "allergen_nutrition.db"


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


def get_conn():
    """
    Get database connection - single source of truth.
    Returns PostgreSQL connection if DATABASE_URL is set, otherwise SQLite.
    PostgreSQL connections use dict_row factory so rows are already dictionaries.
    """
    if USE_POSTGRES:
        import psycopg  # pyright: ignore[reportMissingImports]
        from psycopg.rows import dict_row  # pyright: ignore[reportMissingImports]
        normalized_url = normalize_pg_url(DATABASE_URL)
        conn = psycopg.connect(normalized_url, row_factory=dict_row, connect_timeout=5)
        return conn
    else:
        # SQLite fallback (local dev only)
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn


def row_to_dict(row, cursor=None):
    """
    Convert database row to dict.
    PostgreSQL rows are already dicts (via dict_row factory).
    SQLite rows need conversion from sqlite3.Row.
    """
    if isinstance(row, sqlite3.Row):
        return {key: row[key] for key in row.keys()}
    else:
        # PostgreSQL rows are already dictionaries (dict_row factory)
        return row if isinstance(row, dict) else dict(row)


def prepare_query(query):
    """
    Convert SQLite-style ? placeholders to PostgreSQL %s placeholders if needed.
    """
    if USE_POSTGRES and "?" in query:
        return query.replace("?", "%s")
    return query


def execute_query(query, params=None):
    """
    Execute a query and return results.
    Handles both SQLite (?) and PostgreSQL (%s) placeholders.
    """
    conn = get_conn()
    try:
        cursor = conn.cursor()
        # Convert ? to %s for PostgreSQL
        if USE_POSTGRES and "?" in query:
            query = query.replace("?", "%s")
        cursor.execute(query, params or ())
        results = cursor.fetchall()
        conn.commit()
        return results
    finally:
        conn.close()


def ensure_schema():
    """
    Create users table if it doesn't exist (idempotent).
    Works with both PostgreSQL and SQLite.
    Always commits changes for both database types.
    """
    conn = get_conn()
    try:
        cursor = conn.cursor()
        
        if USE_POSTGRES:
            # PostgreSQL schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    active_session_token TEXT
                )
            """)
        else:
            # SQLite schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    active_session_token TEXT
                )
            """)
            
            # Add active_session_token column if it doesn't exist (migration for existing databases)
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN active_session_token TEXT")
            except sqlite3.OperationalError:
                # Column already exists, ignore
                pass
        
        # Always commit schema changes for both Postgres and SQLite
        conn.commit()
    finally:
        conn.close()

