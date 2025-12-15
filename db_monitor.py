"""
Database health monitoring module.
Runs periodic health checks in a background thread.
"""
import os
import time
import threading
import logging
from datetime import datetime, timezone

# Import database connection logic
import db

logger = logging.getLogger(__name__)

# Module-level variable to store last health check result
LAST_DB_STATUS = None


def probe_db():
    """
    Probe database health by running a simple SELECT 1 query.
    Returns dict with db_type, ok, checked_at, latency_ms, error.
    Never raises exceptions - always returns a result dict.
    """
    start_time = time.time()
    checked_at = datetime.now(timezone.utc).isoformat()
    
    try:
        # Determine DB type
        db_type = "postgres" if db.USE_POSTGRES else "sqlite"
        
        # Get connection (uses existing db.get_conn() with timeout)
        conn = db.get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            return {
                "db_type": db_type,
                "ok": True,
                "checked_at": checked_at,
                "latency_ms": latency_ms,
                "error": None
            }
        except Exception as e:
            # Close connection if open
            try:
                conn.close()
            except:
                pass
            raise e
            
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        error_str = str(e)
        
        # Determine DB type even on error
        db_type = "postgres" if db.USE_POSTGRES else "sqlite"
        
        return {
            "db_type": db_type,
            "ok": False,
            "checked_at": checked_at,
            "latency_ms": latency_ms,
            "error": error_str
        }


def _monitor_loop(interval_seconds):
    """Internal monitoring loop that runs in background thread"""
    global LAST_DB_STATUS
    
    while True:
        try:
            status = probe_db()
            LAST_DB_STATUS = status
            
            if status["ok"]:
                logger.info("DB_HEALTH=ok db_type=%s latency_ms=%d", 
                           status["db_type"], status["latency_ms"])
            else:
                logger.info("DB_HEALTH=fail error=%s", status["error"])
                
        except Exception as e:
            # Even probe_db can theoretically fail in edge cases, so catch everything
            logger.error("DB_HEALTH monitor exception: %s", str(e))
            LAST_DB_STATUS = {
                "db_type": "unknown",
                "ok": False,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "latency_ms": 0,
                "error": f"Monitor exception: {str(e)}"
            }
        
        time.sleep(interval_seconds)


def start_db_monitor():
    """
    Start background database health monitoring thread.
    Only starts if ENABLE_DB_MONITOR=1 environment variable is set.
    """
    enable_monitor = os.getenv("ENABLE_DB_MONITOR", "0").strip()
    if enable_monitor not in ("1", "true", "yes", "on"):
        logger.info("DB_MONITOR=disabled (ENABLE_DB_MONITOR not set to 1)")
        return
    
    interval_str = os.getenv("DB_MONITOR_INTERVAL_SECONDS", "60")
    try:
        interval_seconds = int(interval_str)
        if interval_seconds < 1:
            interval_seconds = 60
    except ValueError:
        interval_seconds = 60
    
    logger.info("DB_MONITOR=starting interval_seconds=%d", interval_seconds)
    
    # Start background thread (daemon=True so it doesn't block shutdown)
    monitor_thread = threading.Thread(
        target=_monitor_loop,
        args=(interval_seconds,),
        daemon=True,
        name="db_monitor"
    )
    monitor_thread.start()
    logger.info("DB_MONITOR=started")

