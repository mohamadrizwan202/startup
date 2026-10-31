"""Create recipe-specific snapshots for personalized smoothies.

Each snapshot belongs to one existing generation ledger record.
This migration does not modify credit records or historical ingredients.

Migration functions accept an existing PostgreSQL cursor.
Database connection and execution are intentionally managed separately.
"""


def upgrade(cur):
    """Create the snapshot table without modifying the credit ledger."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS
            public.personalized_smoothie_recipe_snapshots (
                generation_id INTEGER PRIMARY KEY
                    REFERENCES public.personalized_smoothie_generations(id)
                    ON DELETE CASCADE,
                variant VARCHAR(40) NOT NULL,
                ingredient_selections JSONB NOT NULL,
                updated_at TIMESTAMP NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
        """
    )


def verify(cur):
    """Verify the expected snapshot columns."""
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'personalized_smoothie_recipe_snapshots'
        ORDER BY ordinal_position
        """
    )

    actual = [row[0] for row in cur.fetchall()]

    expected = [
        "generation_id",
        "variant",
        "ingredient_selections",
        "updated_at",
    ]

    if actual != expected:
        raise RuntimeError(
            "Unexpected personalized smoothie snapshot schema: "
            f"expected={expected!r}, actual={actual!r}"
        )


if __name__ == "__main__":
    raise SystemExit(
        "This migration must be executed through an explicitly "
        "approved database connection and transaction."
    )
