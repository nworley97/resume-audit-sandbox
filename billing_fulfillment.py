"""Verify Stripe purchases and commit entitlements with a unique checkout receipt."""
from datetime import datetime, timedelta
import hashlib
import re
import uuid
import time
from types import SimpleNamespace

import stripe
from sqlalchemy import func

from db import SessionLocal
from models import Tenant, User
from subscription_models import (
    CheckoutAttempt, CheckoutFulfillment, PaymentHistory, PendingSignup, TenantSubscription, TenantUsage,
)
from stripe_config import STRIPE_PRICE_LOOKUP_KEYS, STRIPE_PRODUCTS


def value(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def object_id(obj):
    return obj if isinstance(obj, str) else value(obj, "id")


def price_plan(price):
    """Only our configured product/lookup-key pairs can grant entitlements."""
    product = object_id(value(price, "product"))
    lookup = value(price, "lookup_key")
    for tier, cycles in STRIPE_PRICE_LOOKUP_KEYS.items():
        for cycle, key in cycles.items():
            if lookup == key and product == STRIPE_PRODUCTS.get(tier):
                return tier, cycle
    raise ValueError("Checkout contains an unrecognized price/product")


def signup_fingerprint(pending):
    # Bind a checkout to the exact signup, so a later form submission cannot
    # replace the password/company on an already-open payment session.
    fields = [pending.email, pending.password_hash, pending.company_name,
              pending.full_name, pending.plan_tier, pending.billing_cycle]
    return hashlib.sha256("\0".join(field or "" for field in fields).encode()).hexdigest()


class CheckoutConflict(RuntimeError):
    """An existing purchase must finish before another can be opened."""


def create_checkout(tier, cycle, *, success_url, cancel_url, email=None,
                    customer_id=None, tenant_id=None, pending=None):
    from stripe_service import USE_REAL_STRIPE
    from stripe_config import STRIPE_SECRET_KEY
    if not USE_REAL_STRIPE:
        raise RuntimeError("Payments are unavailable. Please contact support.")
    if tier not in {"starter", "pro", "ultra", "extra_seat"} or cycle not in {"monthly", "yearly"}:
        raise ValueError("Invalid plan or billing cycle")
    if tenant_id is None and pending is None:
        raise ValueError("Checkout requires an account or pending signup")
    stripe.api_key = STRIPE_SECRET_KEY
    kind = "seats" if tier == "extra_seat" else "plan"
    scope = f"tenant:{tenant_id}:{kind}" if tenant_id is not None else f"signup:{pending.id}"

    # Independent sessions avoid closing/committing the caller's transaction.
    # Parent locks serialize creation; active_scope also enforces uniqueness.
    with SessionLocal.session_factory() as db:
        snapshot = None
        if tenant_id is not None:
            owner = db.query(Tenant).filter_by(id=tenant_id).with_for_update().one()
            sub = db.query(TenantSubscription).filter_by(tenant_id=owner.id).one()
            if not customer_id or customer_id != sub.stripe_customer_id:
                raise ValueError("Checkout customer does not match account")
            if kind == "plan" and sub.stripe_subscription_id and sub.is_active():
                raise CheckoutConflict("Your plan is already active. Reload billing before changing it.")
        else:
            owner = db.query(PendingSignup).filter_by(id=pending.id).with_for_update().one()
            if owner.processed:
                raise CheckoutConflict("This signup has already completed. Please sign in.")
            snapshot = {field: getattr(owner, field) for field in (
                "id", "email", "password_hash", "company_name", "full_name", "plan_tier", "billing_cycle")}
            email = owner.email
        attempt = db.query(CheckoutAttempt).filter_by(active_scope=scope).first()
        if attempt and attempt.session_id:
            existing = stripe.checkout.Session.retrieve(attempt.session_id)
            status = value(existing, "status")
            if status == "expired":
                attempt.active_scope = None
                db.flush()
                attempt = None
            elif status == "complete":
                raise CheckoutConflict("Your payment is processing. Reload billing shortly.")
            elif status != "open":
                raise CheckoutConflict("Checkout status could not be confirmed. Please contact support.")
        if attempt:
            metadata = attempt.parameters["metadata"]
            if (metadata["plan_tier"], metadata["billing_cycle"]) != (tier, cycle):
                raise CheckoutConflict("Another plan checkout is open. Complete it or wait for it to expire.")
            if snapshot and signup_fingerprint(SimpleNamespace(**snapshot)) != signup_fingerprint(SimpleNamespace(**attempt.signup)):
                raise CheckoutConflict("A checkout is already open with your earlier signup details. Complete that checkout or wait for it to expire.")
            if attempt.session_id:
                return value(existing, "url")
            if datetime.utcnow() - attempt.created_at > timedelta(hours=23):
                # Stripe may prune idempotency keys after 24 hours. An unknown
                # outcome must be reconciled, never retried as a new purchase.
                raise CheckoutConflict("A previous checkout needs payment support to reconcile it.")
        else:
            prices = stripe.Price.list(lookup_keys=[STRIPE_PRICE_LOOKUP_KEYS[tier][cycle]], active=True, limit=2)
            items = value(prices, "data", [])
            if len(items) != 1 or price_plan(items[0]) != (tier, cycle):
                raise RuntimeError("The selected price is not configured. Please contact support.")
            attempt_id = uuid.uuid4().hex
            metadata = {"checkout_attempt_id": attempt_id, "plan_tier": tier, "billing_cycle": cycle}
            if snapshot:
                metadata.update(pending_signup_id=str(owner.id),
                                signup_fingerprint=signup_fingerprint(SimpleNamespace(**snapshot)))
            if tenant_id is not None:
                metadata["tenant_id"] = str(tenant_id)
            identity = {"customer": customer_id} if customer_id else {"customer_email": email}
            parameters = dict(
                mode="subscription", line_items=[{"price": object_id(items[0]), "quantity": 1}],
                success_url=success_url, cancel_url=cancel_url, metadata=metadata,
                expires_at=int(time.time()) + 35 * 60, **identity,
            )
            attempt = CheckoutAttempt(id=attempt_id, scope=scope, active_scope=scope,
                                      parameters=parameters, signup=snapshot)
            db.add(attempt)
        # Persist BEFORE Stripe, including stable URLs/price/expiry and signup.
        db.commit()
        attempt_id, parameters = attempt.id, dict(attempt.parameters)

    checkout = stripe.checkout.Session.create(**parameters, idempotency_key=f"checkout-{attempt_id}")
    session_id = object_id(checkout)
    if not session_id:
        raise RuntimeError("Stripe returned no checkout identifier")
    with SessionLocal.session_factory() as db:
        saved = db.query(CheckoutAttempt).filter_by(id=attempt_id).with_for_update().one()
        if saved.session_id and saved.session_id != session_id:
            raise RuntimeError("Checkout idempotency mismatch")
        saved.session_id = session_id
        db.commit()
    return value(checkout, "url")


def fulfill_checkout(session_id):
    """Retrieve payment state; do not trust event timing or locally selected tiers.

    A receipt's primary key prevents concurrent or sequential replay. Row locks
    serialize entitlement updates; receipt and access changes share a transaction.
    Exceptions propagate to the webhook endpoint so Stripe can retry failures.
    """
    from stripe_config import STRIPE_SECRET_KEY
    if not session_id or not STRIPE_SECRET_KEY:
        raise RuntimeError("Checkout verification unavailable")
    with SessionLocal.session_factory() as receipt_db:
        if receipt_db.get(CheckoutFulfillment, session_id):
            return {"status": "already_fulfilled"}
    stripe.api_key = STRIPE_SECRET_KEY
    checkout = stripe.checkout.Session.retrieve(session_id, expand=["line_items", "subscription"])
    if value(checkout, "status") != "complete" or value(checkout, "payment_status") not in {"paid", "no_payment_required"}:
        return {"status": "awaiting_payment"}
    customer_id = object_id(value(checkout, "customer"))
    if not customer_id:
        raise ValueError("Checkout has no customer")
    lines = value(checkout, "line_items", {})
    if value(lines, "has_more", False):
        line_items = list(stripe.checkout.Session.list_line_items(session_id).auto_paging_iter())
    else:
        line_items = value(lines, "data", [])
    if len(line_items) != 1:
        raise ValueError("Expected one plan or seat product")
    tier, cycle = price_plan(value(line_items[0], "price", {}))
    quantity = value(line_items[0], "quantity")
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
        raise ValueError("Invalid purchase quantity")
    provider_sub = value(checkout, "subscription")
    if isinstance(provider_sub, str):
        provider_sub = stripe.Subscription.retrieve(provider_sub)
    if not object_id(provider_sub) or object_id(value(provider_sub, "customer")) != customer_id:
        raise ValueError("Checkout subscription is not active for this customer")
    subscription_items = value(value(provider_sub, "items", {}), "data", [])
    if len(subscription_items) != 1 or price_plan(value(subscription_items[0], "price", {})) != (tier, cycle):
        raise ValueError("Checkout price does not match its subscription")

    db = SessionLocal()
    welcome = None
    try:
        if db.get(CheckoutFulfillment, session_id):
            return {"status": "already_fulfilled"}
        metadata = value(checkout, "metadata", {})
        attempt_id = value(metadata, "checkout_attempt_id")
        attempt = db.get(CheckoutAttempt, attempt_id) if attempt_id else None
        if attempt_id and (not attempt or (attempt.session_id and attempt.session_id != session_id)):
            raise ValueError("Checkout attempt identity mismatch")
        if attempt:
            # A webhook may beat the HTTP response that saves the session ID.
            attempt.session_id = session_id
        if tier == "extra_seat":
            if value(provider_sub, "status") not in {"active", "trialing"}:
                raise ValueError("Seat subscription is not active")
            sub = db.query(TenantSubscription).filter_by(stripe_customer_id=customer_id).with_for_update().first()
            if not sub or not sub.is_active():
                raise ValueError("No active account for seat purchase")
            if db.get(CheckoutFulfillment, session_id):
                return {"status": "already_fulfilled"}
            sub.extra_seats = (sub.extra_seats or 0) + quantity
            db.add(PaymentHistory(
                tenant_id=sub.tenant_id, amount=value(checkout, "amount_total", 0) / 100,
                currency=value(checkout, "currency", "usd").upper(), status="succeeded",
                description=f"Added {quantity} additional seat(s)", extra_seats=quantity,
                stripe_payment_intent_id=object_id(value(checkout, "payment_intent")),
            ))
            kind = "seats"
        else:
            if tier not in {"starter", "pro", "ultra"} or quantity != 1:
                raise ValueError("Invalid subscription plan")
            sub = db.query(TenantSubscription).filter_by(stripe_customer_id=customer_id).with_for_update().first()
            if not sub:
                pending_id = value(metadata, "pending_signup_id")
                # Support already-open legacy Payment Links using their verified
                # checkout email. New checkouts bind the exact pending signup.
                email = value(value(checkout, "customer_details", {}), "email") or value(checkout, "customer_email", "")
                query = db.query(PendingSignup)
                query = query.filter(PendingSignup.id == int(pending_id)) if pending_id else query.filter(func.lower(PendingSignup.email) == email.lower())
                pending_record = query.with_for_update().first()
                pending = SimpleNamespace(**attempt.signup) if attempt and attempt.signup else pending_record
                if not pending:
                    if db.get(CheckoutFulfillment, session_id):
                        return {"status": "already_fulfilled"}
                    raise ValueError("No pending signup for verified checkout")
                if pending_id and signup_fingerprint(pending) != value(metadata, "signup_fingerprint"):
                    raise ValueError("Signup changed after checkout was opened")
                existing_user = db.query(User).filter(func.lower(User.username) == pending.email.lower()).first()
                if existing_user:
                    existing_sub = db.query(TenantSubscription).filter_by(tenant_id=existing_user.tenant_id).with_for_update().first()
                    if existing_sub and existing_sub.stripe_subscription_id:
                        return _reconcile_duplicate(db, existing_sub, provider_sub, checkout, session_id, attempt)
                    raise ValueError("Checkout customer is not associated with this existing account")
                if value(provider_sub, "status") not in {"active", "trialing"}:
                    raise ValueError("Checkout subscription is not active")
                slug = re.sub(r"[^a-z0-9-]", "", pending.company_name.lower().replace(" ", "-"))[:40] or "company"
                base_slug, counter = slug, 0
                while db.query(Tenant).filter_by(slug=slug).first():
                    counter += 1
                    slug = f"{base_slug}-{counter}"
                tenant = Tenant(slug=slug, display_name=pending.company_name)
                db.add(tenant); db.flush()
                db.add(User(username=pending.email.lower(), pw_hash=pending.password_hash,
                            tenant_id=tenant.id, role="admin", full_name=pending.full_name))
                sub = TenantSubscription(tenant_id=tenant.id, stripe_customer_id=customer_id)
                db.add(sub)
                if pending_record:
                    pending_record.processed = True
                welcome = (pending.email, pending.company_name, tier, slug)
            if db.get(CheckoutFulfillment, session_id):
                return {"status": "already_fulfilled"}
            if sub.stripe_subscription_id and sub.stripe_subscription_id != object_id(provider_sub):
                previous = stripe.Subscription.retrieve(sub.stripe_subscription_id)
                if value(previous, "status") not in {"canceled", "incomplete_expired"}:
                    return _reconcile_duplicate(db, sub, provider_sub, checkout, session_id, attempt)
            if value(provider_sub, "status") not in {"active", "trialing"}:
                raise ValueError("Checkout subscription is not active")
            sub.plan_tier, sub.billing_cycle = tier, cycle
            sub.status = value(provider_sub, "status")
            sub.stripe_subscription_id = object_id(provider_sub)
            item = subscription_items[0]
            start = value(provider_sub, "current_period_start") or value(item, "current_period_start")
            end = value(provider_sub, "current_period_end") or value(item, "current_period_end")
            sub.current_period_start = datetime.utcfromtimestamp(start) if start else datetime.utcnow()
            sub.current_period_end = datetime.utcfromtimestamp(end) if end else None
            if welcome:
                db.add(TenantUsage(tenant_id=sub.tenant_id, period_start=sub.current_period_start,
                                   period_end=sub.get_period_end_date(), resumes_reviewed=0))
            kind = "plan"
        if attempt:
            attempt.active_scope = None
        db.add(CheckoutFulfillment(session_id=session_id, tenant_id=sub.tenant_id, kind=kind))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    if welcome:
        from stripe_webhooks import _send_welcome_email
        _send_welcome_email(*welcome)
    return {"status": "fulfilled", "kind": kind}


def _reconcile_duplicate(db, existing_sub, provider_sub, checkout, session_id, attempt):
    """Keep the established plan; stop an accidental second recurring charge.

    Cancellation is retry-safe even if the database commit fails afterwards.
    Any initial payment is explicitly recorded for refund review, never hidden.
    """
    new_id = object_id(provider_sub)
    if new_id == existing_sub.stripe_subscription_id:
        raise ValueError("Existing account requires manual checkout reconciliation")
    if value(provider_sub, "status") != "canceled":
        canceled = stripe.Subscription.cancel(new_id, invoice_now=False, prorate=False)
        if value(canceled, "status") != "canceled":
            raise RuntimeError("Duplicate subscription cancellation was not confirmed")
    db.add(PaymentHistory(
        tenant_id=existing_sub.tenant_id, amount=value(checkout, "amount_total", 0) / 100,
        currency=value(checkout, "currency", "usd").upper(), status="refund_review",
        description=f"Duplicate subscription {new_id} canceled; review initial payment for refund",
        stripe_invoice_id=object_id(value(checkout, "invoice")),
        stripe_payment_intent_id=object_id(value(checkout, "payment_intent")),
    ))
    db.add(CheckoutFulfillment(session_id=session_id, tenant_id=existing_sub.tenant_id, kind="duplicate_plan"))
    if attempt:
        attempt.active_scope = None
    db.commit()
    return {"status": "duplicate_canceled", "refund_review": True}
