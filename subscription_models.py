# subscription_models.py
"""
Subscription and billing models - ADDITIVE to existing models.py

This module adds subscription tracking without modifying existing models.
New tables are created to track:
- Tenant subscriptions (plan tier, billing cycle, status)
- Usage tracking (jobs, resumes, seats per billing period)
- Payment history (for audit trail)

IMPORTANT: This is designed to be non-disruptive to existing functionality.
Existing tenants without subscription records are treated as "grandfathered"
at the Ultra tier with unlimited access.
"""

from datetime import datetime, timedelta
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, 
    Float, ForeignKey, Text, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict
from db import Base, engine as models_engine
import enum


class SubscriptionStatus(enum.Enum):
    """Subscription status values."""
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    GRANDFATHERED = "grandfathered"  # For existing users before billing system


class BillingCycle(enum.Enum):
    """Billing cycle options."""
    MONTHLY = "monthly"
    YEARLY = "yearly"


class TenantSubscription(Base):
    """
    Subscription information for a tenant.
    One-to-one relationship with Tenant.
    
    If a tenant has no subscription record, they are considered "grandfathered"
    at the Ultra tier with full access.
    """
    __tablename__ = "tenant_subscription"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Plan details
    plan_tier = Column(String(20), nullable=False, default="free")  # free, starter, pro, ultra
    billing_cycle = Column(String(20), nullable=False, default="monthly")  # monthly, yearly
    status = Column(String(20), nullable=False, default="active")  # active, canceled, past_due, trialing, grandfathered
    
    # Subscription dates
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    current_period_start = Column(DateTime(timezone=True), default=datetime.utcnow)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    
    # Extra seats purchased (beyond what's included in plan)
    extra_seats = Column(Integer, default=0)
    
    # Stripe integration (for future real Stripe connection)
    stripe_customer_id = Column(String(100), nullable=True)
    stripe_subscription_id = Column(String(100), nullable=True)
    
    # Payment method info (masked for display)
    payment_method_last4 = Column(String(4), nullable=True)
    payment_method_brand = Column(String(20), nullable=True)  # visa, mastercard, etc.
    payment_method_exp_month = Column(Integer, nullable=True)
    payment_method_exp_year = Column(Integer, nullable=True)

    def is_active(self) -> bool:
        """Check if subscription is in good standing."""
        return self.status in ("active", "trialing", "grandfathered")
    
    def get_total_seats(self) -> int:
        """Get total seats available (included + extra)."""
        from plans_config import get_plan_limit
        included = get_plan_limit(self.plan_tier, "seats_included")
        return included + (self.extra_seats or 0)
    
    def get_period_end_date(self) -> datetime:
        """Calculate the end of the current billing period."""
        if self.current_period_end:
            return self.current_period_end
        
        start = self.current_period_start or self.created_at or datetime.utcnow()
        if self.billing_cycle == "yearly":
            # Add approximately one year
            try:
                end = start.replace(year=start.year + 1)
            except ValueError:
                # Handle Feb 29 -> Feb 28
                end = start.replace(year=start.year + 1, day=28)
        else:
            # Add one month
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                try:
                    end = start.replace(month=start.month + 1)
                except ValueError:
                    # Handle months with different day counts
                    end = start.replace(month=start.month + 1, day=28)
        return end


class TenantUsage(Base):
    """
    Usage tracking for a tenant within a billing period.
    Reset on subscription anniversary date.
    """
    __tablename__ = "tenant_usage"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    
    # Billing period this usage applies to
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    
    # Usage counters
    resumes_reviewed = Column(Integer, default=0)
    # Note: active_jobs is calculated from job_description table, not stored here
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class PendingSignup(Base):
    """
    Temporary storage for signup data before account creation.
    Used when redirecting to Stripe payment links - webhooks will use this
    to create accounts after payment succeeds.
    """
    __tablename__ = "pending_signup"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    
    # Signup form data (stored as JSON-like fields)
    plan_tier = Column(String(20), nullable=False)
    billing_cycle = Column(String(20), nullable=False)
    company_name = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)  # Hashed password
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)  # Clean up after 24 hours
    
    # Status tracking
    processed = Column(Boolean, default=False)  # Mark as processed when account created


class PaymentHistory(Base):
    """
    Record of all payments for audit trail.
    """
    __tablename__ = "payment_history"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    
    # Payment details
    amount = Column(Float, nullable=False)  # Amount in USD
    currency = Column(String(3), default="USD")
    description = Column(String(200), nullable=True)
    
    # Status
    status = Column(String(20), nullable=False)  # succeeded, failed, pending, refunded
    
    # Reference to what was paid for
    plan_tier = Column(String(20), nullable=True)
    billing_cycle = Column(String(20), nullable=True)
    extra_seats = Column(Integer, default=0)
    
    # Stripe reference (for future)
    stripe_payment_intent_id = Column(String(100), nullable=True)
    stripe_invoice_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Payment method used (for display)
    payment_method_last4 = Column(String(4), nullable=True)
    payment_method_brand = Column(String(20), nullable=True)


# ─── Schema Migration Helper ────────────────────────────────────────────────

def ensure_subscription_schema():
    """
    Create subscription tables if they don't exist.
    This is additive and safe to run multiple times.
    """
    from sqlalchemy import inspect
    
    insp = inspect(models_engine)
    existing_tables = insp.get_table_names()
    
    tables_to_create = []
    
    if "tenant_subscription" not in existing_tables:
        tables_to_create.append(TenantSubscription.__table__)
    
    if "tenant_usage" not in existing_tables:
        tables_to_create.append(TenantUsage.__table__)
    
    if "payment_history" not in existing_tables:
        tables_to_create.append(PaymentHistory.__table__)
    
    if "pending_signup" not in existing_tables:
        tables_to_create.append(PendingSignup.__table__)
    
    if tables_to_create:
        Base.metadata.create_all(models_engine, tables=tables_to_create)
        print(f"Created subscription tables: {[t.name for t in tables_to_create]}")


# ─── Helper Functions ───────────────────────────────────────────────────────

def get_tenant_subscription(tenant_id: int, db_session) -> TenantSubscription:
    """
    Get or create subscription for a tenant.
    
    Existing tenants without subscriptions are treated as grandfathered
    at the Ultra tier.
    """
    from models import Tenant
    
    sub = db_session.query(TenantSubscription).filter(
        TenantSubscription.tenant_id == tenant_id
    ).first()
    
    if sub:
        return sub
    
    # Check if tenant exists
    tenant = db_session.get(Tenant, tenant_id)
    if not tenant:
        return None
    
    # For existing tenants, return a "virtual" grandfathered subscription
    # We don't create a record - just return info indicating full access
    virtual_sub = TenantSubscription(
        tenant_id=tenant_id,
        plan_tier="ultra",
        billing_cycle="yearly",
        status="grandfathered",
        created_at=tenant.created_at,
        current_period_start=tenant.created_at,
    )
    # Don't add to session - this is a virtual object for existing tenants
    return virtual_sub


def get_or_create_current_usage(tenant_id: int, db_session) -> TenantUsage:
    """
    Get or create usage record for current billing period.
    """
    sub = get_tenant_subscription(tenant_id, db_session)
    if not sub:
        return None
    
    now = datetime.utcnow()
    period_start = sub.current_period_start or now
    period_end = sub.get_period_end_date()
    
    # Find existing usage for this period
    usage = db_session.query(TenantUsage).filter(
        TenantUsage.tenant_id == tenant_id,
        TenantUsage.period_start <= now,
        TenantUsage.period_end > now
    ).first()
    
    if usage:
        return usage
    
    # Create new usage record for this period
    usage = TenantUsage(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
        resumes_reviewed=0,
    )
    db_session.add(usage)
    db_session.commit()
    
    return usage


def increment_resume_usage(tenant_id: int, db_session) -> bool:
    """
    Increment resume usage counter.
    Returns True if successful, False if limit reached.
    """
    from plans_config import get_plan_limit
    
    sub = get_tenant_subscription(tenant_id, db_session)
    if not sub:
        return False
    
    # Grandfathered users have unlimited access
    if sub.status == "grandfathered":
        return True
    
    usage = get_or_create_current_usage(tenant_id, db_session)
    if not usage:
        return False
    
    limit = get_plan_limit(sub.plan_tier, "monthly_resumes")
    
    if usage.resumes_reviewed >= limit:
        return False
    
    usage.resumes_reviewed += 1
    usage.updated_at = datetime.utcnow()
    db_session.commit()
    
    return True


def check_can_post_job(tenant_id: int, db_session) -> tuple[bool, int, int]:
    """
    Check if tenant can post a new job.
    Returns (can_post, current_count, limit).
    """
    from plans_config import get_plan_limit
    from models import JobDescription
    
    sub = get_tenant_subscription(tenant_id, db_session)
    if not sub:
        return False, 0, 0
    
    # Grandfathered users have unlimited access
    if sub.status == "grandfathered":
        return True, 0, 999
    
    limit = get_plan_limit(sub.plan_tier, "active_jobs")
    
    # Count active jobs for this tenant
    active_count = db_session.query(JobDescription).filter(
        JobDescription.tenant_id == tenant_id,
        JobDescription.status == "active"
    ).count()
    
    return active_count < limit, active_count, limit


def check_can_add_seat(tenant_id: int, db_session) -> tuple[bool, int, int]:
    """
    Check if tenant can add a new user (seat).
    Returns (can_add, current_count, limit).
    """
    from models import User
    
    sub = get_tenant_subscription(tenant_id, db_session)
    if not sub:
        return False, 0, 0
    
    # Grandfathered users have unlimited access
    if sub.status == "grandfathered":
        return True, 0, 999
    
    total_seats = sub.get_total_seats()
    
    # Count users for this tenant
    user_count = db_session.query(User).filter(
        User.tenant_id == tenant_id
    ).count()
    
    return user_count < total_seats, user_count, total_seats


def get_usage_summary(tenant_id: int, db_session) -> dict:
    """
    Get complete usage summary for a tenant.
    """
    from plans_config import get_plan_limit, has_feature_access
    from models import JobDescription, User
    
    sub = get_tenant_subscription(tenant_id, db_session)
    if not sub:
        return None
    
    usage = get_or_create_current_usage(tenant_id, db_session) if sub.status != "grandfathered" else None
    
    # Count active jobs
    active_jobs = db_session.query(JobDescription).filter(
        JobDescription.tenant_id == tenant_id,
        JobDescription.status == "active"
    ).count()
    
    # Count users
    user_count = db_session.query(User).filter(
        User.tenant_id == tenant_id
    ).count()
    
    is_grandfathered = sub.status == "grandfathered"
    
    return {
        "plan_tier": sub.plan_tier,
        "plan_display": sub.plan_tier.title(),
        "billing_cycle": sub.billing_cycle,
        "status": sub.status,
        "is_grandfathered": is_grandfathered,
        
        # Limits
        "jobs_limit": 999 if is_grandfathered else get_plan_limit(sub.plan_tier, "active_jobs"),
        "resumes_limit": 999 if is_grandfathered else get_plan_limit(sub.plan_tier, "monthly_resumes"),
        "seats_limit": 999 if is_grandfathered else sub.get_total_seats(),
        
        # Current usage
        "jobs_used": active_jobs,
        "resumes_used": 0 if is_grandfathered else (usage.resumes_reviewed if usage else 0),
        "seats_used": user_count,
        
        # Feature access
        "has_claim_validity": is_grandfathered or has_feature_access(sub.plan_tier, "claim_validity_score"),
        "has_red_flag": is_grandfathered or has_feature_access(sub.plan_tier, "red_flag_detection"),
        "has_analytics": is_grandfathered or has_feature_access(sub.plan_tier, "full_analytics_engine"),
        
        # Billing info
        "period_end": sub.get_period_end_date() if not is_grandfathered else None,
        "extra_seats": sub.extra_seats or 0,
    }

