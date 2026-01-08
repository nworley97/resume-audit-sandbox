# stripe_config.py
"""
Stripe Configuration - Product and Price ID mappings.

SECURITY: API keys are loaded from environment variables, never hardcoded.
Set these in your .env file or hosting platform environment:
  - STRIPE_SECRET_KEY
  - STRIPE_PUBLISHABLE_KEY
  - STRIPE_WEBHOOK_SECRET

Product IDs and Price lookup keys are safe to include in code.
"""

import os

# ─── Environment Variables ───────────────────────────────────────────────────
# These must be set in your environment (Render, .env file, etc.)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

# Webhook secrets - you have two endpoints configured
STRIPE_WEBHOOK_SECRET_SNAPSHOT = os.getenv("STRIPE_WEBHOOK_SECRET_SNAPSHOT")
STRIPE_WEBHOOK_SECRET_THIN = os.getenv("STRIPE_WEBHOOK_SECRET_THIN")

# Backwards compatibility - use snapshot by default
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", STRIPE_WEBHOOK_SECRET_SNAPSHOT)


# ─── Stripe Product IDs ──────────────────────────────────────────────────────
# These map your plan tiers to Stripe Product IDs

STRIPE_PRODUCTS = {
    "free": "prod_TWoKwNq2yIPmtO",
    "starter": "prod_TWoGtnRvv6ZsQD",
    "pro": "prod_TWoAdYWJkFxSSW",
    "ultra": "prod_TPIsyc97itUIrb",
    "extra_seat": "prod_TWmokORGiY8RQc",
}


# ─── Stripe Price Lookup Keys ────────────────────────────────────────────────
# Using lookup_keys instead of price IDs for easier management.
# These are configured in Stripe Dashboard when creating prices.

STRIPE_PRICE_LOOKUP_KEYS = {
    "free": {
        "monthly": "free_monthly",
        "yearly": "free_annual",
    },
    "starter": {
        "monthly": "starter_monthly",
        "yearly": "starter_annual",
    },
    "pro": {
        "monthly": "pro_monthly",
        "yearly": "pro_annual",
    },
    "ultra": {
        "monthly": "ultra_monthly",
        "yearly": "ultra_annual",
    },
    "extra_seat": {
        "monthly": "extra_seat_monthly",
        # No annual option for extra seats
    },
}


# ─── Helper Functions ────────────────────────────────────────────────────────

def get_product_id(plan_tier: str) -> str:
    """Get the Stripe Product ID for a plan tier."""
    return STRIPE_PRODUCTS.get(plan_tier.lower(), STRIPE_PRODUCTS["free"])


def get_price_lookup_key(plan_tier: str, billing_cycle: str = "monthly") -> str:
    """
    Get the Stripe Price lookup key for a plan tier and billing cycle.
    
    Args:
        plan_tier: One of 'free', 'starter', 'pro', 'ultra', 'extra_seat'
        billing_cycle: Either 'monthly' or 'yearly'
    
    Returns:
        The lookup key string (e.g., 'starter_monthly')
    """
    tier = plan_tier.lower()
    cycle = "yearly" if billing_cycle.lower() in ("yearly", "annual", "year") else "monthly"
    
    if tier not in STRIPE_PRICE_LOOKUP_KEYS:
        tier = "free"
    
    prices = STRIPE_PRICE_LOOKUP_KEYS[tier]
    return prices.get(cycle, prices.get("monthly", "free_monthly"))


def is_configured() -> bool:
    """Check if Stripe is properly configured."""
    return bool(STRIPE_SECRET_KEY and STRIPE_SECRET_KEY.startswith(("sk_test_", "sk_live_")))


def is_live_mode() -> bool:
    """Check if running in Stripe live mode (vs test mode)."""
    return bool(STRIPE_SECRET_KEY and STRIPE_SECRET_KEY.startswith("sk_live_"))


# ─── Webhook Event Types ─────────────────────────────────────────────────────
# Events we handle from Stripe webhooks

WEBHOOK_EVENTS = [
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_succeeded",
    "invoice.payment_failed",
    "invoice.upcoming",
    "payment_method.attached",
    "payment_method.detached",
    "customer.created",
    "customer.updated",
]


# ─── Subscription Settings ───────────────────────────────────────────────────

# Trial period settings (set to 0 to disable trials)
TRIAL_PERIOD_DAYS = {
    "free": 0,
    "starter": 0,  # Set to 14 if you want 14-day trials
    "pro": 0,
    "ultra": 0,
}

# Proration behavior when changing plans
# Options: 'create_prorations', 'none', 'always_invoice'
PRORATION_BEHAVIOR = "create_prorations"

# Cancel at period end (True) or immediately (False)
CANCEL_AT_PERIOD_END = True

