import ast
import os
import sqlite3
import tempfile
from pathlib import Path


# Keep this module isolated from real runtime credentials and databases.
for key in (
    "DATABASE_URL",
    "DATABASE_URL_RUNTIME",
    "DATABASE_URL_MIGRATE",
    "STRIPE_SECRET_KEY",
    "STRIPE_PUBLISHABLE_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRO_MONTHLY_PRICE_ID",
    "REDIS_URL",
    "RENDER",
):
    os.environ[key] = ""

os.environ["ENABLE_DB_MIGRATIONS"] = "1"
os.environ["DB_USE_RUNTIME_ROLE"] = "0"

import db


_TEST_TMPDIR = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_TEST_TMPDIR.name) / "registration_health_goals.sqlite3"
db.USE_POSTGRES = False

if hasattr(db, "DATABASE_URL_MIGRATE"):
    db.DATABASE_URL_MIGRATE = ""
if hasattr(db, "RUNTIME_DB_URL"):
    db.RUNTIME_DB_URL = ""

db.ensure_schema()


def _load_health_goal_helpers():
    source_path = Path("startup_recovered.py")
    source_tree = ast.parse(source_path.read_text(encoding="utf-8"))

    wanted_assignments = {"ACCOUNT_HEALTH_GOAL_COUNT"}
    wanted_functions = {
        "_validate_account_health_goal_selection",
        "_insert_account_health_goal_preferences",
    }
    selected_nodes = []
    found = set()

    for node in source_tree.body:
        if isinstance(node, ast.Assign):
            assigned_names = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if assigned_names & wanted_assignments:
                selected_nodes.append(node)
                found.update(assigned_names & wanted_assignments)
        elif (
            isinstance(node, ast.FunctionDef)
            and node.name in wanted_functions
        ):
            selected_nodes.append(node)
            found.add(node.name)

    expected = wanted_assignments | wanted_functions
    assert found == expected

    helper_module = ast.Module(
        body=selected_nodes,
        type_ignores=[],
    )
    ast.fix_missing_locations(helper_module)

    namespace = {"db": db}
    exec(
        compile(
            helper_module,
            filename=str(source_path),
            mode="exec",
        ),
        namespace,
    )
    return namespace


def test_health_goal_helpers_reject_invalid_values_and_persist_six():
    helpers = _load_health_goal_helpers()
    required_count = helpers["ACCOUNT_HEALTH_GOAL_COUNT"]
    validate = helpers["_validate_account_health_goal_selection"]
    insert_preferences = helpers[
        "_insert_account_health_goal_preferences"
    ]

    selected_goals = [
        f"goal-{position}"
        for position in range(1, required_count + 1)
    ]
    catalog = [
        {"value": value, "label": value.title()}
        for value in selected_goals
    ]

    valid, error = validate(selected_goals, catalog)
    assert error is None
    assert valid == selected_goals

    invalid_count, count_error = validate(selected_goals[:-1], catalog)
    assert invalid_count is None
    assert count_error == f"Choose exactly {required_count} health goals."

    duplicate, duplicate_error = validate(
        selected_goals[:-1] + [selected_goals[0]],
        catalog,
    )
    assert duplicate is None
    assert duplicate_error == "Choose six different health goals."

    forged, forged_error = validate(
        selected_goals[:-1] + ["not-a-real-goal"],
        catalog,
    )
    assert forged is None
    assert forged_error == "Choose only the health goals shown on this page."

    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            ("six-valid-goals@example.com", "test-hash"),
        )
        user_id = cursor.lastrowid

        insert_preferences(cursor, user_id, valid)
        conn.commit()

        rows = cursor.execute(
            """
            SELECT category_value, display_order
            FROM user_health_goal_preferences
            WHERE user_id = ?
            ORDER BY display_order
            """,
            (user_id,),
        ).fetchall()

        assert rows == [
            (goal, display_order)
            for display_order, goal in enumerate(
                selected_goals,
                start=1,
            )
        ]
    finally:
        conn.close()
