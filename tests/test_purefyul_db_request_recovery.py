"""Failure-path tests for PureFyul's pooled PostgreSQL request ownership.

All connections and pools are fakes: this suite never opens a database or
needs a DATABASE_URL. Tests use Flask's real request/teardown behavior.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, g
from psycopg.pq import TransactionStatus

import db


class FakeConnection:
    def __init__(self, *, bad=False):
        self.info = SimpleNamespace(transaction_status=(
            TransactionStatus.UNKNOWN if bad else TransactionStatus.IDLE
        ))
        self.rollback_calls = 0
        self.bad = bad

    def rollback(self):
        self.rollback_calls += 1
        if self.bad:
            raise RuntimeError("simulated disconnected PostgreSQL session")


class FakePool:
    def __init__(self):
        self.active = set()
        self.created = 0
        self.returned = 0

    def getconn(self):
        if len(self.active) >= 4:
            raise RuntimeError("simulated four-connection pool exhausted")
        connection = FakeConnection()
        self.active.add(connection)
        self.created += 1
        return connection

    def putconn(self, connection):
        if connection not in self.active:
            raise AssertionError("duplicate or foreign connection return")
        self.active.remove(connection)
        self.returned += 1


@pytest.fixture
def fake_pg_pool(monkeypatch):
    pool = FakePool()
    monkeypatch.setattr(db, "USE_POSTGRES", True)
    monkeypatch.setattr(db, "RUNTIME_DB_URL", "postgresql:///fake_test_db")
    monkeypatch.setattr(db, "_get_runtime_pg_pool", lambda *_: pool)
    return pool


def isolated_app():
    app = Flask("purefyul-db-recovery-test")
    app.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=False)

    @app.teardown_request
    def release_borrowed(_exception):
        db.reclaim_request_connections()

    return app


def test_repeated_failed_requests_do_not_exhaust_pool(fake_pg_pool):
    app = isolated_app()

    @app.get("/failure")
    def fails_after_borrow():
        db.get_conn()  # Intentionally no explicit close
        raise RuntimeError("simulated database query failure")

    with app.test_client() as client:
        for _ in range(24):
            response = client.get("/failure")
            assert response.status_code == 500
            assert len(fake_pg_pool.active) == 0

    assert fake_pg_pool.created == 24
    assert fake_pg_pool.returned == 24


def test_successful_but_leaking_route_is_reclaimed(fake_pg_pool):
    app = isolated_app()

    @app.get("/forget-close")
    def forget_close():
        db.get_conn()
        return "ok"

    response = app.test_client().get("/forget-close")
    assert response.status_code == 200
    assert fake_pg_pool.created == fake_pg_pool.returned == 1
    assert len(fake_pg_pool.active) == 0


def test_explicit_close_and_context_manager_return_only_once(fake_pg_pool):
    app = isolated_app()

    @app.get("/clean")
    def clean():
        first = db.get_conn()
        first.close()
        first.close()  # idempotence
        with db.get_conn():
            pass
        assert not g._purefyul_pg_leases
        return "ok"

    response = app.test_client().get("/clean")
    assert response.status_code == 200
    assert fake_pg_pool.created == fake_pg_pool.returned == 2
    assert len(fake_pg_pool.active) == 0


def test_failed_rollback_still_returns_to_pool(caplog):
    app = isolated_app()
    pool = FakePool()
    conn = FakeConnection(bad=True)
    pool.active.add(conn)

    @app.get("/bad")
    def bad_connection():
        db._track_request_lease(db._PooledPostgresConnection(pool, conn))
        raise RuntimeError("query failed")

    response = app.test_client().get("/bad")
    assert response.status_code == 500
    assert pool.returned == 1
    assert not pool.active
    assert "PSYCOPG_POOL=rollback_before_return_failed" in caplog.text


def test_no_request_is_noop():
    assert db.reclaim_request_connections() == 0


def test_real_application_registers_recovery_hook():
    source = Path(__file__).resolve().parents[1] / "startup_recovered.py"
    module = ast.parse(source.read_text())
    hooks = [
        f for f in module.body
        if isinstance(f, ast.FunctionDef)
        and f.name == "_return_orphaned_postgres_connections"
    ]
    assert len(hooks) == 1
    assert any(
        isinstance(d, ast.Attribute)
        and d.attr == "teardown_request"
        for d in hooks[0].decorator_list
    )
