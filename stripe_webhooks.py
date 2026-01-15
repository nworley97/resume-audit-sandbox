# stripe_webhooks.py
"""
Stripe Webhook Handler - Processes incoming webhook events from Stripe.

This module handles webhook events for:
- Subscription lifecycle (created, updated, deleted)
- Payment events (succeeded, failed)
- Customer events

Events are verified using webhook signatures before processing.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

# Create Blueprint for webhook routes
stripe_webhooks_bp = Blueprint('stripe_webhooks', __name__, url_prefix='/billing/webhooks')


# ─── Webhook Configuration ───────────────────────────────────────────────────

def get_webhook_secret(event_type: str = "snapshot") -> Optional[str]:
    """Get the appropriate webhook secret based on event type."""
    from stripe_config import (
        STRIPE_WEBHOOK_SECRET,
        STRIPE_WEBHOOK_SECRET_SNAPSHOT,
        STRIPE_WEBHOOK_SECRET_THIN,
    )
    
    if event_type == "thin":
        return STRIPE_WEBHOOK_SECRET_THIN or STRIPE_WEBHOOK_SECRET
    return STRIPE_WEBHOOK_SECRET_SNAPSHOT or STRIPE_WEBHOOK_SECRET


# ─── Webhook Endpoint ────────────────────────────────────────────────────────

@stripe_webhooks_bp.route('/stripe', methods=['POST'])
def handle_stripe_webhook():
    """
    Main Stripe webhook endpoint.
    
    Verifies the webhook signature and routes to appropriate handler.
    """
    from stripe_config import STRIPE_SECRET_KEY
    
    # Check if Stripe is configured
    if not STRIPE_SECRET_KEY:
        logger.warning("Webhook received but Stripe not configured")
        return jsonify({"error": "Stripe not configured"}), 503
    
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
    if not sig_header:
        logger.warning("Webhook received without signature")
        return jsonify({"error": "No signature"}), 400
    
    # Try both webhook secrets (snapshot and thin)
    event = None
    webhook_secret = get_webhook_secret("snapshot")
    
    if webhook_secret:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except stripe.error.SignatureVerificationError:
            # Try thin webhook secret
            webhook_secret_thin = get_webhook_secret("thin")
            if webhook_secret_thin and webhook_secret_thin != webhook_secret:
                try:
                    event = stripe.Webhook.construct_event(
                        payload, sig_header, webhook_secret_thin
                    )
                except stripe.error.SignatureVerificationError as e:
                    logger.error(f"Webhook signature verification failed: {e}")
                    return jsonify({"error": "Invalid signature"}), 400
            else:
                logger.error("Webhook signature verification failed")
                return jsonify({"error": "Invalid signature"}), 400
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            return jsonify({"error": "Invalid payload"}), 400
    else:
        # No webhook secret configured - parse without verification (not recommended for production)
        logger.warning("Processing webhook without signature verification - configure STRIPE_WEBHOOK_SECRET")
        try:
            import json
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            return jsonify({"error": "Invalid payload"}), 400
    
    # Route to appropriate handler
    event_type = event.type
    logger.info(f"Processing Stripe webhook: {event_type}")
    
    try:
        handler = WEBHOOK_HANDLERS.get(event_type, handle_unknown_event)
        result = handler(event)
        return jsonify({"status": "success", "event": event_type}), 200
    except Exception as e:
        logger.error(f"Error processing webhook {event_type}: {e}", exc_info=True)
        # Return 200 to prevent Stripe from retrying (we'll handle errors internally)
        return jsonify({"status": "error", "message": str(e)}), 200


# ─── Event Handlers ──────────────────────────────────────────────────────────

def handle_subscription_created(event) -> Dict[str, Any]:
    """Handle customer.subscription.created event."""
    subscription = event.data.object
    customer_id = subscription.customer
    subscription_id = subscription.id
    status = subscription.status
    
    logger.info(f"Subscription created: {subscription_id} for customer {customer_id} (status: {status})")
    
    # Update database
    _update_subscription_in_db(
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        status=_map_stripe_status(status),
        current_period_start=datetime.fromtimestamp(subscription.current_period_start),
        current_period_end=datetime.fromtimestamp(subscription.current_period_end),
    )
    
    return {"subscription_id": subscription_id, "status": status}


def handle_subscription_updated(event) -> Dict[str, Any]:
    """Handle customer.subscription.updated event."""
    subscription = event.data.object
    customer_id = subscription.customer
    subscription_id = subscription.id
    status = subscription.status
    
    logger.info(f"Subscription updated: {subscription_id} (status: {status})")
    
    # Check for plan changes
    plan_tier = None
    billing_cycle = None
    
    if subscription.items and subscription.items.data:
        item = subscription.items.data[0]
        price = item.price
        
        # Extract plan info from price metadata or lookup key
        if price.lookup_key:
            parts = price.lookup_key.split("_")
            if len(parts) >= 2:
                plan_tier = parts[0]
                billing_cycle = "yearly" if "annual" in parts[1] else "monthly"
    
    # Update database
    _update_subscription_in_db(
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        status=_map_stripe_status(status),
        plan_tier=plan_tier,
        billing_cycle=billing_cycle,
        current_period_start=datetime.fromtimestamp(subscription.current_period_start),
        current_period_end=datetime.fromtimestamp(subscription.current_period_end),
    )
    
    return {"subscription_id": subscription_id, "status": status}


def handle_subscription_deleted(event) -> Dict[str, Any]:
    """Handle customer.subscription.deleted event."""
    subscription = event.data.object
    customer_id = subscription.customer
    subscription_id = subscription.id
    
    logger.info(f"Subscription deleted: {subscription_id}")
    
    # Update database - mark as canceled
    _update_subscription_in_db(
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        status="canceled",
        canceled_at=datetime.utcnow(),
    )
    
    return {"subscription_id": subscription_id, "status": "canceled"}


def handle_invoice_payment_succeeded(event) -> Dict[str, Any]:
    """Handle invoice.payment_succeeded event."""
    invoice = event.data.object
    customer_id = invoice.customer
    amount = invoice.amount_paid / 100  # Convert from cents
    
    logger.info(f"Payment succeeded: ${amount} for customer {customer_id}")
    
    # Record payment in history
    _record_payment_history(
        stripe_customer_id=customer_id,
        stripe_invoice_id=invoice.id,
        stripe_payment_intent_id=invoice.payment_intent,
        amount=amount,
        currency=invoice.currency,
        status="succeeded",
        description=f"Invoice {invoice.number or invoice.id}",
    )
    
    return {"invoice_id": invoice.id, "amount": amount}


def handle_invoice_payment_failed(event) -> Dict[str, Any]:
    """Handle invoice.payment_failed event."""
    invoice = event.data.object
    customer_id = invoice.customer
    amount = invoice.amount_due / 100
    
    logger.warning(f"Payment failed: ${amount} for customer {customer_id}")
    
    # Record failed payment
    _record_payment_history(
        stripe_customer_id=customer_id,
        stripe_invoice_id=invoice.id,
        stripe_payment_intent_id=invoice.payment_intent,
        amount=amount,
        currency=invoice.currency,
        status="failed",
        description=f"Failed: Invoice {invoice.number or invoice.id}",
    )
    
    # Update subscription status to past_due
    if invoice.subscription:
        _update_subscription_in_db(
            stripe_subscription_id=invoice.subscription,
            status="past_due",
        )
    
    # TODO: Send notification email to customer
    
    return {"invoice_id": invoice.id, "amount": amount, "status": "failed"}


def handle_payment_method_attached(event) -> Dict[str, Any]:
    """Handle payment_method.attached event."""
    payment_method = event.data.object
    customer_id = payment_method.customer
    
    logger.info(f"Payment method attached for customer {customer_id}")
    
    # Update payment method info in database
    if payment_method.card:
        _update_payment_method_in_db(
            stripe_customer_id=customer_id,
            card_last4=payment_method.card.last4,
            card_brand=payment_method.card.brand,
            card_exp_month=payment_method.card.exp_month,
            card_exp_year=payment_method.card.exp_year,
        )
    
    return {"customer_id": customer_id, "payment_method_id": payment_method.id}


def handle_customer_created(event) -> Dict[str, Any]:
    """Handle customer.created event."""
    customer = event.data.object
    logger.info(f"Customer created: {customer.id} ({customer.email})")
    
    # Check if this customer email matches a pending signup
    _maybe_create_account_from_pending_signup(customer.email, customer.id)
    
    return {"customer_id": customer.id, "email": customer.email}


def handle_checkout_session_completed(event) -> Dict[str, Any]:
    """Handle checkout.session.completed event (for payment links)."""
    checkout_session = event.data.object
    customer_id = checkout_session.customer
    
    # Extract email - customer_details is a Stripe object, not a dict
    customer_email = None
    if checkout_session.customer_details:
        customer_email = getattr(checkout_session.customer_details, 'email', None)
    # Fallback to customer_email field
    if not customer_email:
        customer_email = getattr(checkout_session, 'customer_email', None)
    
    logger.info(f"Checkout session completed: {checkout_session.id} for customer {customer_id}, email: {customer_email}")
    
    # If we have customer email, try to create account from pending signup
    account_created = False
    if customer_email:
        account_created = _maybe_create_account_from_pending_signup(customer_email, customer_id)
    
    if not account_created:
        # Log for debugging - this might indicate an email mismatch
        logger.warning(
            f"Checkout completed but no account created for email: {customer_email}, "
            f"customer_id: {customer_id}. Check if pending signup exists with matching email."
        )
    
    return {"session_id": checkout_session.id, "customer_id": customer_id, "account_created": account_created}


def handle_unknown_event(event) -> Dict[str, Any]:
    """Handle unknown/unhandled events."""
    logger.debug(f"Unhandled webhook event type: {event.type}")
    return {"event_type": event.type, "status": "ignored"}


# ─── Event Handler Registry ──────────────────────────────────────────────────

WEBHOOK_HANDLERS = {
    "customer.subscription.created": handle_subscription_created,
    "customer.subscription.updated": handle_subscription_updated,
    "customer.subscription.deleted": handle_subscription_deleted,
    "invoice.payment_succeeded": handle_invoice_payment_succeeded,
    "invoice.payment_failed": handle_invoice_payment_failed,
    "payment_method.attached": handle_payment_method_attached,
    "customer.created": handle_customer_created,
    "checkout.session.completed": handle_checkout_session_completed,
}


# ─── Database Helpers ────────────────────────────────────────────────────────

def _map_stripe_status(stripe_status: str) -> str:
    """Map Stripe subscription status to our internal status."""
    status_map = {
        "active": "active",
        "trialing": "trialing",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
        "incomplete": "incomplete",
        "incomplete_expired": "canceled",
    }
    return status_map.get(stripe_status, stripe_status)


def _update_subscription_in_db(
    stripe_customer_id: str = None,
    stripe_subscription_id: str = None,
    status: str = None,
    plan_tier: str = None,
    billing_cycle: str = None,
    current_period_start: datetime = None,
    current_period_end: datetime = None,
    canceled_at: datetime = None,
) -> bool:
    """Update subscription record in database based on Stripe webhook."""
    try:
        from db import SessionLocal
        from subscription_models import TenantSubscription
        
        db = SessionLocal()
        try:
            # Find subscription by Stripe IDs
            query = db.query(TenantSubscription)
            
            if stripe_subscription_id:
                subscription = query.filter(
                    TenantSubscription.stripe_subscription_id == stripe_subscription_id
                ).first()
            elif stripe_customer_id:
                subscription = query.filter(
                    TenantSubscription.stripe_customer_id == stripe_customer_id
                ).first()
            else:
                logger.warning("No identifier provided for subscription update")
                return False
            
            if not subscription:
                logger.warning(f"Subscription not found: customer={stripe_customer_id}, sub={stripe_subscription_id}")
                return False
            
            # Update fields
            if status:
                subscription.status = status
            if plan_tier:
                subscription.plan_tier = plan_tier
            if billing_cycle:
                subscription.billing_cycle = billing_cycle
            if current_period_start:
                subscription.current_period_start = current_period_start
            if current_period_end:
                subscription.current_period_end = current_period_end
            if canceled_at:
                subscription.canceled_at = canceled_at
            
            db.commit()
            logger.info(f"Updated subscription {subscription.id} in database")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error updating subscription in database: {e}", exc_info=True)
        return False


def _update_payment_method_in_db(
    stripe_customer_id: str,
    card_last4: str,
    card_brand: str,
    card_exp_month: int,
    card_exp_year: int,
) -> bool:
    """Update payment method info in database."""
    try:
        from db import SessionLocal
        from subscription_models import TenantSubscription
        
        db = SessionLocal()
        try:
            subscription = db.query(TenantSubscription).filter(
                TenantSubscription.stripe_customer_id == stripe_customer_id
            ).first()
            
            if not subscription:
                logger.warning(f"Subscription not found for customer: {stripe_customer_id}")
                return False
            
            subscription.payment_method_last4 = card_last4
            subscription.payment_method_brand = card_brand
            subscription.payment_method_exp_month = card_exp_month
            subscription.payment_method_exp_year = card_exp_year
            
            db.commit()
            logger.info(f"Updated payment method for subscription {subscription.id}")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error updating payment method in database: {e}", exc_info=True)
        return False


def _maybe_create_account_from_pending_signup(customer_email: str, stripe_customer_id: str) -> bool:
    """
    Create an account from pending signup data when payment succeeds.
    
    Called by webhook handlers when a customer is created or checkout completes.
    Looks up pending signup by email and creates tenant/user/subscription.
    
    Uses SELECT FOR UPDATE to prevent race conditions when multiple webhooks
    fire for the same customer (e.g., customer.created + checkout.session.completed).
    """
    if not customer_email:
        return False
    
    try:
        from db import SessionLocal
        from models import Tenant, User
        from subscription_models import PendingSignup, TenantSubscription, TenantUsage
        from plans_config import PLAN_PRICING
        
        db = SessionLocal()
        try:
            # Find pending signup by email with row lock to prevent race conditions
            # Normalize email to lowercase for consistent matching
            pending = db.query(PendingSignup).filter(
                PendingSignup.email == customer_email.lower(),
                PendingSignup.processed == False,
                PendingSignup.expires_at > datetime.utcnow()
            ).with_for_update(skip_locked=True).first()
            
            if not pending:
                logger.debug(f"No pending signup found for email: {customer_email}")
                return False
            
            # Check if user already exists
            existing_user = db.query(User).filter(User.username == pending.email).first()
            if existing_user:
                logger.warning(f"User already exists for email: {pending.email}, marking pending as processed")
                pending.processed = True
                db.commit()
                return False
            
            # Create tenant
            tenant_slug = pending.company_name.lower().replace(' ', '-').replace('.', '')[:20]
            base_slug = tenant_slug
            counter = 1
            while db.query(Tenant).filter(Tenant.slug == tenant_slug).first():
                tenant_slug = f"{base_slug}-{counter}"
                counter += 1
            
            tenant = Tenant(
                slug=tenant_slug,
                display_name=pending.company_name,
            )
            db.add(tenant)
            db.flush()
            
            # Create user
            user = User(
                username=pending.email,
                tenant_id=tenant.id,
            )
            user.pw_hash = pending.password_hash  # Use the stored hash directly
            db.add(user)
            db.flush()
            
            # Get subscription info from Stripe if available
            subscription_status = 'active'
            stripe_subscription_id = None
            
            try:
                import stripe
                from stripe_config import STRIPE_SECRET_KEY
                if STRIPE_SECRET_KEY:
                    stripe.api_key = STRIPE_SECRET_KEY
                    # Try to get subscription for this customer
                    subscriptions = stripe.Subscription.list(customer=stripe_customer_id, limit=1)
                    if subscriptions.data:
                        sub = subscriptions.data[0]
                        stripe_subscription_id = sub.id
                        subscription_status = _map_stripe_status(sub.status)
            except Exception as e:
                logger.warning(f"Could not fetch subscription from Stripe: {e}")
            
            # Create subscription record
            now = datetime.utcnow()
            subscription = TenantSubscription(
                tenant_id=tenant.id,
                plan_tier=pending.plan_tier,
                billing_cycle=pending.billing_cycle,
                status=subscription_status,
                created_at=now,
                current_period_start=now,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
            )
            db.add(subscription)
            
            # Create initial usage record
            period_end = subscription.get_period_end_date()
            usage = TenantUsage(
                tenant_id=tenant.id,
                period_start=now,
                period_end=period_end,
                resumes_reviewed=0,
            )
            db.add(usage)
            
            # Mark pending signup as processed
            pending.processed = True
            
            db.commit()
            
            logger.info(f"Created account from pending signup: {pending.email} -> tenant {tenant.id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating account from pending signup: {e}", exc_info=True)
            return False
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in _maybe_create_account_from_pending_signup: {e}", exc_info=True)
        return False


def _record_payment_history(
    stripe_customer_id: str,
    stripe_invoice_id: str = None,
    stripe_payment_intent_id: str = None,
    amount: float = 0,
    currency: str = "usd",
    status: str = "succeeded",
    description: str = "",
) -> bool:
    """Record a payment in the payment history table."""
    try:
        from db import SessionLocal
        from subscription_models import TenantSubscription, PaymentHistory
        
        db = SessionLocal()
        try:
            # Find tenant ID from subscription
            subscription = db.query(TenantSubscription).filter(
                TenantSubscription.stripe_customer_id == stripe_customer_id
            ).first()
            
            if not subscription:
                logger.warning(f"Subscription not found for customer: {stripe_customer_id}")
                return False
            
            # Check for duplicate
            existing = db.query(PaymentHistory).filter(
                PaymentHistory.stripe_invoice_id == stripe_invoice_id
            ).first() if stripe_invoice_id else None
            
            if existing:
                # Update existing record
                existing.status = status
                existing.amount = amount
                db.commit()
                return True
            
            # Create new payment record
            payment = PaymentHistory(
                tenant_id=subscription.tenant_id,
                amount=amount,
                currency=currency.upper(),
                status=status,
                description=description,
                stripe_payment_intent_id=stripe_payment_intent_id,
                stripe_invoice_id=stripe_invoice_id,
                payment_method_last4=subscription.payment_method_last4,
                payment_method_brand=subscription.payment_method_brand,
            )
            
            db.add(payment)
            db.commit()
            logger.info(f"Recorded payment history for tenant {subscription.tenant_id}")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error recording payment history: {e}", exc_info=True)
        return False

