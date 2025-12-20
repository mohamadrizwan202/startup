# Database Restore Runbook (pg_dump / pg_restore)

## Purpose
Restore the Flask app database from a `pg_dump` custom-format backup file:
`backup_YYYY-MM-DD_HHMM.dump`

This is used for:
- dropped tables / bad migrations
- accidental deletes / corruption
- rebuild to a known-good state

## Key Reality
- Restoring from a dump returns DB state to the **backup timestamp** (RPO = time since last backup).
- On free Render Postgres you can't create a second free DB, so hosted restore drills are limited.

## Tools
All commands use Postgres 18 client tools installed in conda env `pg18`:
`conda run -n pg18 ...`

---

## Quick Decision Tree
- **Need real production recovery** → Path A (restore into a NEW hosted Postgres, then cut over DB_URL)
- **Free Render drill / verification** → Path B (restore locally and verify)

---

## Step 0 — Pick which dump to restore
From repo root:

```bash
cd /Users/hadiyamaan/Desktop/New_Project
latest="$(ls -t backup_*.dump 2>/dev/null | head -n 1)"
echo "Using dump: $latest"
```

---

## Path A: Restore to Hosted Postgres (Production/Target Host)

### Prerequisites
- `TARGET_DB_URL` environment variable set (e.g., `postgresql://user:pass@host:5432/dbname`)
- Backup file available (e.g., `backup_2024-01-15_1430.dump`)
- Postgres 18 client tools available

### Steps

```bash
# 1. Set target database URL
export TARGET_DB_URL="postgresql://user:pass@host:5432/dbname"

# 2. Restore from backup file
conda run -n pg18 pg_restore \
  -d "$TARGET_DB_URL" \
  --verbose \
  --clean \
  --if-exists \
  backup_2024-01-15_1430.dump

# 3. Verify restore (tables + row count)
conda run -n pg18 psql "$TARGET_DB_URL" -c "\dt"  # List tables
conda run -n pg18 psql "$TARGET_DB_URL" -c "SELECT COUNT(*) FROM public.users;"
```

### Verification Checklist
- [ ] `\dt` shows expected tables (users, etc.)
- [ ] `SELECT COUNT(*) FROM public.users;` returns expected row count
- [ ] App `/__health` endpoint returns 200
- [ ] App `/dbcheck` endpoint (with token) returns 200 (DB reachable).
- [ ] Test login with a known user account

---

## Path B: Restore Locally (Free Tier Drill)

### Prerequisites
- Local Postgres instance running on port 5433
- Backup file available
- Conda environment `pg18` activated

### Steps

```bash
# 1. Start local Postgres instance (if not running)
conda run -n pg18 pg_ctl -D .pgdata_restore -l pg_restore_drill.log \
  -o "-p 5433 -h 127.0.0.1" start

# 2. Create database (if needed)
conda run -n pg18 createdb -h 127.0.0.1 -p 5433 myapp_restore

# 3. Restore from backup file
conda run -n pg18 pg_restore \
  -h 127.0.0.1 \
  -p 5433 \
  -d myapp_restore \
  --verbose \
  --clean \
  --if-exists \
  backup_2024-01-15_1430.dump

# 4. Verify restore
conda run -n pg18 psql -h 127.0.0.1 -p 5433 -d myapp_restore -c "\dt"
conda run -n pg18 psql -h 127.0.0.1 -p 5433 -d myapp_restore -c "SELECT COUNT(*) FROM public.users;"
```

### Verification Checklist
- [ ] Tables exist (`\dt` shows users table)
- [ ] Row count matches backup source
- [ ] Can connect: `psql -h 127.0.0.1 -p 5433 -d myapp_restore`

---

## Incident Triage Checklist

Before restoring, assess the situation:

- [ ] **Confirm data loss**: Is this a confirmed data corruption/loss, or a false alarm?
- [ ] **Check backups**: List available backup files, verify most recent backup timestamp
- [ ] **Check application logs**: Review Render logs for error patterns
- [ ] **Verify database connectivity**: Test `/__health` and `/dbcheck` endpoints
- [ ] **Check database status**: Is Postgres instance running and accessible?
- [ ] **Identify scope**: Full database restore needed, or specific table(s)?
- [ ] **Notify stakeholders**: If production incident, communicate impact and timeline

---

## Post-Restore Checklist

After successful restore:

- [ ] **Data verification**: Spot-check critical tables (users, sessions, etc.)
- [ ] **Application smoke test**: Login, create record, verify functionality
- [ ] **Monitor logs**: Watch for errors in first 5-10 minutes post-restore
- [ ] **Verify backups**: Confirm backup schedule is still running
- [ ] **Document incident**: Record what happened, restore time, data loss window (if any)
- [ ] **Update runbook**: Add any lessons learned or procedure improvements

---

## Common Errors & Solutions

### Version Mismatch
**Error**: `pg_restore: error: input file appears to be a text format dump. Please use psql.`

**Solution**: Use `pg_restore` for custom format (`.dump`), `psql` for plain text dumps.

---

### Connection: Socket vs Host

**Error**: `could not connect to server: No such file or directory`

**Problem**: Using Unix socket instead of TCP connection.

**Solution**: Always use `-h 127.0.0.1` for local connections, or full connection string for remote:
```bash
# Correct for local
conda run -n pg18 psql -h 127.0.0.1 -p 5433 -d dbname

# Correct for remote (via URL)
conda run -n pg18 psql "postgresql://user:pass@host:5432/dbname"
```

---

### Port in Use

**Error**: `FATAL: database files are incompatible with server` or `address already in use`

**Problem**: Port 5433 already in use, or Postgres version mismatch.

**Solution**:
```bash
# Check if port is in use
lsof -i :5433

# Stop existing instance
conda run -n pg18 pg_ctl -D .pgdata_restore stop

# Restart with correct port
conda run -n pg18 pg_ctl -D .pgdata_restore -o "-p 5433 -h 127.0.0.1" start
```

---

### Permission Denied

**Error**: `permission denied for schema public` or `must be owner of database`

**Solution**: Restore as superuser, or grant necessary privileges:
```bash
# Restore as superuser (if local)
conda run -n pg18 psql -h 127.0.0.1 -p 5433 -U postgres -d myapp_restore

# For hosted databases, use admin/migrate role connection string
```

---

## Notes

- **Free Render limitation**: Free tier allows only one Postgres database. For restore drills, use local Postgres instance.
- **Backup location**: Backups are created by `db_backup.sh` (assume stored in project root or backup directory)
- **Connection strings**: Never commit real URLs/passwords. Use environment variables.
- **Rollback plan**: If restore fails, original database should still be intact (pg_restore uses transactions where possible).
