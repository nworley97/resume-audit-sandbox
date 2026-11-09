"""Verify Stripe purchases and commit entitlements with a unique checkout receipt."""
from datetime import datetime
import hashlib
import re

import stripe
from sqlalchemy import func

from db import SessionLocal
from models import Tenant, User
from subscription_models import (
    CheckoutFulfillment, PaymentHistory, PendingSignup, TenantSubscription, TenantUsage,
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


def create_checkout(tier, cycle, *, success_url, cancel_url, email=None,
                    customer_id=None, tenant_id=None, pending=None):
    from stripe_service import USE_REAL_STRIPE
    from stripe_config import STRIPE_SECRET_KEY
    if not USE_REAL_STRIPE:
        raise RuntimeError("Payments are unavailable. Please contact support.")
    if tier not in {"starter", "pro", "ultra", "extra_seat"} or cycle not in {"monthly", "yearly"}:
        raise ValueError("Invalid plan or billing cycle")
    stripe.api_key = STRIPE_SECRET_KEY
    prices = stripe.Price.list(lookup_keys=[STRIPE_PRICE_LOOKUP_KEYS[tier][cycle]], active=True, limit=2)
    items = value(prices, "data", [])
    if len(items) != 1 or price_plan(items[0]) != (tier, cycle):
        raise RuntimeError("The selected price is not configured. Please contact support.")
    metadata = {}
    if pending is not None:
        metadata = {"pending_signup_id": str(pending.id), "signup_fingerprint": signup_fingerprint(pending)}
    if tenant_id is not None:
        metadata["tenant_id"] = str(tenant_id)
    identity = {"customer": customer_id} if customer_id else {"customer_email": email}
    checkout = stripe.checkout.Session.create(
        mode="subscription", line_items=[{"price": object_id(items[0]), "quantity": 1}],
        success_url=success_url, cancel_url=cancel_url, metadata=metadata, **identity,
    )
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
    if (not object_id(provider_sub) or object_id(value(provider_sub, "customer")) != customer_id
            or value(provider_sub, "status") not in {"active", "trialing"}):
        raise ValueError("Checkout subscription is not active for this customer")
    subscription_items = value(value(provider_sub, "items", {}), "data", [])
    if len(subscription_items) != 1 or price_plan(value(subscription_items[0], "price", {})) != (tier, cycle):
        raise ValueError("Checkout price does not match its subscription")

    db = SessionLocal()
    welcome = None
    try:
        if db.get(CheckoutFulfillment, session_id):
            return {"status": "already_fulfilled"}
        if tier == "extra_seat":
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
                metadata = value(checkout, "metadata", {})
                pending_id = value(metadata, "pending_signup_id")
                # Support already-open legacy Payment Links using their verified
                # checkout email. New checkouts bind the exact pending signup.
                email = value(value(checkout, "customer_details", {}), "email") or value(checkout, "customer_email", "")
                query = db.query(PendingSignup).filter(PendingSignup.processed.is_(False))
                query = query.filter(PendingSignup.id == int(pending_id)) if pending_id else query.filter(func.lower(PendingSignup.email) == email.lower())
                pending = query.with_for_update().first()
                if not pending:
                    if db.get(CheckoutFulfillment, session_id):
                        return {"status": "already_fulfilled"}
                    raise ValueError("No pending signup for verified checkout")
                if pending_id and signup_fingerprint(pending) != value(metadata, "signup_fingerprint"):
                    raise ValueError("Signup changed after checkout was opened")
                if db.query(User).filter(func.lower(User.username) == pending.email.lower()).first():
                    raise ValueError("Checkout customer is not associated with this existing account")
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
                pending.processed = True
                welcome = (pending.email, pending.company_name, tier, slug)
            if db.get(CheckoutFulfillment, session_id):
                return {"status": "already_fulfilled"}
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
