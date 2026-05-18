"""
Blog posts table migration for PureFyul.
Run once on production Postgres via Render Shell.

Usage (Render Shell):
  cd /opt/render/project/src && python migrations/003_blog_posts.py
"""
import os
import sys


def run_migration():
    import psycopg

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]

    conn = psycopg.connect(db_url)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.blog_posts (
            id                  SERIAL PRIMARY KEY,
            slug                VARCHAR(200) UNIQUE NOT NULL,
            title               VARCHAR(300) NOT NULL,
            excerpt             VARCHAR(500),
            body_html           TEXT NOT NULL DEFAULT '',
            body_markdown       TEXT,
            cover_image_url     VARCHAR(500),
            category            VARCHAR(100) DEFAULT 'general',
            tags                TEXT[] DEFAULT '{}',
            author              VARCHAR(100) DEFAULT 'PureFyul Team',
            status              VARCHAR(20) DEFAULT 'draft',
            published_at        TIMESTAMPTZ,
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            updated_at          TIMESTAMPTZ DEFAULT NOW(),
            meta_title          VARCHAR(200),
            meta_description    VARCHAR(300),
            related_ingredients TEXT[] DEFAULT '{}',
            related_goals       TEXT[] DEFAULT '{}',
            reading_time_min    INT DEFAULT 5
        );
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS blog_slug_idx ON public.blog_posts(slug);")
    cur.execute("CREATE INDEX IF NOT EXISTS blog_status_pub_idx ON public.blog_posts(status, published_at DESC);")
    cur.execute("CREATE INDEX IF NOT EXISTS blog_category_idx ON public.blog_posts(category);")

    conn.commit()
    cur.close()
    conn.close()
    print("SUCCESS: blog_posts table created with indexes")


if __name__ == "__main__":
    run_migration()
