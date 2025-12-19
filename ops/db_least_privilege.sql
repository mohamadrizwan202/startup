-- ============================================================================
-- Database Least-Privilege Setup for PostgreSQL
-- ============================================================================
-- This script creates two Postgres roles with least-privilege permissions:
--   1. app_runtime: For application runtime (CRUD only, no schema changes)
--   2. app_migrate: For migrations/schema changes (CREATE, ALTER, DROP)
--
-- Usage:
--   1. Connect as a superuser/admin (e.g., Render external database URL) to your database
--   2. Run this script: python ops/run_sql.py ops/db_least_privilege.sql
--   3. After roles are created, run: python ops/run_sql.py ops/db_default_privileges.sql
--      (connect as app_migrate role via DATABASE_URL_MIGRATE)
--   4. Update your DATABASE_URL_RUNTIME to use app_runtime role
--   5. Update your DATABASE_URL_MIGRATE to use app_migrate role (for migrations)
--
-- ============================================================================

-- Step 1: Create roles (idempotent - safe to rerun)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_runtime') THEN
        CREATE ROLE app_runtime;
        RAISE NOTICE 'Role app_runtime created.';
    ELSE
        RAISE NOTICE 'Role app_runtime already exists, skipping.';
    END IF;
    
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_migrate') THEN
        CREATE ROLE app_migrate;
        RAISE NOTICE 'Role app_migrate created.';
    ELSE
        RAISE NOTICE 'Role app_migrate already exists, skipping.';
    END IF;
END
$$;

-- Step 2: Revoke all privileges by default (principle of least privilege)
-- Note: CONNECT revokes must use dynamic SQL because current_database() can't be used in static GRANT
DO $$
DECLARE
    dbname text := current_database();
BEGIN
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM app_runtime', dbname);
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM app_migrate', dbname);
END
$$;

REVOKE ALL ON SCHEMA public FROM app_runtime;
REVOKE ALL ON SCHEMA public FROM app_migrate;

-- Step 3: Grant basic connection and schema usage
-- CONNECT grants must use dynamic SQL (current_database() can't be used in static GRANT)
DO $$
DECLARE
    dbname text := current_database();
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO app_runtime', dbname);
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO app_migrate', dbname);
END
$$;

GRANT USAGE ON SCHEMA public TO app_runtime;
GRANT USAGE ON SCHEMA public TO app_migrate;

-- Step 4: Grant runtime role CRUD permissions on existing tables
-- (These grants apply to tables that already exist)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_runtime;

-- Step 5: Grant runtime role sequence usage (for SERIAL columns)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_runtime;

-- Step 6: Grant migrate role full permissions (for schema changes)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_migrate;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_migrate;
GRANT CREATE ON SCHEMA public TO app_migrate;

-- ============================================================================
-- IMPORTANT: Default privileges must be set separately by app_migrate role
-- ============================================================================
-- After running this script, you MUST run ops/db_default_privileges.sql
-- while connected as the app_migrate role to set default privileges for
-- future tables/sequences created by migrations.
--
-- Command:
--   export ADMIN_DATABASE_URL="postgresql://...app_migrate:password@..."
--   python ops/run_sql.py ops/db_default_privileges.sql
--
-- ============================================================================

-- ============================================================================
-- Notes:
-- ============================================================================
-- - app_runtime should be used for normal application operations (DATABASE_URL_RUNTIME)
-- - app_migrate should be used only for migrations/schema changes (DATABASE_URL_MIGRATE)
-- - If you need to create new tables, use app_migrate role
-- - Default privileges ensure future tables created by app_migrate are accessible to app_runtime
-- ============================================================================
