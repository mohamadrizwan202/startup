-- Reviewed ingredient bounds for Tune My Smoothie.
--
-- This table stores product-policy data only.
-- It does not store nutrition composition and does not define serving science.
--
-- No production ingredient rules are inserted by this migration.

CREATE TABLE public.ingredient_tuning_rules (
    nutrition_lookup_name TEXT PRIMARY KEY
        CHECK (BTRIM(nutrition_lookup_name) <> ''),

    min_weight_g DOUBLE PRECISION,
    max_weight_g DOUBLE PRECISION,

    source_type TEXT,
    source_reference TEXT,
    rationale TEXT,

    review_status TEXT NOT NULL DEFAULT 'draft',
    enabled BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ingredient_tuning_rules_min_positive
        CHECK (
            min_weight_g IS NULL
            OR min_weight_g > 0
        ),

    CONSTRAINT ingredient_tuning_rules_max_positive
        CHECK (
            max_weight_g IS NULL
            OR max_weight_g > 0
        ),

    CONSTRAINT ingredient_tuning_rules_range_order
        CHECK (
            min_weight_g IS NULL
            OR max_weight_g IS NULL
            OR min_weight_g <= max_weight_g
        )
);

-- Protect the repository's normalized exact-lookup contract.
-- "mango", " MANGO ", etc. cannot coexist as separate rules.
CREATE UNIQUE INDEX ingredient_tuning_rules_normalized_name_uidx
ON public.ingredient_tuning_rules (
    LOWER(BTRIM(nutrition_lookup_name))
);

-- Runtime may read approved policy data but must not edit it.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'app_runtime'
    ) THEN
        REVOKE INSERT, UPDATE, DELETE
        ON TABLE public.ingredient_tuning_rules
        FROM app_runtime;

        GRANT SELECT
        ON TABLE public.ingredient_tuning_rules
        TO app_runtime;
    END IF;
END
$$;

-- Migration/admin role may maintain reviewed policy data when present.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'app_migrate'
    ) THEN
        GRANT SELECT, INSERT, UPDATE, DELETE
        ON TABLE public.ingredient_tuning_rules
        TO app_migrate;
    END IF;
END
$$;
