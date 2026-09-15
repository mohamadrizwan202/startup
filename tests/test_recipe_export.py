import io
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest


# ---------------------------------------------------------------------------
# HARD TEST ISOLATION
# ---------------------------------------------------------------------------

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

os.environ["ANTHROPIC_API_KEY"] = "test-only"
os.environ["DB_USE_RUNTIME_ROLE"] = "0"
os.environ["RUN_SCHEMA"] = "0"
os.environ["PF_DISABLE_RATELIMIT"] = "1"
os.environ["ENABLE_INTERNAL_ROUTES"] = "0"
os.environ["SECRET_KEY"] = "purefyul-recipe-export-tests-only"
os.environ["ENVIRONMENT"] = "test"
os.environ["FLASK_DEBUG"] = "0"

import db  # noqa: E402


_TEST_TMPDIR = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_TEST_TMPDIR.name) / "recipe_export_test.sqlite3"

import startup_recovered as appmod  # noqa: E402


TEST_USER = {
    "id": 30,
    "email": "recipe-export-test@example.com",
    "password_hash": "not-used",
    "created_at": "",
}


@pytest.fixture
def client(monkeypatch):
    appmod.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SECRET_KEY="purefyul-recipe-export-tests-only",
    )

    monkeypatch.setattr(
        appmod,
        "get_user_by_id",
        lambda user_id: TEST_USER if int(user_id) == TEST_USER["id"] else None,
    )

    monkeypatch.setattr(
        appmod,
        "get_user_plan",
        lambda user_id: "pro" if int(user_id) == TEST_USER["id"] else "free",
    )

    with appmod.app.test_client() as test_client:
        with test_client.session_transaction() as sess:
            sess["_user_id"] = str(TEST_USER["id"])
            sess["_fresh"] = True

        yield test_client


def _create_saved_recipes_table():
    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        conn.execute("DROP TABLE IF EXISTS saved_recipes")
        conn.execute(
            """
            CREATE TABLE saved_recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                ingredients TEXT NOT NULL,
                nutrition_summary TEXT,
                health_goal TEXT,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _xlsx_rows(response):
    assert response.status_code == 200
    assert response.content_type.startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    assert (
        "purefyul_recipes.xlsx"
        in response.headers.get("Content-Disposition", "")
    )

    raw = response.get_data()

    # XLSX files are ZIP archives.
    assert raw.startswith(b"PK")

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = set(archive.namelist())

        assert "xl/workbook.xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        assert "xl/styles.xml" in names

        shared_strings = []

        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(
                archive.read("xl/sharedStrings.xml")
            )

            ns = {
                "x": (
                    "http://schemas.openxmlformats.org/"
                    "spreadsheetml/2006/main"
                )
            }

            for si in root.findall("x:si", ns):
                parts = [
                    node.text or ""
                    for node in si.iter(
                        "{http://schemas.openxmlformats.org/"
                        "spreadsheetml/2006/main}t"
                    )
                ]
                shared_strings.append("".join(parts))

        sheet = ET.fromstring(
            archive.read("xl/worksheets/sheet1.xml")
        )

        ns = {
            "x": (
                "http://schemas.openxmlformats.org/"
                "spreadsheetml/2006/main"
            )
        }

        result = []

        for row in sheet.findall(".//x:sheetData/x:row", ns):
            values = []

            for cell in row.findall("x:c", ns):
                cell_type = cell.get("t")
                value_node = cell.find("x:v", ns)

                if value_node is None:
                    values.append("")
                    continue

                raw_value = value_node.text or ""

                if cell_type == "s":
                    values.append(
                        shared_strings[int(raw_value)]
                    )
                else:
                    try:
                        values.append(float(raw_value))
                    except ValueError:
                        values.append(raw_value)

            result.append(values)

        workbook_xml = archive.read("xl/workbook.xml").decode(
            "utf-8"
        )
        sheet_xml = archive.read(
            "xl/worksheets/sheet1.xml"
        ).decode("utf-8")

    return result, workbook_xml, sheet_xml


def test_recipe_export_excel_preserves_values_and_user_isolation(
    client,
    monkeypatch,
):
    monkeypatch.setattr(appmod.db, "USE_POSTGRES", False)

    _create_saved_recipes_table()

    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        conn.execute(
            """
            INSERT INTO saved_recipes
                (
                    user_id,
                    name,
                    ingredients,
                    nutrition_summary,
                    health_goal,
                    notes,
                    created_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                TEST_USER["id"],
                "Morning Smoothie",
                json.dumps([
                    {
                        "name": "Papaya",
                        "quantity": 110,
                        "unit": "g",
                    },
                    {
                        "name": "Oat milk",
                        "quantity": 150,
                        "unit": "mL",
                    },
                    {
                        "name": "Chia seeds",
                        "quantity": 10,
                        "unit": "g",
                    },
                ]),
                json.dumps({
                    "calories": 275.123456,
                    "protein": 12.56789,
                    "carbs": 42.111,
                    "fat": 8.222,
                    "fiber": 9.333,
                    "sugar": 18.444,
                }),
                "digestive-health",
                "For: Woman 19–30 | Timing: Breakfast",
                "2026-09-14 16:30:00",
            ),
        )

        # Different user: must not appear.
        conn.execute(
            """
            INSERT INTO saved_recipes
                (
                    user_id,
                    name,
                    ingredients,
                    nutrition_summary,
                    health_goal,
                    notes,
                    created_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                999,
                "Other User Smoothie",
                json.dumps([
                    {
                        "name": "Banana",
                        "quantity": 100,
                        "unit": "g",
                    }
                ]),
                json.dumps({"calories": 999}),
                "",
                "",
                "2026-09-14 16:31:00",
            ),
        )

        conn.commit()
    finally:
        conn.close()

    response = client.get("/api/recipes/export")
    rows, workbook_xml, sheet_xml = _xlsx_rows(response)

    assert rows[0] == [
        "Name",
        "Health Goal",
        "Audience",
        "Timing",
        "Ingredients",
        "Calories (kcal)",
        "Protein (g)",
        "Carbs (g)",
        "Fat (g)",
        "Fiber (g)",
        "Sugar (g)",
        "Saved On",
    ]

    assert len(rows) == 2

    row = rows[1]

    assert row[0] == "Morning Smoothie"
    assert row[1] == "Digestive Health"
    assert row[2] == "Woman 19–30"
    assert row[3] == "Breakfast"
    assert row[4] == (
        "• Papaya 110g\n"
        "• Oat milk 150mL\n"
        "• Chia seeds 10g"
    )

    # Workbook stores the real numbers; Excel formatting displays
    # them to one decimal place.
    assert row[5] == pytest.approx(275.123456)
    assert row[6] == pytest.approx(12.56789)
    assert row[7] == pytest.approx(42.111)
    assert row[8] == pytest.approx(8.222)
    assert row[9] == pytest.approx(9.333)
    assert row[10] == pytest.approx(18.444)

    workbook_text = response.get_data(as_text=False)

    assert b"Other User Smoothie" not in workbook_text

    # Workbook-level presentation contract.
    assert "Saved Smoothies" in workbook_xml

    # Frozen header row and autofilter must exist.
    assert "<pane" in sheet_xml
    assert 'ySplit="1"' in sheet_xml
    assert "<autoFilter" in sheet_xml


class FakePostgresCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed_sql = None
        self.executed_params = None

    def execute(self, sql, params):
        self.executed_sql = sql
        self.executed_params = params

    def fetchall(self):
        return self.rows


class FakePostgresConnection:
    def __init__(self, rows):
        self.cursor_instance = FakePostgresCursor(rows)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def test_recipe_export_accepts_postgres_jsonb_objects(
    client,
    monkeypatch,
):
    postgres_rows = [
        {
            "id": 1,
            "user_id": TEST_USER["id"],
            "name": "Postgres Smoothie",
            "ingredients": [
                {
                    "name": "Blueberry",
                    "quantity": 80,
                    "unit": "g",
                },
                {
                    "name": "Greek yogurt",
                    "quantity": 120,
                    "unit": "g",
                },
            ],
            "nutrition_summary": {
                "calories": 210,
                "protein": 18,
                "carbs": 24,
                "fat": 5,
                "fiber": 5,
                "sugar": 14,
            },
            "health_goal": "high-protein",
            "notes": "For: Man 19–30 | Timing: Post Workout",
            "created_at": "2026-09-14 16:31:00",
        }
    ]

    fake_conn = FakePostgresConnection(postgres_rows)

    monkeypatch.setattr(appmod.db, "USE_POSTGRES", True)
    monkeypatch.setattr(
        appmod.db,
        "get_conn",
        lambda: fake_conn,
    )

    response = client.get("/api/recipes/export")
    rows, _, _ = _xlsx_rows(response)

    assert len(rows) == 2

    row = rows[1]

    assert row[0] == "Postgres Smoothie"
    assert row[1] == "High Protein"
    assert row[2] == "Man 19–30"
    assert row[3] == "Post Workout"
    assert row[4] == (
        "• Blueberry 80g\n"
        "• Greek yogurt 120g"
    )

    assert row[5] == 210
    assert row[6] == 18
    assert row[7] == 24
    assert row[8] == 5
    assert row[9] == 5
    assert row[10] == 14

    assert (
        "WHERE user_id = %s"
        in fake_conn.cursor_instance.executed_sql
    )
    assert fake_conn.cursor_instance.executed_params == (
        TEST_USER["id"],
    )
    assert fake_conn.closed is True


def test_recipe_export_free_user_remains_blocked(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        appmod,
        "get_user_plan",
        lambda _user_id: "free",
    )

    response = client.get("/api/recipes/export")

    assert response.status_code == 403
    assert response.get_json()["error"] == "upgrade_required"
