-- ============================================================================
-- Set Default Privileges for Future Tables/Sequences
-- ============================================================================
-- This script sets default privileges so that future tables/sequences created
-- by the app_migrate role will automatically grant appropriate permissions to app_runtime.
--
-- IMPORTANT: This script MUST be run while connected as the app_migrate role.
-- Running as a superuser/admin will NOT work because default privileges are
-- role-specific and must be set by the role that will create the objects.
--
-- Usage:
--   1. Set ADMIN_DATABASE_URL to use app_migrate role:
--      export ADMIN_DATABASE_URL="postgresql://dbname_user:password@host:port/dbname?user=app_migrate"
--      OR use DATABASE_URL_MIGRATE if it's already configured with app_migrate
--   2. Run: python ops/run_sql.py ops/db_default_privileges.sql
--
-- ============================================================================

-- Set default privileges for future tables created by app_migrate
-- This ensures app_runtime gets CRUD access to any new tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime;

-- Set default privileges for future sequences created by app_migrate
-- This ensures app_runtime can use sequences (for SERIAL columns)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO app_runtime;

-- ============================================================================
-- Verification (optional - uncomment to check)
-- ============================================================================
-- SELECT 
--     defaclrole::regrole as role_name,
--     defaclnamespace::regnamespace as schema,
--     defaclobjtype as object_type,
--     defaclacl as privileges
-- FROM pg_default_acl
-- WHERE defaclrole = 'app_migrate'::regrole
--     AND defaclnamespace = 'public'::regnamespace;
-- ============================================================================

