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
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)


# ─── Email Helpers ───────────────────────────────────────────────────────────

def _send_transactional_email(to: str, subject: str, html: str) -> bool:
    try:
        import resend
        resend.api_key = os.environ.get("RESEND_API_KEY", "")
        if not resend.api_key:
            logger.warning("RESEND_API_KEY not set — skipping email")
            return False
        resend.Emails.send({
            "from": "AlteraSF <noreply@alterasf.com>",
            "to": [to],
            "subject": subject,
            "html": html,
        })
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


def _send_welcome_email(to: str, company_name: str, plan_tier: str, tenant_slug: str) -> None:
    plan_label = plan_tier.title()
    login_url = f"https://app.alterasf.com/{tenant_slug}/login"
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a;">
      <h1 style="color:#2563eb;margin-bottom:8px;">Welcome to AlteraSF! 🎉</h1>
      <p>Hi {company_name},</p>
      <p>Your account is ready. You're on the <strong>{plan_label}</strong> plan.</p>
      <p style="margin:24px 0;">
        <a href="{login_url}"
           style="background:#2563eb;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;">
          Go to Dashboard
        </a>
      </p>
      <p style="color:#6b7280;font-size:14px;">
        Need help? Reply to this email or visit our support page.
      </p>
    </div>
    """
    _send_transactional_email(to, "Welcome to AlteraSF — your account is ready", html)


def _send_payment_confirmation_email(
    to: str,
    company_name: str,
    amount: float,
    currency: str,
    invoice_number: str,
    plan_tier: str,
    billing_cycle: str,
    period_end: Optional[datetime],
) -> None:
    plan_label = plan_tier.title() if plan_tier else "Your plan"
    currency_symbol = "$" if currency.lower() == "usd" else currency.upper()
    next_billing = period_end.strftime("%B %d, %Y") if period_end else "—"
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a;">
      <h2 style="color:#16a34a;">Payment Confirmed</h2>
      <p>Hi {company_name}, we received your payment. Thank you!</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:8px 0;border-bottom:1px solid #e5e7eb;color:#6b7280;">Invoice</td>
            <td style="padding:8px 0;border-bottom:1px solid #e5e7eb;text-align:right;">{invoice_number}</td></tr>
        <tr><td style="padding:8px 0;border-bottom:1px solid #e5e7eb;color:#6b7280;">Plan</td>
            <td style="padding:8px 0;border-bottom:1px solid #e5e7eb;text-align:right;">{plan_label} ({billing_cycle})</td></tr>
        <tr><td style="padding:8px 0;border-bottom:1px solid #e5e7eb;color:#6b7280;">Amount</td>
            <td style="padding:8px 0;border-bottom:1px solid #e5e7eb;text-align:right;font-weight:600;">{currency_symbol}{amount:,.2f}</td></tr>
        <tr><td style="padding:8px 0;color:#6b7280;">Next billing date</td>
            <td style="padding:8px 0;text-align:right;">{next_billing}</td></tr>
      </table>
      <p style="color:#6b7280;font-size:14px;">Questions? Reply to this email and we'll help.</p>
    </div>
    """
    _send_transactional_email(to, f"AlteraSF — payment confirmed ({currency_symbol}{amount:,.2f})", html)

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
        logger.error("Stripe webhook signing secret is not configured")
        return jsonify({"error": "Webhook verification unavailable"}), 503
    
    # Route to appropriate handler
    event_type = event.type
    logger.info(f"Processing Stripe webhook: {event_type}")
    
    try:
        handler = WEBHOOK_HANDLERS.get(event_type, handle_unknown_event)
        result = handler(event)
        return jsonify({"status": "success", "event": event_type}), 200
    except Exception as e:
        logger.error(f"Error processing webhook {event_type}: {e}", exc_info=True)
        # Transient failures must be retried; never acknowledge lost fulfillment.
        return jsonify({"status": "error", "message": "Payment processing failed; retry required"}), 500


# ─── Event Handlers ──────────────────────────────────────────────────────────

def _safe_get(obj, key, default=None):
    """Safely get attribute from Stripe object (works with both dict and object access)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def handle_subscription_created(event) -> Dict[str, Any]:
    """Handle customer.subscription.created event."""
    subscription = event.data.object
    
    customer_id = _safe_get(subscription, 'customer')
    subscription_id = _safe_get(subscription, 'id')
    status = _safe_get(subscription, 'status')
    period_start = _safe_get(subscription, 'current_period_start')
    period_end = _safe_get(subscription, 'current_period_end')
    
    logger.info(f"Subscription created: {subscription_id} for customer {customer_id} (status: {status})")
    
    # Update database
    _update_subscription_in_db(
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        status=_map_stripe_status(status),
        current_period_start=datetime.fromtimestamp(period_start) if period_start else None,
        current_period_end=datetime.fromtimestamp(period_end) if period_end else None,
    )
    
    return {"subscription_id": subscription_id, "status": status}


def handle_subscription_updated(event) -> Dict[str, Any]:
    """Handle customer.subscription.updated event."""
    subscription = event.data.object
    
    customer_id = _safe_get(subscription, 'customer')
    subscription_id = _safe_get(subscription, 'id')
    status = _safe_get(subscription, 'status')
    
    logger.info(f"Subscription updated: {subscription_id} (status: {status})")
    
    # Check for plan changes
    plan_tier = None
    billing_cycle = None
    
    # Safely access subscription items
    sub_items = _safe_get(subscription, 'items', {})
    items_data = _safe_get(sub_items, 'data', [])
    
    if items_data and len(items_data) > 0:
        item = items_data[0]
        price = _safe_get(item, 'price', {})
        lookup_key = _safe_get(price, 'lookup_key')
        
        # Extract plan info from price metadata or lookup key
        if lookup_key:
            parts = lookup_key.split("_")
            if len(parts) >= 2:
                plan_tier = parts[0]
                billing_cycle = "yearly" if "annual" in parts[1] else "monthly"
    
    # Safely get period timestamps
    period_start = _safe_get(subscription, 'current_period_start')
    period_end = _safe_get(subscription, 'current_period_end')
    
    # Update database
    _update_subscription_in_db(
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        status=_map_stripe_status(status),
        plan_tier=plan_tier,
        billing_cycle=billing_cycle,
        current_period_start=datetime.fromtimestamp(period_start) if period_start else None,
        current_period_end=datetime.fromtimestamp(period_end) if period_end else None,
    )
    
    return {"subscription_id": subscription_id, "status": status}


def handle_subscription_deleted(event) -> Dict[str, Any]:
    """Handle customer.subscription.deleted event."""
    subscription = event.data.object
    
    customer_id = _safe_get(subscription, 'customer')
    subscription_id = _safe_get(subscription, 'id')
    
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
    customer_id = _safe_get(invoice, 'customer')
    amount_paid = _safe_get(invoice, 'amount_paid', 0)
    amount = amount_paid / 100  # Convert from cents
    invoice_id = _safe_get(invoice, 'id')
    
    logger.info(f"Payment succeeded: ${amount} for customer {customer_id}")

    currency = _safe_get(invoice, 'currency', 'usd')
    invoice_number = _safe_get(invoice, 'number') or invoice_id

    # Record payment in history
    _record_payment_history(
        stripe_customer_id=customer_id,
        stripe_invoice_id=invoice_id,
        stripe_payment_intent_id=_safe_get(invoice, 'payment_intent'),
        amount=amount,
        currency=currency,
        status="succeeded",
        description=f"Invoice {invoice_number}",
    )

    # Send payment confirmation email
    try:
        from db import SessionLocal
        from models import Tenant, User
        from subscription_models import TenantSubscription

        db = SessionLocal()
        try:
            sub = db.query(TenantSubscription).filter(
                TenantSubscription.stripe_customer_id == customer_id
            ).first()
            if sub:
                tenant = db.query(Tenant).filter(Tenant.id == sub.tenant_id).first()
                user = db.query(User).filter(User.tenant_id == sub.tenant_id).first()
                if tenant and user:
                    _send_payment_confirmation_email(
                        to=user.username,
                        company_name=tenant.display_name or tenant.slug,
                        amount=amount,
                        currency=currency,
                        invoice_number=invoice_number,
                        plan_tier=sub.plan_tier,
                        billing_cycle=sub.billing_cycle,
                        period_end=sub.current_period_end,
                    )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to send payment confirmation email: {e}")

    return {"invoice_id": invoice_id, "amount": amount}


def handle_invoice_payment_failed(event) -> Dict[str, Any]:
    """Handle invoice.payment_failed event."""
    invoice = event.data.object
    customer_id = _safe_get(invoice, 'customer')
    amount_due = _safe_get(invoice, 'amount_due', 0)
    amount = amount_due / 100
    invoice_id = _safe_get(invoice, 'id')
    
    logger.warning(f"Payment failed: ${amount} for customer {customer_id}")
    
    # Record failed payment
    _record_payment_history(
        stripe_customer_id=customer_id,
        stripe_invoice_id=invoice_id,
        stripe_payment_intent_id=_safe_get(invoice, 'payment_intent'),
        amount=amount,
        currency=_safe_get(invoice, 'currency', 'usd'),
        status="failed",
        description=f"Failed: Invoice {_safe_get(invoice, 'number') or invoice_id}",
    )
    
    # Update subscription status to past_due
    subscription_id = _safe_get(invoice, 'subscription')
    if subscription_id:
        _update_subscription_in_db(
            stripe_subscription_id=subscription_id,
            status="past_due",
        )
    
    # TODO: Send notification email to customer
    
    return {"invoice_id": invoice_id, "amount": amount, "status": "failed"}


def handle_payment_method_attached(event) -> Dict[str, Any]:
    """Handle payment_method.attached event."""
    payment_method = event.data.object
    customer_id = _safe_get(payment_method, 'customer')
    pm_id = _safe_get(payment_method, 'id')
    
    logger.info(f"Payment method attached for customer {customer_id}")
    
    # Update payment method info in database
    card = _safe_get(payment_method, 'card')
    if card:
        _update_payment_method_in_db(
            stripe_customer_id=customer_id,
            card_last4=_safe_get(card, 'last4'),
            card_brand=_safe_get(card, 'brand'),
            card_exp_month=_safe_get(card, 'exp_month'),
            card_exp_year=_safe_get(card, 'exp_year'),
        )
    
    return {"customer_id": customer_id, "payment_method_id": pm_id}


def handle_customer_created(event) -> Dict[str, Any]:
    """Customer creation never proves payment or grants account access."""
    return {"customer_id": _safe_get(event.data.object, "id"), "status": "ignored"}


def handle_checkout_session_completed(event) -> Dict[str, Any]:
    """Fulfill verified paid sessions, including delayed-payment success."""
    from billing_fulfillment import fulfill_checkout
    return fulfill_checkout(_safe_get(event.data.object, "id"))


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
    "checkout.session.async_payment_succeeded": handle_checkout_session_completed,
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
        raise


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
        raise




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
                if existing.status != "refund_review":
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
        raise

