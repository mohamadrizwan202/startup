"""
Database connection and schema management.
Supports both PostgreSQL (production) and SQLite (local dev).
"""
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

# Detect database type
# Support for runtime vs migrate roles (least-privilege)
# If DB_USE_RUNTIME_ROLE=1, use DATABASE_URL_RUNTIME for runtime operations
# Otherwise, fall back to DATABASE_URL (backward compatible)
USE_RUNTIME_ROLE = os.getenv("DB_USE_RUNTIME_ROLE", "").strip().lower() in ("1", "true", "yes", "on")
DATABASE_URL_RUNTIME = os.getenv("DATABASE_URL_RUNTIME", "")
DATABASE_URL_MIGRATE = os.getenv("DATABASE_URL_MIGRATE", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Determine which URL to use for runtime operations
if USE_RUNTIME_ROLE and DATABASE_URL_RUNTIME:
    RUNTIME_DB_URL = DATABASE_URL_RUNTIME
else:
    RUNTIME_DB_URL = DATABASE_URL

USE_POSTGRES = bool(RUNTIME_DB_URL and (RUNTIME_DB_URL.startswith("postgres://") or RUNTIME_DB_URL.startswith("postgresql://")))

# SQLite path (local dev only)
if not USE_POSTGRES:
    BASE_DIR = Path(__file__).parent
    DB_PATH = BASE_DIR / "allergen_nutrition.db"


def normalize_pg_url(url: str) -> str:
    """
    Normalize PostgreSQL URL:
    - Convert postgres:// to postgresql://
    - Set sslmode based on hostname (disable for localhost, require for remote)
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    
    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query))
    
    # If sslmode is already set, don't change it
    if "sslmode" not in query_params:
        hostname = parsed.hostname or ""
        if hostname in ("localhost", "127.0.0.1", "::1"):
            query_params["sslmode"] = "disable"
        else:
            query_params["sslmode"] = "require"
    
    # Reconstruct URL with updated query params
    new_query = urlencode(query_params)
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


def get_conn():
    """
    Get database connection - single source of truth.
    Returns PostgreSQL connection if DATABASE_URL is set, otherwise SQLite.
    PostgreSQL connections use dict_row factory so rows are already dictionaries.
    Uses DATABASE_URL_RUNTIME if DB_USE_RUNTIME_ROLE=1, else falls back to DATABASE_URL.
    """
    if USE_POSTGRES:
        import psycopg  # pyright: ignore[reportMissingImports]
        from psycopg.rows import dict_row  # pyright: ignore[reportMissingImports]
        normalized_url = normalize_pg_url(RUNTIME_DB_URL)
        conn = psycopg.connect(normalized_url, row_factory=dict_row, connect_timeout=5)
        return conn
    else:
        # SQLite fallback (local dev only)
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn


def get_migrate_conn():
    """
    Get database connection for migrations/schema changes.
    Uses DATABASE_URL_MIGRATE if set, otherwise falls back to get_conn().
    This allows migrations to use a higher-privilege role (app_migrate) while
    runtime operations use a least-privilege role (app_runtime).
    """
    migrate_url = DATABASE_URL_MIGRATE or RUNTIME_DB_URL
    if migrate_url and (migrate_url.startswith("postgres://") or migrate_url.startswith("postgresql://")):
        import psycopg  # pyright: ignore[reportMissingImports]
        from psycopg.rows import dict_row  # pyright: ignore[reportMissingImports]
        normalized_url = normalize_pg_url(migrate_url)
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


def is_truthy(value):
    """
    Helper to interpret common truthy strings from the environment.
    Returns True for: '1', 'true', 'yes', 'on' (case-insensitive).
    """
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def ensure_schema():
    """
    Create users table if it doesn't exist (idempotent).
    Works with both PostgreSQL and SQLite.
    Always commits changes for both database types.
    Uses migrate connection if available (for schema changes).
    
    Only executes DDL when ENABLE_DB_MIGRATIONS is truthy.
    When disabled, assumes tables already exist (production mode).
    """
    # Prevent runtime DDL in production unless explicitly enabled
    if not is_truthy(os.getenv("ENABLE_DB_MIGRATIONS", "0")):
        return
    
    # Use migrate connection for schema changes if available
    conn = get_migrate_conn() if DATABASE_URL_MIGRATE else get_conn()
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
        
        # Create nutrition_facts table for both Postgres and SQLite
        if USE_POSTGRES:
            # PostgreSQL schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nutrition_facts (
                    id SERIAL PRIMARY KEY,
                    ingredient VARCHAR(255) UNIQUE NOT NULL,
                    calories_per_100g REAL,
                    protein REAL,
                    carbs REAL,
                    fat REAL,
                    fiber REAL,
                    sugar REAL,
                    sodium REAL,
                    serving_size REAL,
                    vitamins TEXT,
                    minerals TEXT
                )
            """)
        else:
            # SQLite schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nutrition_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ingredient TEXT UNIQUE NOT NULL,
                    calories_per_100g REAL,
                    protein REAL,
                    carbs REAL,
                    fat REAL,
                    fiber REAL,
                    sugar REAL,
                    sodium REAL,
                    serving_size REAL,
                    vitamins TEXT,
                    minerals TEXT
                )
            """)
        
        # Always commit schema changes for both Postgres and SQLite
        conn.commit()
    finally:
        conn.close()

