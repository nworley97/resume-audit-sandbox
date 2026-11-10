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
from subscription_models import CheckoutAttempt, CheckoutFulfillment, PaymentHistory, PendingSignup, TenantSubscription
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
        self.provider_guard = patch.object(billing.stripe.Subscription, "retrieve", side_effect=AssertionError("Unmocked Stripe request"))
        self.provider_guard.start()

    def tearDown(self):
        self.provider_guard.stop(); self.email.stop(); self.key.stop()
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

    def open_signup_checkout(self):
        db = SessionLocal(); pending = db.query(PendingSignup).one()
        try:
            return billing.create_checkout("pro", "monthly", pending=pending,
                success_url="https://example.com/success", cancel_url="https://example.com/cancel")
        finally:
            db.close()

    def checkout_patches(self):
        price = checkout()["line_items"]["data"][0]["price"]
        return (patch.object(stripe_service, "USE_REAL_STRIPE", True),
                patch.object(billing.stripe.Price, "list", return_value={"data": [price]}))

    def test_repeated_checkout_reuses_provider_session(self):
        real, price = self.checkout_patches()
        opened = {"id": "cs_test", "status": "open", "url": "https://checkout.stripe.com/reused"}
        with real, price, patch.object(billing.stripe.checkout.Session, "create", return_value=opened) as create, patch.object(billing.stripe.checkout.Session, "retrieve", return_value=opened):
            first = self.open_signup_checkout()
            second = self.open_signup_checkout()
        self.assertEqual(first, second)
        self.assertEqual(create.call_count, 1)
        db = SessionLocal(); self.assertEqual(db.query(CheckoutAttempt).count(), 1); db.close()

    def test_lost_provider_response_reuses_durable_parameters_and_key(self):
        real, price = self.checkout_patches()
        opened = {"id": "cs_test", "url": "https://checkout.stripe.com/recovered"}
        with real, price, patch.object(billing.stripe.checkout.Session, "create", side_effect=[RuntimeError("lost response"), opened]) as create:
            with self.assertRaisesRegex(RuntimeError, "lost response"): self.open_signup_checkout()
            self.assertEqual(self.open_signup_checkout(), opened["url"])
        self.assertEqual(create.call_args_list[0].kwargs, create.call_args_list[1].kwargs)
        self.assertTrue(create.call_args.kwargs["idempotency_key"].startswith("checkout-"))

    def test_complete_checkout_blocks_another_purchase_until_fulfilled(self):
        real, price = self.checkout_patches()
        with real, price, patch.object(billing.stripe.checkout.Session, "create", return_value={"id": "cs_test", "url": "https://checkout.stripe.com/test"}) as create, patch.object(billing.stripe.checkout.Session, "retrieve", return_value={"status": "complete"}):
            self.open_signup_checkout()
            with self.assertRaises(billing.CheckoutConflict): self.open_signup_checkout()
            self.assertEqual(create.call_count, 1)

    def test_expired_checkout_gets_new_identity_without_overwriting_snapshot(self):
        real, price = self.checkout_patches()
        with real, price, patch.object(billing.stripe.checkout.Session, "create", side_effect=[{"id": "cs_old", "url": "https://checkout.stripe.com/old"}, {"id": "cs_new", "url": "https://checkout.stripe.com/new"}]) as create, patch.object(billing.stripe.checkout.Session, "retrieve", return_value={"status": "expired"}):
            self.open_signup_checkout()
            db = SessionLocal(); db.query(PendingSignup).one().company_name = "New company"; db.commit(); db.close()
            self.open_signup_checkout()
            self.assertNotEqual(create.call_args_list[0].kwargs["idempotency_key"], create.call_args_list[1].kwargs["idempotency_key"])
        db = SessionLocal()
        old = db.query(CheckoutAttempt).filter_by(session_id="cs_old").one()
        new = db.query(CheckoutAttempt).filter_by(session_id="cs_new").one()
        self.assertEqual(old.signup["company_name"], "Test & Company!")
        self.assertIsNone(old.active_scope)
        self.assertEqual(new.signup["company_name"], "New company")
        self.assertIsNotNone(new.active_scope)
        db.close()

    def test_conflicting_active_scope_is_rejected_by_database(self):
        from sqlalchemy.exc import IntegrityError
        db = SessionLocal()
        db.add(CheckoutAttempt(id="first", scope="signup:1", active_scope="signup:1", parameters={}))
        db.commit()
        db.add(CheckoutAttempt(id="second", scope="signup:1", active_scope="signup:1", parameters={}))
        with self.assertRaises(IntegrityError): db.commit()
        db.rollback(); db.close()

    def test_ambiguous_creation_after_key_retention_never_creates_again(self):
        real, price = self.checkout_patches()
        with real, price, patch.object(billing.stripe.checkout.Session, "create", side_effect=RuntimeError("lost response")):
            with self.assertRaises(RuntimeError): self.open_signup_checkout()
        db = SessionLocal(); db.query(CheckoutAttempt).one().created_at = datetime.utcnow() - timedelta(hours=25); db.commit(); db.close()
        with patch.object(stripe_service, "USE_REAL_STRIPE", True), patch.object(billing.stripe.checkout.Session, "create") as create:
            with self.assertRaises(billing.CheckoutConflict): self.open_signup_checkout()
            create.assert_not_called()

    def test_changed_signup_fulfills_original_snapshot(self):
        real, price = self.checkout_patches()
        with real, price, patch.object(billing.stripe.checkout.Session, "create", return_value={"id": "cs_test", "url": "https://checkout.stripe.com/test"}):
            self.open_signup_checkout()
        db = SessionLocal()
        attempt = db.query(CheckoutAttempt).one()
        data = checkout(); data["metadata"] = dict(attempt.parameters["metadata"])
        pending = db.query(PendingSignup).one()
        pending.password_hash = "replacement-hash"; pending.company_name = "Replacement company"
        db.commit(); db.close()
        self.fulfill(data)
        db = SessionLocal()
        self.assertEqual(db.query(User).one().pw_hash, "stored-hash")
        self.assertEqual(db.query(Tenant).one().display_name, "Test & Company!")
        self.assertIsNone(db.query(CheckoutAttempt).one().active_scope)
        db.close()

    def test_identical_signup_resubmit_keeps_checkout_and_password(self):
        real, price = self.checkout_patches()
        opened = {"id": "cs_test", "status": "open", "url": "https://checkout.stripe.com/test"}
        form = dict(email="buyer@example.com", password="Repeated-password-123", company_name="Company", full_name="Buyer", plan_tier="pro", billing_cycle="monthly")
        with real, price, patch.object(billing.stripe.checkout.Session, "create", return_value=opened) as create, patch.object(billing.stripe.checkout.Session, "retrieve", return_value=opened):
            client = module.app.test_client()
            for _ in range(2):
                response = client.post('/billing/signup', data=form)
                self.assertEqual(response.headers["Location"], opened["url"])
            self.assertEqual(create.call_count, 1)
        db = SessionLocal(); attempt = db.query(CheckoutAttempt).one()
        data = checkout(); data["metadata"] = dict(attempt.parameters["metadata"]); db.close()
        self.fulfill(data)
        db = SessionLocal(); self.assertTrue(db.query(User).one().check_pw(form["password"])); db.close()

    def test_existing_plan_is_preserved_and_duplicate_is_canceled_once(self):
        self.add_existing()
        data = checkout(); data["subscription"]["id"] = "sub_duplicate"
        with patch.object(billing.stripe.Subscription, "retrieve", return_value={"id": "sub_base", "status": "active"}), patch.object(billing.stripe.Subscription, "cancel", return_value={"status": "canceled"}) as cancel:
            self.assertEqual(self.fulfill(data)["status"], "duplicate_canceled")
            self.assertEqual(self.fulfill(data)["status"], "already_fulfilled")
        cancel.assert_called_once_with("sub_duplicate", invoice_now=False, prorate=False)
        db = SessionLocal()
        self.assertEqual(db.query(TenantSubscription).one().stripe_subscription_id, "sub_base")
        self.assertEqual(db.query(PaymentHistory).one().status, "refund_review")
        db.close()

    def test_repeated_account_upgrade_opens_one_checkout_without_granting_access(self):
        self.add_existing()
        db = SessionLocal(); sub = db.query(TenantSubscription).one()
        sub.plan_tier = "free"; sub.stripe_subscription_id = None
        user = User(username="admin@example.com", tenant_id=sub.tenant_id, role="admin")
        user.set_pw("Password-test-123"); db.add(user); db.commit()
        with module.app.app_context(): login_id = user.get_id()
        db.close()
        client = module.app.test_client()
        with client.session_transaction() as state:
            state.update(_user_id=login_id, _fresh=True, tenant_slug="existing")
        token = client.get("/api/settings").json["csrf_token"]
        opened = {"id": "cs_test", "status": "open", "url": "https://checkout.stripe.com/test"}
        real, price = self.checkout_patches()
        with real, price, patch.object(billing.stripe.checkout.Session, "create", return_value=opened) as create, patch.object(billing.stripe.checkout.Session, "retrieve", return_value=opened):
            for _ in range(2):
                response = client.post("/billing/change-plan", data={"plan_tier": "pro", "billing_cycle": "monthly"}, headers={"X-CSRF-Token": token})
                self.assertEqual(response.headers["Location"], opened["url"])
            create.assert_called_once()
        db = SessionLocal()
        self.assertEqual(db.query(TenantSubscription).one().plan_tier, "free")
        self.assertEqual(db.query(CheckoutAttempt).count(), 1)
        db.close()

    def test_duplicate_cancellation_can_recover_after_commit_failure(self):
        self.add_existing()
        data = checkout(); data["subscription"]["id"] = "sub_duplicate"
        with patch.object(billing.stripe.Subscription, "retrieve", return_value={"status": "active"}), patch.object(billing.stripe.Subscription, "cancel", return_value={"status": "canceled"}), patch("sqlalchemy.orm.Session.commit", side_effect=RuntimeError("database down")):
            with self.assertRaises(RuntimeError): self.fulfill(data)
        data["subscription"]["status"] = "canceled"
        with patch.object(billing.stripe.Subscription, "retrieve", return_value={"status": "active"}), patch.object(billing.stripe.Subscription, "cancel") as cancel:
            self.assertEqual(self.fulfill(data)["status"], "duplicate_canceled")
            cancel.assert_not_called()

    def test_subscription_failure_returns_500_then_retry_removes_access(self):
        self.add_existing()
        with patch.object(stripe_webhooks, "get_webhook_secret", return_value="test-secret"):
            with patch("sqlalchemy.orm.Session.commit", side_effect=RuntimeError("database down")):
                response = self.signed_event("customer.subscription.deleted", {"id": "sub_base", "customer": "cus_test"})
                self.assertEqual(response.status_code, 500)
            db = SessionLocal(); self.assertEqual(db.query(TenantSubscription).one().status, "active"); db.close()
            self.assertEqual(self.signed_event("customer.subscription.deleted", {"id": "sub_base", "customer": "cus_test"}).status_code, 200)
        db = SessionLocal(); self.assertEqual(db.query(TenantSubscription).one().status, "canceled"); db.close()

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
        db = SessionLocal(); sub = db.query(TenantSubscription).one(); sub.plan_tier = "free"; sub.stripe_subscription_id = None; db.commit(); db.close()
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
        self.add_existing()
        db = SessionLocal(); sub = db.query(TenantSubscription).one()
        sub.stripe_subscription_id = None
        tenant_id = sub.tenant_id
        db.commit(); db.close()
        price = checkout()["line_items"]["data"][0]["price"]
        with patch.object(stripe_service, "USE_REAL_STRIPE", True), patch.object(billing.stripe.Price, "list", return_value={"data": [price]}), patch.object(billing.stripe.checkout.Session, "create", return_value={"id": "cs_test", "url": "https://checkout.stripe.com/test"}) as create:
            url = billing.create_checkout("pro", "monthly", customer_id="cus_test", tenant_id=tenant_id,
                                          success_url="https://example.com/success", cancel_url="https://example.com/cancel")
            self.assertEqual(url, "https://checkout.stripe.com/test")
            self.assertEqual(create.call_args.kwargs["customer"], "cus_test")
            self.assertNotIn("customer_email", create.call_args.kwargs)
