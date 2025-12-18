# plans_config.py
"""
Single source of truth for all subscription plan limits, pricing, and feature access.
Modify the values below to adjust plan offerings.

IMPORTANT: This file is intentionally simple and editable.
To change limits or pricing, just update the dictionaries below.
"""

from typing import Dict, List, Any

# ─── Plan Tiers ─────────────────────────────────────────────────────────────
# Order matters for comparison (index used for "higher tier" checks)
PLAN_TIERS = ["free", "starter", "pro", "ultra"]

# ─── Pricing Configuration ──────────────────────────────────────────────────
# All prices in USD
PLAN_PRICING = {
    "free": {
        "monthly_price": 0,
        "yearly_price": 0,
        "display_name": "Free",
        "tagline": "Get started for",
    },
    "starter": {
        "monthly_price": 49,
        "yearly_price": 382.20,  # ~35% savings
        "display_name": "Starter",
        "tagline": "",
    },
    "pro": {
        "monthly_price": 129,
        "yearly_price": 1006.20,  # ~35% savings
        "display_name": "Pro",
        "tagline": "",
    },
    "ultra": {
        "monthly_price": 239,
        "yearly_price": 1864.20,  # ~35% savings
        "display_name": "Ultra",
        "tagline": "",
    },
}

# ─── Plan Limits ────────────────────────────────────────────────────────────
# These are per-tenant limits (shared across all users in a tenant)
PLAN_LIMITS = {
    "free": {
        "active_jobs": 1,           # Number of active job postings allowed
        "monthly_resumes": 25,       # Resumes that can be reviewed per month
        "seats_included": 1,         # Number of user seats included
    },
    "starter": {
        "active_jobs": 3,
        "monthly_resumes": 100,
        "seats_included": 1,
    },
    "pro": {
        "active_jobs": 10,
        "monthly_resumes": 500,
        "seats_included": 3,
    },
    "ultra": {
        "active_jobs": 20,
        "monthly_resumes": 1000,
        "seats_included": 3,
    },
}

# ─── Extra Seat Pricing ─────────────────────────────────────────────────────
EXTRA_SEAT_PRICE_MONTHLY = 20  # USD per additional seat per month

# ─── Feature Access Matrix ──────────────────────────────────────────────────
# Maps feature keys to the list of plans that have access
FEATURE_ACCESS = {
    "job_relevancy_score": ["free", "starter", "pro", "ultra"],
    "job_board": ["free", "starter", "pro", "ultra"],
    "claim_validity_score": ["pro", "ultra"],
    "red_flag_detection": ["pro", "ultra"],
    "full_analytics_engine": ["ultra"],
    "dedicated_support": ["ultra"],
}

# Human-readable feature names for display
FEATURE_DISPLAY_NAMES = {
    "job_relevancy_score": "Job Relevancy Score",
    "job_board": "Job Board",
    "claim_validity_score": "Claim Validity Score",
    "red_flag_detection": "Red Flag Detection",
    "full_analytics_engine": "Full Analytics Engine",
    "dedicated_support": "Dedicated Support Rep",
}

# ─── Enterprise Contact ─────────────────────────────────────────────────────
ENTERPRISE_CONTACT_EMAIL = "sales@alterasf.com"

# ─── Yearly Discount ────────────────────────────────────────────────────────
YEARLY_DISCOUNT_PERCENT = 35  # Display text: "Save 35% Annually"


# ─── Helper Functions ───────────────────────────────────────────────────────

def get_plan_limit(plan_tier: str, limit_key: str) -> int:
    """Get a specific limit for a plan tier."""
    plan = plan_tier.lower() if plan_tier else "free"
    if plan not in PLAN_LIMITS:
        plan = "free"
    return PLAN_LIMITS[plan].get(limit_key, 0)


def get_plan_price(plan_tier: str, billing_cycle: str = "monthly") -> float:
    """Get the price for a plan tier and billing cycle."""
    plan = plan_tier.lower() if plan_tier else "free"
    if plan not in PLAN_PRICING:
        return 0
    
    if billing_cycle == "yearly":
        return PLAN_PRICING[plan]["yearly_price"]
    return PLAN_PRICING[plan]["monthly_price"]


def has_feature_access(plan_tier: str, feature_key: str) -> bool:
    """Check if a plan tier has access to a specific feature."""
    plan = plan_tier.lower() if plan_tier else "free"
    allowed_plans = FEATURE_ACCESS.get(feature_key, [])
    return plan in allowed_plans


def get_tier_index(plan_tier: str) -> int:
    """Get the index of a plan tier (for comparison)."""
    plan = plan_tier.lower() if plan_tier else "free"
    try:
        return PLAN_TIERS.index(plan)
    except ValueError:
        return 0


def is_higher_tier(plan_a: str, plan_b: str) -> bool:
    """Check if plan_a is a higher tier than plan_b."""
    return get_tier_index(plan_a) > get_tier_index(plan_b)


def get_upgrade_options(current_plan: str) -> List[str]:
    """Get list of plans that are upgrades from the current plan."""
    current_index = get_tier_index(current_plan)
    return PLAN_TIERS[current_index + 1:]


def get_all_plans_for_display() -> List[Dict[str, Any]]:
    """Get all plan information formatted for display in pricing page."""
    plans = []
    for tier in PLAN_TIERS:
        plan_info = {
            "tier": tier,
            "display_name": PLAN_PRICING[tier]["display_name"],
            "tagline": PLAN_PRICING[tier]["tagline"],
            "monthly_price": PLAN_PRICING[tier]["monthly_price"],
            "yearly_price": PLAN_PRICING[tier]["yearly_price"],
            "limits": PLAN_LIMITS[tier],
            "features": [],
        }
        
        # Add features this plan has access to
        for feature_key, allowed_plans in FEATURE_ACCESS.items():
            if tier in allowed_plans:
                plan_info["features"].append({
                    "key": feature_key,
                    "name": FEATURE_DISPLAY_NAMES.get(feature_key, feature_key),
                })
        
        plans.append(plan_info)
    
    return plans


# ─── Notification Messages ──────────────────────────────────────────────────
# Messages displayed when limits are reached (matches Figma designs)

def get_limit_notification(plan_tier: str, limit_type: str, current_value: int = 0) -> Dict[str, str]:
    """
    Get notification message and CTA for a specific limit type.
    
    Args:
        plan_tier: Current plan tier
        limit_type: One of 'seats', 'jobs', 'resumes'
        current_value: Current usage (optional, for display)
    
    Returns:
        Dict with 'title', 'message', 'cta_text', 'cta_action'
    """
    plan = plan_tier.lower() if plan_tier else "free"
    plan_display = PLAN_PRICING.get(plan, {}).get("display_name", "Free")
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    
    notifications = {
        "seats": {
            "title": "Seat limit reached",
            "message": f"The {plan_display} plan includes {limits['seats_included']} seat{'s' if limits['seats_included'] > 1 else ''}. Additional seats are available for ${EXTRA_SEAT_PRICE_MONTHLY}/month each.",
            "cta_text": "Add Seat",
            "cta_action": "add_seat",
        },
        "jobs": {
            "title": "Monthly job post limit reached" if plan != "free" else "No active job posts left",
            "message": _get_jobs_message(plan, plan_display, limits),
            "cta_text": "Contact Sales" if plan == "ultra" else "See Plans",
            "cta_action": "contact_sales" if plan == "ultra" else "see_plans",
        },
        "resumes": {
            "title": "Monthly resume limit reached",
            "message": _get_resumes_message(plan, plan_display, limits),
            "cta_text": "Contact Sales" if plan == "ultra" else "See Plans",
            "cta_action": "contact_sales" if plan == "ultra" else "see_plans",
        },
    }
    
    return notifications.get(limit_type, {
        "title": "Limit reached",
        "message": "You've reached your plan limit.",
        "cta_text": "See Plans",
        "cta_action": "see_plans",
    })


def _get_jobs_message(plan: str, plan_display: str, limits: dict) -> str:
    """Get the jobs limit message based on plan."""
    if plan == "free":
        return "You've used your 1 active job for this month. Upgrade to Starter to post more roles."
    elif plan == "starter":
        return f"You've posted all {limits['active_jobs']} active jobs available on Starter this month. Upgrade to Pro for up to 10 active jobs."
    elif plan == "pro":
        return f"You've posted all {limits['active_jobs']} active jobs available this month on Pro. Upgrade to Ultra for 20 active jobs per month."
    elif plan == "ultra":
        return f"You've hit your {limits['active_jobs']} active jobs for this month. Contact us for Enterprise-level scaling."
    return "You've reached your job posting limit."


def _get_resumes_message(plan: str, plan_display: str, limits: dict) -> str:
    """Get the resumes limit message based on plan."""
    if plan == "free":
        return f"You've reviewed all {limits['monthly_resumes']} resumes allowed this month. Upgrade to Starter to continue screening candidates."
    elif plan == "starter":
        return f"You've reached your {limits['monthly_resumes']}-resume monthly limit. Upgrade to Pro to review more candidates."
    elif plan == "pro":
        return f"You've used all {limits['monthly_resumes']} monthly resumes in your Pro plan. Upgrade to Ultra for unlimited monthly reviews."
    elif plan == "ultra":
        return f"You've used all {limits['monthly_resumes']} monthly resumes in your Ultra plan. Contact us for Enterprise-level scaling."
    return "You've reached your resume review limit."


def get_feature_notification(feature_key: str, current_plan: str) -> Dict[str, str]:
    """Get notification for when a feature is not available on current plan."""
    feature_name = FEATURE_DISPLAY_NAMES.get(feature_key, feature_key)
    allowed_plans = FEATURE_ACCESS.get(feature_key, [])
    
    # Find the lowest tier that has this feature
    upgrade_to = None
    for tier in PLAN_TIERS:
        if tier in allowed_plans:
            upgrade_to = PLAN_PRICING[tier]["display_name"]
            break
    
    if feature_key == "full_analytics_engine":
        return {
            "title": "Analytics not included",
            "message": "The full Analytics Engine is available only on Ultra and Enterprise plans.",
            "cta_text": "See Plans",
            "cta_action": "see_plans",
        }
    elif feature_key == "claim_validity_score":
        return {
            "title": "Feature not available",
            "message": "Claim Validity Scores are available on Pro and Ultra.",
            "cta_text": "See Plans",
            "cta_action": "see_plans",
        }
    else:
        return {
            "title": "Feature not available",
            "message": f"{feature_name} is available on {upgrade_to} and higher plans.",
            "cta_text": "See Plans",
            "cta_action": "see_plans",
        }

