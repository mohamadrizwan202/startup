"""
Database connection and schema management.
Supports both PostgreSQL (production) and SQLite (local dev).
"""
import atexit
import logging
import os
import sqlite3
import threading
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

_logger = logging.getLogger(__name__)

_RUNTIME_PG_POOL = None
_RUNTIME_PG_POOL_LOCK = threading.Lock()


class _PooledPostgresConnection:
    def __init__(self, pool, connection):
        self._pool = pool
        self._connection = connection

    def __getattr__(self, name):
        connection = self._connection
        if connection is None:
            raise RuntimeError("PostgreSQL connection is already closed")
        return getattr(connection, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        connection = self._connection
        if connection is None:
            return
        self._connection = None
        try:
            from psycopg.pq import TransactionStatus
            if connection.info.transaction_status != TransactionStatus.IDLE:
                connection.rollback()
        except Exception:
            _logger.warning(
                "PSYCOPG_POOL=rollback_before_return_failed",
                exc_info=True,
            )
        finally:
            self._pool.putconn(connection)


def _get_runtime_pg_pool(normalized_url, dict_row):
    global _RUNTIME_PG_POOL

    pool = _RUNTIME_PG_POOL
    if pool is not None:
        return pool

    with _RUNTIME_PG_POOL_LOCK:
        pool = _RUNTIME_PG_POOL
        if pool is not None:
            return pool

        from psycopg_pool import ConnectionPool

        # A per-borrow health query measured about 462 ms here, nearly
        # erasing pooling benefits. Idle connections are instead bounded.
        pool = ConnectionPool(
            conninfo=normalized_url,
            kwargs={"row_factory": dict_row, "connect_timeout": 5},
            min_size=0,
            max_size=4,
            timeout=5,
            max_idle=60,
            open=False,
        )
        pool.open()
        _RUNTIME_PG_POOL = pool
        _logger.info(
            "PSYCOPG_POOL=enabled max_size=4 max_idle_seconds=60"
        )
        return pool


def _close_runtime_pg_pool():
    global _RUNTIME_PG_POOL

    with _RUNTIME_PG_POOL_LOCK:
        pool = _RUNTIME_PG_POOL
        _RUNTIME_PG_POOL = None

    if pool is not None:
        try:
            pool.close()
        except Exception:
            _logger.exception("PSYCOPG_POOL=close_failed")


atexit.register(_close_runtime_pg_pool)

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
        # Handle local Unix socket URLs (postgresql:/// or postgres:///) without normalization
        if RUNTIME_DB_URL.startswith("postgresql:///") or RUNTIME_DB_URL.startswith("postgres:///"):
            normalized_url = RUNTIME_DB_URL
        else:
            normalized_url = normalize_pg_url(RUNTIME_DB_URL)
        pool = _get_runtime_pg_pool(normalized_url, dict_row)
        return _PooledPostgresConnection(pool, pool.getconn())
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
        # Handle local Unix socket URLs (postgresql:/// or postgres:///) without normalization
        if migrate_url.startswith("postgresql:///") or migrate_url.startswith("postgres:///"):
            normalized_url = migrate_url
        else:
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
        
        # Add password reset columns if they do not exist
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN reset_token TEXT")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN reset_token_expiry TEXT")
        except Exception:
            pass

        # USER PERSONALIZATION PROFILE
        # Store raw profile inputs only.
        # BMI and estimated daily calorie requirement are derived later.
        #
        # Canonical measurement storage:
        #   height_cm
        #   weight_kg
        #
        # preferred_*_unit controls input/display only.
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id INTEGER PRIMARY KEY
                        REFERENCES users(id) ON DELETE CASCADE,
                    sex TEXT,
                    age INTEGER,
                    height_cm DOUBLE PRECISION,
                    weight_kg DOUBLE PRECISION,
                    activity_level TEXT,
                    pregnancy_lactation_status TEXT CHECK (
                        pregnancy_lactation_status IS NULL
                        OR pregnancy_lactation_status IN (
                            'neither',
                            'pregnant',
                            'lactating',
                            'prefer_not_to_say'
                        )
                    ),
                    preferred_height_unit TEXT NOT NULL DEFAULT 'cm',
                    preferred_weight_unit TEXT NOT NULL DEFAULT 'kg',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    CONSTRAINT user_profiles_sex_valid
                        CHECK (sex IS NULL OR sex IN ('female', 'male')),
                    CONSTRAINT user_profiles_activity_level_valid
                        CHECK (
                            activity_level IS NULL
                            OR activity_level IN (
                                'inactive',
                                'low_active',
                                'active',
                                'very_active'
                            )
                        ),
                    CONSTRAINT user_profiles_age_supported
                        CHECK (age IS NULL OR age >= 4),
                    CONSTRAINT user_profiles_height_positive
                        CHECK (height_cm IS NULL OR height_cm > 0),
                    CONSTRAINT user_profiles_weight_positive
                        CHECK (weight_kg IS NULL OR weight_kg > 0),
                    CONSTRAINT user_profiles_height_unit_valid
                        CHECK (preferred_height_unit IN ('cm', 'ft_in')),
                    CONSTRAINT user_profiles_weight_unit_valid
                        CHECK (preferred_weight_unit IN ('kg', 'lb'))
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id INTEGER PRIMARY KEY
                        REFERENCES users(id) ON DELETE CASCADE,
                    sex TEXT,
                    age INTEGER,
                    height_cm REAL,
                    weight_kg REAL,
                    activity_level TEXT,
                    pregnancy_lactation_status TEXT CHECK (
                        pregnancy_lactation_status IS NULL
                        OR pregnancy_lactation_status IN (
                            'neither',
                            'pregnant',
                            'lactating',
                            'prefer_not_to_say'
                        )
                    ),
                    preferred_height_unit TEXT NOT NULL DEFAULT 'cm',
                    preferred_weight_unit TEXT NOT NULL DEFAULT 'kg',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    CHECK (sex IS NULL OR sex IN ('female', 'male')),
                    CHECK (
                        activity_level IS NULL
                        OR activity_level IN (
                            'inactive',
                            'low_active',
                            'active',
                            'very_active'
                        )
                    ),
                    CHECK (age IS NULL OR age >= 4),
                    CHECK (height_cm IS NULL OR height_cm > 0),
                    CHECK (weight_kg IS NULL OR weight_kg > 0),
                    CHECK (preferred_height_unit IN ('cm', 'ft_in')),
                    CHECK (preferred_weight_unit IN ('kg', 'lb'))
                )
            """)

        # Add pregnancy/lactation safety field to existing profiles.
        # This field only controls standard-EER eligibility.
        # Pregnancy/lactation EER calculations are intentionally not
        # implemented here.
        if USE_POSTGRES:
            cursor.execute("""
                ALTER TABLE user_profiles
                ADD COLUMN IF NOT EXISTS pregnancy_lactation_status TEXT
                CHECK (
                    pregnancy_lactation_status IS NULL
                    OR pregnancy_lactation_status IN (
                        'neither',
                        'pregnant',
                        'lactating',
                        'prefer_not_to_say'
                    )
                )
            """)
        else:
            cursor.execute("PRAGMA table_info(user_profiles)")
            profile_columns = {
                row[1] for row in cursor.fetchall()
            }
            if "pregnancy_lactation_status" not in profile_columns:
                cursor.execute("""
                    ALTER TABLE user_profiles
                    ADD COLUMN pregnancy_lactation_status TEXT
                    CHECK (
                        pregnancy_lactation_status IS NULL
                        OR pregnancy_lactation_status IN (
                            'neither',
                            'pregnant',
                            'lactating',
                            'prefer_not_to_say'
                        )
                    )
                """)

        # Account health goals are chosen during registration and shown on the
        # signed-in preset screen. They are intentionally separate from
        # user_profiles, persons, and personalized smoothie credit usage.
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_health_goal_preferences (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL
                        REFERENCES users(id) ON DELETE CASCADE,
                    category_value VARCHAR(255) NOT NULL,
                    display_order SMALLINT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

                    CONSTRAINT user_health_goal_preferences_category_not_blank
                        CHECK (BTRIM(category_value) <> ''),
                    CONSTRAINT user_health_goal_preferences_display_order_valid
                        CHECK (display_order BETWEEN 1 AND 6),
                    CONSTRAINT user_health_goal_preferences_user_category_unique
                        UNIQUE (user_id, category_value),
                    CONSTRAINT user_health_goal_preferences_user_order_unique
                        UNIQUE (user_id, display_order)
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_health_goal_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL
                        REFERENCES users(id) ON DELETE CASCADE,
                    category_value TEXT NOT NULL,
                    display_order INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                    CHECK (TRIM(category_value) <> ''),
                    CHECK (display_order BETWEEN 1 AND 6),
                    UNIQUE (user_id, category_value),
                    UNIQUE (user_id, display_order)
                )
            """)

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
        

        # ── WEB SAAS PERSONALIZATION: PERSONS ─────────────────────────────
        # Consumer web personalization only.
        # Keep separate from the B2B/app user_profiles system.
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS persons (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name VARCHAR(100) NOT NULL,
                    is_default BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT persons_name_not_blank
                        CHECK (BTRIM(name) <> '')
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS persons_user_id_idx
                ON persons(user_id)
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS persons_one_default_per_user_uidx
                ON persons(user_id)
                WHERE is_default = TRUE
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS persons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK (TRIM(name) <> ''),
                    CHECK (is_default IN (0, 1))
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS persons_user_id_idx
                ON persons(user_id)
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS persons_one_default_per_user_uidx
                ON persons(user_id)
                WHERE is_default = 1
            """)

        # ── WEB PERSONALIZATION: PERSON PREFERENCES ────────────────────────
        # Consumer web personalization only.
        # Keep separate from the app profile system.
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS person_preferences (
                    id SERIAL PRIMARY KEY,
                    person_id INTEGER NOT NULL
                        REFERENCES persons(id) ON DELETE CASCADE,
                    goal_slug VARCHAR(100) NOT NULL,
                    timing_slug VARCHAR(100),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    person_preferences_person_id_uidx
                ON person_preferences(person_id)
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS person_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id INTEGER NOT NULL
                        REFERENCES persons(id) ON DELETE CASCADE,
                    goal_slug TEXT NOT NULL,
                    timing_slug TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    person_preferences_person_id_uidx
                ON person_preferences(person_id)
            """)

        # ── WEB PERSONALIZATION: PERSON INGREDIENT PREFERENCES ────────────
        # Preferred/avoid choices use reviewed-preset ingredient IDs.
        # Keep separate from the app profile system.
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS person_ingredient_preferences (
                    id SERIAL PRIMARY KEY,
                    person_id INTEGER NOT NULL
                        REFERENCES persons(id) ON DELETE CASCADE,
                    ingredient_id VARCHAR(100) NOT NULL,
                    preference_type VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT person_ingredient_preferences_id_not_blank
                        CHECK (BTRIM(ingredient_id) <> ''),
                    CONSTRAINT person_ingredient_preferences_type_valid
                        CHECK (
                            preference_type IN (
                                'preferred',
                                'avoid'
                            )
                        )
                )
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    person_ingredient_preferences_person_ingredient_uidx
                ON person_ingredient_preferences(
                    person_id,
                    ingredient_id
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS person_ingredient_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id INTEGER NOT NULL
                        REFERENCES persons(id) ON DELETE CASCADE,
                    ingredient_id TEXT NOT NULL,
                    preference_type TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK (TRIM(ingredient_id) <> ''),
                    CHECK (
                        preference_type IN (
                            'preferred',
                            'avoid'
                        )
                    )
                )
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    person_ingredient_preferences_person_ingredient_uidx
                ON person_ingredient_preferences(
                    person_id,
                    ingredient_id
                )
            """)

        # ── WEB PERSONALIZATION: GENERATION LEDGER ────────────────────────
        # Records successful personalized smoothie generations.
        # Free-trial quota is account-wide and counts only free_trial rows.
        # Person deletion preserves usage history by setting person_id NULL.
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS personalized_smoothie_generations (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL
                        REFERENCES users(id) ON DELETE CASCADE,
                    person_id INTEGER
                        REFERENCES persons(id) ON DELETE SET NULL,
                    goal_slug VARCHAR(100) NOT NULL,
                    timing_slug VARCHAR(100) NOT NULL,
                    access_type VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    personalization_id UUID,
                    CONSTRAINT personalized_generations_goal_not_blank
                        CHECK (BTRIM(goal_slug) <> ''),
                    CONSTRAINT personalized_generations_timing_not_blank
                        CHECK (BTRIM(timing_slug) <> ''),
                    CONSTRAINT personalized_generations_access_type_valid
                        CHECK (access_type IN ('free_trial', 'pro'))
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS
                    personalized_generations_user_access_created_idx
                ON personalized_smoothie_generations (
                    user_id,
                    access_type,
                    created_at DESC
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS personalized_smoothie_generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL
                        REFERENCES users(id) ON DELETE CASCADE,
                    person_id INTEGER
                        REFERENCES persons(id) ON DELETE SET NULL,
                    goal_slug TEXT NOT NULL,
                    timing_slug TEXT NOT NULL,
                    access_type TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    personalization_id TEXT,
                    CHECK (TRIM(goal_slug) <> ''),
                    CHECK (TRIM(timing_slug) <> ''),
                    CHECK (access_type IN ('free_trial', 'pro'))
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS
                    personalized_generations_user_access_created_idx
                ON personalized_smoothie_generations (
                    user_id,
                    access_type,
                    created_at DESC
                )
            """)

        # Durable identity for one editable personalized smoothie.
        # Existing rows remain valid quota history but have no editable ID.
        if USE_POSTGRES:
            cursor.execute("""
                ALTER TABLE personalized_smoothie_generations
                ADD COLUMN IF NOT EXISTS personalization_id UUID
            """)
        else:
            cursor.execute(
                "PRAGMA table_info(personalized_smoothie_generations)"
            )
            generation_columns = {
                row[1] for row in cursor.fetchall()
            }
            if "personalization_id" not in generation_columns:
                cursor.execute("""
                    ALTER TABLE personalized_smoothie_generations
                    ADD COLUMN personalization_id TEXT
                """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                personalized_generations_personalization_id_uidx
            ON personalized_smoothie_generations (
                personalization_id
            )
            WHERE personalization_id IS NOT NULL
        """)

        # ── SAVED RECIPES TABLE ──────────────────────────────────────────
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS saved_recipes (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    ingredients JSONB NOT NULL,
                    nutrition_summary JSONB,
                    health_goal VARCHAR(100),
                    timing VARCHAR(100),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS saved_recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    ingredients TEXT NOT NULL,
                    nutrition_summary TEXT,
                    health_goal TEXT,
                    timing TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # ── SMOOTHIE HISTORY TABLE (auto-logged, logged-in users only) ────
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS smoothie_history (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    ingredients JSONB NOT NULL,
                    nutrition_summary JSONB,
                    audience VARCHAR(50),
                    timing VARCHAR(50),
                    health_goal VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS smoothie_history_user_idx
                ON smoothie_history(user_id, created_at DESC)
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS smoothie_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    ingredients TEXT NOT NULL,
                    nutrition_summary TEXT,
                    audience TEXT,
                    timing TEXT,
                    health_goal TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # ── MEAL PLANS TABLE ─────────────────────────────────────────────
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meal_plans (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    week_start DATE,
                    slots JSONB NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meal_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    week_start TEXT,
                    slots TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # ── SUBSCRIPTIONS TABLE ──────────────────────────────────────────
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    plan VARCHAR(50) NOT NULL DEFAULT 'free',
                    status VARCHAR(50) NOT NULL DEFAULT 'active',
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    current_period_end TIMESTAMP,
                    cancel_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    plan TEXT NOT NULL DEFAULT 'free',
                    status TEXT NOT NULL DEFAULT 'active',
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    current_period_end TEXT,
                    cancel_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # Upgrade an existing local SQLite subscriptions table if needed.
        if not USE_POSTGRES:
            try:
                cursor.execute(
                    "ALTER TABLE subscriptions "
                    "ADD COLUMN cancel_at TEXT"
                )
            except sqlite3.OperationalError:
                # Column already exists.
                pass

        # Always commit schema changes for both Postgres and SQLite
        conn.commit()
    finally:
        conn.close()

