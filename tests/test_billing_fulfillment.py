"""No network or charges: signed webhook and purchase transaction regressions."""
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import os
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TEST_MODE"] = "true"
os.environ["OPENAI_API_KEY"] = ""
os.environ["SESSION_COOKIE_SECURE"] = "false"

import app as module
import billing_fulfillment as billing
import stripe_service
import stripe_webhooks
from db import Base, SessionLocal, engine
from models import Tenant, User
from subscription_models import CheckoutFulfillment, PaymentHistory, PendingSignup, TenantSubscription
from stripe_config import STRIPE_PRODUCTS, STRIPE_PRICE_LOOKUP_KEYS


def checkout(tier="pro", paid="paid", customer="cus_test", session="cs_test"):
    price = {"id": "price_test", "product": STRIPE_PRODUCTS[tier], "lookup_key": STRIPE_PRICE_LOOKUP_KEYS[tier]["monthly"]}
    return {"id": session, "status": "complete", "payment_status": paid, "customer": customer,
            "customer_details": {"email": "buyer@example.com"}, "amount_total": 12900, "currency": "usd",
            "line_items": {"data": [{"price": price, "quantity": 1}], "has_more": False},
            "subscription": {"id": "sub_test", "customer": customer, "status": "active",
                             "items": {"data": [{"price": price, "quantity": 1}]}}, "metadata": {}}


class BillingFulfillmentTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(engine)
        db = SessionLocal()
        pending = PendingSignup(email="buyer@example.com", plan_tier="ultra", billing_cycle="yearly",
                                company_name="Test & Company!", full_name="Test Buyer", password_hash="stored-hash",
                                expires_at=datetime.utcnow() + timedelta(days=1))
        db.add(pending); db.commit(); db.close()
        self.key = patch("stripe_config.STRIPE_SECRET_KEY", "sk_test_synthetic")
        self.key.start()
        self.email = patch.object(stripe_webhooks, "_send_welcome_email")
        self.email.start()

    def tearDown(self):
        self.email.stop(); self.key.stop()
        SessionLocal.remove(); Base.metadata.drop_all(engine); engine.dispose()

    def fulfill(self, data):
        with patch.object(billing.stripe.checkout.Session, "retrieve", return_value=data):
            return billing.fulfill_checkout(data["id"])

    def add_existing(self):
        db = SessionLocal()
        tenant = Tenant(slug="existing", display_name="Existing")
        db.add(tenant); db.flush()
        db.add(TenantSubscription(tenant_id=tenant.id, plan_tier="pro", status="active",
                                  stripe_customer_id="cus_test", stripe_subscription_id="sub_base", extra_seats=0))
        db.commit(); db.close()

    def test_customer_creation_grants_no_access(self):
        stripe_webhooks.handle_customer_created(SimpleNamespace(data=SimpleNamespace(object={"id": "cus_test", "email": "buyer@example.com"})))
        db = SessionLocal()
        self.assertEqual(db.query(Tenant).count(), 0)
        self.assertFalse(db.query(PendingSignup).one().processed)
        db.close()

    def test_unpaid_waits_then_paid_creates_actual_purchased_tier_once(self):
        data = checkout(paid="unpaid")
        self.assertEqual(self.fulfill(data)["status"], "awaiting_payment")
        db = SessionLocal(); self.assertEqual(db.query(User).count(), 0); db.close()
        data["payment_status"] = "paid"
        self.assertEqual(self.fulfill(data)["status"], "fulfilled")
        self.assertEqual(self.fulfill(data)["status"], "already_fulfilled")
        db = SessionLocal()
        sub = db.query(TenantSubscription).one()
        self.assertEqual((sub.plan_tier, sub.billing_cycle, sub.stripe_subscription_id), ("pro", "monthly", "sub_test"))
        self.assertEqual(db.query(User).count(), 1)
        self.assertEqual(db.query(CheckoutFulfillment).count(), 1)
        self.assertEqual(db.query(User).one().pw_hash, "stored-hash")
        db.close()

    def test_invalid_payment_price_or_customer_never_grants_access(self):
        for case in ("unrecognized", "wrong_customer", "inactive", "unknown_payment", "negative_quantity"):
            data = checkout()
            if case == "unrecognized": data["line_items"]["data"][0]["price"]["product"] = "prod_wrong"
            if case == "wrong_customer": data["subscription"]["customer"] = "cus_wrong"
            if case == "inactive": data["subscription"]["status"] = "incomplete"
            if case == "negative_quantity": data["line_items"]["data"][0]["quantity"] = -1
            if case == "unknown_payment":
                data["payment_status"] = "mystery"
                self.assertEqual(self.fulfill(data)["status"], "awaiting_payment")
            else:
                with self.assertRaises(ValueError): self.fulfill(data)
            db = SessionLocal(); self.assertEqual(db.query(TenantSubscription).count(), 0); db.close()

    def test_seat_replay_has_one_increment_and_one_receipt(self):
        self.add_existing()
        data = checkout("extra_seat")
        data["line_items"]["data"][0]["quantity"] = 3
        self.fulfill(data); self.fulfill(data)
        db = SessionLocal()
        self.assertEqual(db.query(TenantSubscription).one().extra_seats, 3)
        self.assertEqual(db.query(PaymentHistory).count(), 1)
        self.assertEqual(db.query(CheckoutFulfillment).count(), 1)
        db.close()

    def test_failed_receipt_rolls_back_seats_and_payment_history(self):
        self.add_existing()
        with patch("sqlalchemy.orm.Session.commit", side_effect=RuntimeError("database unavailable")):
            with self.assertRaises(RuntimeError): self.fulfill(checkout("extra_seat"))
        db = SessionLocal()
        self.assertEqual(db.query(TenantSubscription).one().extra_seats, 0)
        self.assertEqual(db.query(PaymentHistory).count(), 0)
        db.close()
        self.assertEqual(self.fulfill(checkout("extra_seat"))["status"], "fulfilled")

    def test_changed_signup_cannot_replace_paying_users_credentials(self):
        data = checkout()
        db = SessionLocal(); pending = db.query(PendingSignup).one()
        data["metadata"] = {"pending_signup_id": str(pending.id), "signup_fingerprint": billing.signup_fingerprint(pending)}
        pending.password_hash = "changed-hash"; db.commit(); db.close()
        with self.assertRaisesRegex(ValueError, "Signup changed"): self.fulfill(data)

    def test_existing_free_account_upgrade_uses_customer_association(self):
        self.add_existing()
        db = SessionLocal(); sub = db.query(TenantSubscription).one(); sub.plan_tier = "free"; db.commit(); db.close()
        self.fulfill(checkout())
        db = SessionLocal()
        self.assertEqual(db.query(TenantSubscription).one().plan_tier, "pro")
        self.assertEqual(db.query(Tenant).count(), 1)
        self.assertEqual(db.query(User).count(), 0)
        db.close()

    def signed_event(self, event_type, data):
        payload = json.dumps({"id": "evt_test", "object": "event", "type": event_type, "data": {"object": data}})
        timestamp = str(int(time.time()))
        digest = hmac.new(b"test-secret", f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
        return module.app.test_client().post("/billing/webhooks/stripe", data=payload,
            headers={"Stripe-Signature": f"t={timestamp},v1={digest}"})

    def test_signed_delayed_payment_and_failure_retry(self):
        with patch.object(stripe_webhooks, "get_webhook_secret", return_value="test-secret"):
            with patch.object(billing.stripe.checkout.Session, "retrieve", side_effect=RuntimeError("provider down")):
                response = self.signed_event("checkout.session.completed", {"id": "cs_test"})
                self.assertEqual(response.status_code, 500)
                self.assertNotIn("provider down", response.get_data(as_text=True))
            with patch.object(billing.stripe.checkout.Session, "retrieve", return_value=checkout()):
                self.assertEqual(self.signed_event("checkout.session.async_payment_succeeded", {"id": "cs_test"}).status_code, 200)

    def test_production_cannot_use_mock_payments(self):
        with patch.object(stripe_service, "USE_REAL_STRIPE", False), patch.dict(os.environ, TEST_MODE="false"):
            self.assertFalse(stripe_service.PaymentService.is_mock_mode())
            with patch.object(stripe_service.MockStripe, "create_customer") as mock_customer:
                with self.assertRaises(RuntimeError): stripe_service.PaymentService.create_customer("test@example.com")
                mock_customer.assert_not_called()
            response = module.app.test_client().post("/billing/signup", data={"plan_tier": "pro"}, headers={"Origin": "http://localhost"})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(module.app.test_client().get("/pricing").status_code, 200)

    def test_inactive_accounts_do_not_keep_extra_seat_capacity(self):
        sub = TenantSubscription(plan_tier="pro", status="canceled", extra_seats=9)
        self.assertEqual(sub.get_total_seats(), 1)

    def test_checkout_creation_binds_existing_customer(self):
        price = checkout()["line_items"]["data"][0]["price"]
        with patch.object(stripe_service, "USE_REAL_STRIPE", True), patch.object(billing.stripe.Price, "list", return_value={"data": [price]}), patch.object(billing.stripe.checkout.Session, "create", return_value={"url": "https://checkout.stripe.com/test"}) as create:
            url = billing.create_checkout("pro", "monthly", customer_id="cus_owned", tenant_id=7,
                                          success_url="https://example.com/success", cancel_url="https://example.com/cancel")
            self.assertEqual(url, "https://checkout.stripe.com/test")
            self.assertEqual(create.call_args.kwargs["customer"], "cus_owned")
            self.assertNotIn("customer_email", create.call_args.kwargs)
