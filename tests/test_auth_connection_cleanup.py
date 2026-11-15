"""PureFyul auth connection cleanup regression tests (no DB connection)."""
import ast
from pathlib import Path
import logging
import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "startup_recovered.py"


class _MockCursor:
    def __init__(self, fail_at=None, row=None):
        self.fail_at = fail_at
        self.row = row

    def execute(self, *_args):
        if self.fail_at == "execute":
            raise RuntimeError("synthetic cursor failure")

    def fetchone(self):
        if self.fail_at == "fetchone":
            raise RuntimeError("synthetic fetch failure")
        return self.row


class _MockConnection:
    def __init__(self, fail_at=None, row=None):
        self.fail_at = fail_at
        self.row = row
        self.close_count = 0

    def cursor(self):
        if self.fail_at == "cursor":
            raise RuntimeError("synthetic cursor creation failure")
        return _MockCursor(self.fail_at, self.row)

    def close(self):
        self.close_count += 1


class _FakeDB:
    @staticmethod
    def prepare_query(query):
        return query

    @staticmethod
    def row_to_dict(row, cursor):
        return dict(row)


def _isolated_auth_function(name, conn, conversion_fails=False):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    funcs = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(funcs) == 1
    func = funcs[0]
    tree = ast.fix_missing_locations(ast.Module(body=[func], type_ignores=[]))
    db = _FakeDB()
    if conversion_fails:
        def fail_conversion(_row, _cursor):
            raise RuntimeError("synthetic conversion failure")
        db.row_to_dict = fail_conversion
    namespace = {"get_conn": lambda: conn, "db": db, "logging": logging}
    exec(compile(tree, str(SOURCE), "exec"), namespace)
    return namespace[name]


@pytest.mark.parametrize("name,argument", [
    ("get_user_by_id", 42),
    ("get_user_by_email", "qa@example.com"),
])
@pytest.mark.parametrize("scenario", [
    "found", "missing", "cursor", "execute", "fetchone", "conversion",
])
def test_auth_db_connection_always_closed(name, argument, scenario):
    row = {"id": 42} if scenario in ("found", "conversion") else None
    conn = _MockConnection(
        fail_at=scenario if scenario in ("cursor", "execute", "fetchone") else None,
        row=row,
    )
    fn = _isolated_auth_function(
        name, conn, conversion_fails=scenario == "conversion"
    )
    value = fn(argument)
    assert value == {"id": 42} if scenario == "found" else value is None
    assert conn.close_count == 1


def test_pool_trace_is_opt_in():
    source = (ROOT / "db.py").read_text(encoding="utf-8")
    assert 'os.getenv("PF_DB_POOL_TRACE") == "1"' in source
    assert "PSYCOPG_POOL=borrow" in source
    assert "PSYCOPG_POOL=returned" in source
