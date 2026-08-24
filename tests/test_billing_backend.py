import os
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# HARD TEST ISOLATION
#
# These values are set BEFORE importing db/startup_recovered so load_dotenv()
# cannot restore real production/service credentials from .env.
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
os.environ["SECRET_KEY"] = "purefyul-billing-tests-only"
os.environ["ENVIRONMENT"] = "test"
os.environ["FLASK_DEBUG"] = "0"

import db  # noqa: E402


_TEST_TMPDIR = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_TEST_TMPDIR.name) / "billing_test.sqlite3"

import startup_recovered as appmod  # noqa: E402


TEST_USER = {
    "id": 20,
    "email": "billing-test@example.com",
    "password_hash": "not-used",
    "created_at": "",
}


class FakeStripeObject:
    def __init__(self, data):
        self._data = dict(data)
        for key, value in data.items():
            setattr(self, key, value)

    def to_dict(self):
        return dict(self._data)


@pytest.fixture(autouse=True)
def isolated_subscription_db():
    assert appmod.db.USE_POSTGRES is False
    assert appmod.db.DB_PATH == db.DB_PATH

    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        conn.execute("DROP TABLE IF EXISTS subscriptions")
        conn.execute(
            """
            CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL,
                status TEXT NOT NULL,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                current_period_end TEXT,
                cancel_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX subscriptions_stripe_subscription_id_uidx
            ON subscriptions(stripe_subscription_id)
            WHERE stripe_subscription_id IS NOT NULL
              AND stripe_subscription_id <> ''
            """
        )
        conn.commit()
    finally:
        conn.close()

    yield


@pytest.fixture
def client(monkeypatch):
    appmod.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SECRET_KEY="purefyul-billing-tests-only",
    )

    monkeypatch.setattr(
        appmod,
        "get_user_by_id",
        lambda user_id: TEST_USER if int(user_id) == TEST_USER["id"] else None,
    )

    with appmod.app.test_client() as test_client:
        with test_client.session_transaction() as sess:
            sess["_user_id"] = str(TEST_USER["id"])
            sess["_fresh"] = True

        yield test_client


def _enable_fake_stripe(monkeypatch):
    monkeypatch.setattr(appmod, "STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setattr(
        appmod,
        "STRIPE_PRO_MONTHLY_PRICE_ID",
        "price_test_purefyul_pro",
    )


def test_custom_checkout_session_uses_elements_and_existing_metadata(
    client,
    monkeypatch,
):
    _enable_fake_stripe(monkeypatch)
    monkeypatch.setattr(appmod, "get_user_plan", lambda user_id: "free")

    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id="cs_test_custom",
            client_secret="cs_test_secret",
        )

    monkeypatch.setattr(
        appmod.stripe.checkout.Session,
        "create",
        fake_create,
    )

    response = client.post(
        "/billing/create-custom-checkout-session",
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"clientSecret": "cs_test_secret"}

    assert captured["ui_mode"] == "elements"
    assert captured["mode"] == "subscription"
    assert captured["payment_method_types"] == ["card"]
    assert captured["line_items"] == [
        {
            "price": "price_test_purefyul_pro",
            "quantity": 1,
        }
    ]
    assert captured["customer_email"] == TEST_USER["email"]
    assert captured["client_reference_id"] == str(TEST_USER["id"])
    assert captured["metadata"] == {
        "purefyul_user_id": str(TEST_USER["id"]),
        "purefyul_plan": "pro",
    }
    assert captured["subscription_data"]["metadata"] == captured["metadata"]
    assert "/pricing?checkout=success&session_id={CHECKOUT_SESSION_ID}" in (
        captured["return_url"]
    )


def test_custom_checkout_blocks_existing_pro_before_stripe(
    client,
    monkeypatch,
):
    _enable_fake_stripe(monkeypatch)
    monkeypatch.setattr(appmod, "get_user_plan", lambda user_id: "pro")

    called = {"stripe": False}

    def should_not_call(**kwargs):
        called["stripe"] = True
        raise AssertionError("Stripe must not be called for an existing Pro user")

    monkeypatch.setattr(
        appmod.stripe.checkout.Session,
        "create",
        should_not_call,
    )

    response = client.post(
        "/billing/create-custom-checkout-session",
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "Your account already has Pro access."
    assert called["stripe"] is False


def test_cancel_subscription_schedules_period_end_and_syncs(
    client,
    monkeypatch,
):
    _enable_fake_stripe(monkeypatch)

    monkeypatch.setattr(
        appmod,
        "_get_active_stripe_subscription_state",
        lambda user_id: {
            "stripe_subscription_id": "sub_test_active",
            "stripe_customer_id": "cus_test",
        },
    )

    captured = {}

    def fake_modify(subscription_id, **kwargs):
        captured["subscription_id"] = subscription_id
        captured.update(kwargs)
        return FakeStripeObject(
            {
                "id": subscription_id,
                "status": "active",
                "cancel_at_period_end": True,
            }
        )

    monkeypatch.setattr(appmod.stripe.Subscription, "modify", fake_modify)

    synced = {}

    def fake_sync(payload):
        synced.update(payload)
        return "updated"

    monkeypatch.setattr(appmod, "_sync_stripe_subscription", fake_sync)

    response = client.post(
        "/billing/cancel-subscription",
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.get_json()["scheduled"] is True
    assert captured == {
        "subscription_id": "sub_test_active",
        "cancel_at_period_end": True,
    }
    assert synced["id"] == "sub_test_active"
    assert synced["cancel_at_period_end"] is True


def test_resume_subscription_removes_period_end_cancellation(
    client,
    monkeypatch,
):
    _enable_fake_stripe(monkeypatch)

    monkeypatch.setattr(
        appmod,
        "_get_active_stripe_subscription_state",
        lambda user_id: {
            "stripe_subscription_id": "sub_test_active",
            "stripe_customer_id": "cus_test",
        },
    )

    captured = {}

    def fake_modify(subscription_id, **kwargs):
        captured["subscription_id"] = subscription_id
        captured.update(kwargs)
        return FakeStripeObject(
            {
                "id": subscription_id,
                "status": "active",
                "cancel_at_period_end": False,
            }
        )

    monkeypatch.setattr(appmod.stripe.Subscription, "modify", fake_modify)
    monkeypatch.setattr(
        appmod,
        "_sync_stripe_subscription",
        lambda payload: "updated",
    )

    response = client.post(
        "/billing/resume-subscription",
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.get_json()["resumed"] is True
    assert captured == {
        "subscription_id": "sub_test_active",
        "cancel_at_period_end": False,
    }


def test_cancel_returns_404_without_stripe_subscription(
    client,
    monkeypatch,
):
    _enable_fake_stripe(monkeypatch)

    monkeypatch.setattr(
        appmod,
        "_get_active_stripe_subscription_state",
        lambda user_id: None,
    )

    def should_not_call(*args, **kwargs):
        raise AssertionError("Stripe must not be called without billing state")

    monkeypatch.setattr(appmod.stripe.Subscription, "modify", should_not_call)

    response = client.post(
        "/billing/cancel-subscription",
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 404
    assert "No active Stripe subscription" in response.get_json()["error"]


def test_webhook_rejects_invalid_signature(client, monkeypatch):
    monkeypatch.setattr(appmod, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    def invalid_event(*args, **kwargs):
        raise ValueError("invalid signature")

    monkeypatch.setattr(
        appmod.stripe.Webhook,
        "construct_event",
        invalid_event,
    )

    response = client.post(
        "/billing/stripe-webhook",
        data=b"{}",
        headers={"Stripe-Signature": "bad-signature"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_webhook"}


def test_updated_webhook_retrieves_current_subscription_before_sync(
    client,
    monkeypatch,
):
    monkeypatch.setattr(appmod, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    event = SimpleNamespace(
        id="evt_test_updated",
        type="customer.subscription.updated",
        data=SimpleNamespace(
            object=FakeStripeObject({"id": "sub_test_current"})
        ),
    )

    monkeypatch.setattr(
        appmod.stripe.Webhook,
        "construct_event",
        lambda *args, **kwargs: event,
    )

    retrieved = {"id": None}

    def fake_retrieve(subscription_id):
        retrieved["id"] = subscription_id
        return FakeStripeObject(
            {
                "id": subscription_id,
                "status": "active",
                "customer": "cus_test",
            }
        )

    monkeypatch.setattr(
        appmod.stripe.Subscription,
        "retrieve",
        fake_retrieve,
    )

    synced = {}

    def fake_sync(payload):
        synced.update(payload)
        return "updated"

    monkeypatch.setattr(appmod, "_sync_stripe_subscription", fake_sync)

    response = client.post(
        "/billing/stripe-webhook",
        data=b"{}",
        headers={"Stripe-Signature": "test-signature"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"received": True}
    assert retrieved["id"] == "sub_test_current"
    assert synced["id"] == "sub_test_current"
    assert synced["status"] == "active"


def test_deleted_webhook_uses_signed_deleted_state_without_retrieve(
    client,
    monkeypatch,
):
    monkeypatch.setattr(appmod, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    event = SimpleNamespace(
        id="evt_test_deleted",
        type="customer.subscription.deleted",
        data=SimpleNamespace(
            object=FakeStripeObject(
                {
                    "id": "sub_test_deleted",
                    "status": "active",
                    "customer": "cus_test",
                }
            )
        ),
    )

    monkeypatch.setattr(
        appmod.stripe.Webhook,
        "construct_event",
        lambda *args, **kwargs: event,
    )

    def should_not_retrieve(*args, **kwargs):
        raise AssertionError(
            "Deleted webhook must not retrieve and overwrite signed deleted state"
        )

    monkeypatch.setattr(
        appmod.stripe.Subscription,
        "retrieve",
        should_not_retrieve,
    )

    synced = {}

    def fake_sync(payload):
        synced.update(payload)
        return "updated"

    monkeypatch.setattr(appmod, "_sync_stripe_subscription", fake_sync)

    response = client.post(
        "/billing/stripe-webhook",
        data=b"{}",
        headers={"Stripe-Signature": "test-signature"},
    )

    assert response.status_code == 200
    assert synced["id"] == "sub_test_deleted"
    assert synced["status"] == "canceled"


def test_subscription_sync_inserts_then_updates_single_stripe_row(monkeypatch):
    monkeypatch.setattr(
        appmod,
        "_stripe_subscription_has_pro_price",
        lambda subscription: True,
    )
    monkeypatch.setattr(
        appmod,
        "_stripe_subscription_period_end",
        lambda subscription: 1800000000,
    )

    initial = {
        "id": "sub_test_sync",
        "status": "active",
        "customer": "cus_test_sync",
        "metadata": {
            "purefyul_user_id": str(TEST_USER["id"]),
            "purefyul_plan": "pro",
        },
        "cancel_at_period_end": False,
    }

    assert appmod._sync_stripe_subscription(initial) == "inserted"

    updated = dict(initial)
    updated["status"] = "canceled"
    updated["cancel_at"] = 1800000000

    assert appmod._sync_stripe_subscription(updated) == "updated"

    conn = sqlite3.connect(str(db.DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM subscriptions
            WHERE stripe_subscription_id = ?
            """,
            ("sub_test_sync",),
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0]["user_id"] == TEST_USER["id"]
    assert rows[0]["plan"] == "pro"
    assert rows[0]["status"] == "canceled"
    assert rows[0]["stripe_customer_id"] == "cus_test_sync"
    assert rows[0]["cancel_at"] is not None


def test_subscription_sync_ignores_unmapped_new_subscription(monkeypatch):
    monkeypatch.setattr(
        appmod,
        "_stripe_subscription_has_pro_price",
        lambda subscription: True,
    )

    payload = {
        "id": "sub_test_unmapped",
        "status": "active",
        "customer": "cus_test",
        "metadata": {
            "purefyul_user_id": str(TEST_USER["id"]),
            "purefyul_plan": "free",
        },
    }

    assert appmod._sync_stripe_subscription(payload) == "ignored"

    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM subscriptions
            WHERE stripe_subscription_id = ?
            """,
            ("sub_test_unmapped",),
        ).fetchone()[0]
    finally:
        conn.close()

    assert count == 0


def test_pricing_uses_current_period_end_for_customer_label(
    client,
    monkeypatch,
):
    monkeypatch.setattr(appmod, "get_user_plan", lambda user_id: "pro")
    monkeypatch.setattr(
        appmod,
        "_get_active_stripe_subscription_state",
        lambda user_id: {
            "stripe_customer_id": "cus_test",
            "stripe_subscription_id": "sub_test",
            "current_period_end": "2026-09-23T22:07:15",
            "cancel_at": None,
        },
    )

    captured = {}

    def fake_render(template_name, **context):
        captured["template"] = template_name
        captured.update(context)
        return "pricing-test"

    monkeypatch.setattr(appmod, "render_template", fake_render)

    response = client.get("/pricing")

    assert response.status_code == 200
    assert captured["template"] == "pricing.html"
    assert captured["pricing_user_plan"] == "pro"
    assert captured["has_stripe_billing"] is True
    assert captured["pricing_cancel_at"] is None
    assert captured["pricing_period_end_label"] == "September 23, 2026"

def test_pricing_template_uses_custom_checkout_and_manage_pro():
    template_path = (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "pricing.html"
    )
    template = template_path.read_text()

    assert "create_portal_session" not in template
    assert "url_for('pro_checkout')" in template

    # Cancellation must not be advertised directly on Pricing.
    assert "cancel_pro_subscription" not in template
    assert "resume_pro_subscription" not in template

    assert "url_for('manage_pro')" in template
    assert "Manage Pro" in template



def test_portal_route_removed_and_hosted_checkout_fallback_retained():
    routes = {rule.rule for rule in appmod.app.url_map.iter_rules()}

    assert "/billing/create-portal-session" not in routes

    # Custom flow is the user-facing path.
    assert "/billing/checkout" in routes
    assert "/billing/create-custom-checkout-session" in routes
    assert "/billing/cancel-subscription" in routes
    assert "/billing/resume-subscription" in routes

    # Keep the proven hosted route as an unused fallback for now.
    assert "/billing/create-checkout-session" in routes


def test_manage_pro_active_subscription_context(client, monkeypatch):
    monkeypatch.setattr(
        appmod,
        "get_user_plan",
        lambda user_id: "pro",
    )

    monkeypatch.setattr(
        appmod,
        "_get_active_stripe_subscription_state",
        lambda user_id: {
            "stripe_customer_id": "cus_test",
            "stripe_subscription_id": "sub_test",
            "status": "active",
            "current_period_end": "2026-09-23T22:07:15",
            "cancel_at": None,
        },
    )

    captured = {}

    def fake_render(template_name, **context):
        captured["template"] = template_name
        captured.update(context)
        return "manage-pro-test"

    monkeypatch.setattr(
        appmod,
        "render_template",
        fake_render,
    )

    response = client.get("/billing/manage")

    assert response.status_code == 200
    assert captured["template"] == "manage_pro.html"
    assert captured["subscription_status"] == "Active"
    assert captured["cancellation_scheduled"] is False
    assert captured["period_end_label"] == "September 23, 2026"
    assert captured["show_cancel_confirmation"] is False


def test_manage_pro_cancel_confirmation_is_explicit(client, monkeypatch):
    monkeypatch.setattr(
        appmod,
        "get_user_plan",
        lambda user_id: "pro",
    )

    monkeypatch.setattr(
        appmod,
        "_get_active_stripe_subscription_state",
        lambda user_id: {
            "stripe_customer_id": "cus_test",
            "stripe_subscription_id": "sub_test",
            "status": "active",
            "current_period_end": "2026-09-23T22:07:15",
            "cancel_at": None,
        },
    )

    captured = {}

    monkeypatch.setattr(
        appmod,
        "render_template",
        lambda template_name, **context: (
            captured.update(
                {"template": template_name, **context}
            )
            or "manage-pro-confirm-test"
        ),
    )

    response = client.get(
        "/billing/manage?confirm_cancel=1"
    )

    assert response.status_code == 200
    assert captured["show_cancel_confirmation"] is True
    assert captured["cancellation_scheduled"] is False


def test_manage_pro_scheduled_cancel_state(client, monkeypatch):
    monkeypatch.setattr(
        appmod,
        "get_user_plan",
        lambda user_id: "pro",
    )

    monkeypatch.setattr(
        appmod,
        "_get_active_stripe_subscription_state",
        lambda user_id: {
            "stripe_customer_id": "cus_test",
            "stripe_subscription_id": "sub_test",
            "status": "active",
            "current_period_end": "2026-09-23T22:07:15",
            "cancel_at": "2026-09-23T22:07:15",
        },
    )

    captured = {}

    monkeypatch.setattr(
        appmod,
        "render_template",
        lambda template_name, **context: (
            captured.update(
                {"template": template_name, **context}
            )
            or "manage-pro-scheduled-test"
        ),
    )

    response = client.get("/billing/manage")

    assert response.status_code == 200
    assert captured["cancellation_scheduled"] is True
    assert captured["cancel_at_label"] == "September 23, 2026"
    assert captured["show_cancel_confirmation"] is False


def test_manage_pro_route_exists():
    routes = {
        rule.rule
        for rule in appmod.app.url_map.iter_rules()
    }

    assert "/billing/manage" in routes
