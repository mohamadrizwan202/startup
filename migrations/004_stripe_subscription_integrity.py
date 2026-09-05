"""
Stripe subscription integrity migration for PureFyul.

Purpose:
- Store Stripe's scheduled cancellation timestamp when present.
- Prevent the same Stripe subscription from being stored more than once.
- Preserve existing manual Pro rows where stripe_subscription_id IS NULL.

Run once on production Postgres via Render Shell:

  cd /opt/render/project/src
  python migrations/004_stripe_subscription_integrity.py
"""

import os
import sys

import psycopg


def run_migration():
    db_url = os.environ.get("DATABASE_URL", "").strip()

    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]

    conn = psycopg.connect(db_url)

    try:
        cur = conn.cursor()

        # Store Stripe's scheduled cancellation timestamp.
        # NULL means there is no scheduled cancellation.
        cur.execute("""
            ALTER TABLE public.subscriptions
            ADD COLUMN IF NOT EXISTS cancel_at TIMESTAMP
        """)

        # Safety check: do not create the unique index if bad historical
        # Stripe data already exists.
        cur.execute("""
            SELECT stripe_subscription_id, COUNT(*)
            FROM public.subscriptions
            WHERE stripe_subscription_id IS NOT NULL
              AND stripe_subscription_id <> ''
            GROUP BY stripe_subscription_id
            HAVING COUNT(*) > 1
        """)

        duplicates = cur.fetchall()

        if duplicates:
            print("ERROR: duplicate Stripe subscription IDs already exist:")
            for subscription_id, count in duplicates:
                print(f"  {subscription_id}: {count} rows")

            conn.rollback()
            sys.exit(1)

        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                subscriptions_stripe_subscription_id_uidx
            ON public.subscriptions (stripe_subscription_id)
            WHERE stripe_subscription_id IS NOT NULL
              AND stripe_subscription_id <> ''
        """)

        conn.commit()

        print(
            "SUCCESS: Stripe subscription cancellation timestamp and "
            "integrity index are ready"
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
