# billing_routes.py
"""
Billing and subscription routes - Flask Blueprint.

This blueprint handles:
- Public pricing page
- New user signup with plan selection
- Checkout and payment processing
- Account billing management
- Seat purchasing
- Enterprise contact

ADDITIVE: This is a new blueprint that doesn't modify existing routes.
"""

from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, jsonify, g
)
from flask_login import login_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from db import SessionLocal
from models import Tenant, User
from plans_config import (
    get_all_plans_for_display, get_plan_price, get_plan_limit,
    PLAN_PRICING, PLAN_LIMITS, PLAN_TIERS, YEARLY_DISCOUNT_PERCENT,
    EXTRA_SEAT_PRICE_MONTHLY, ENTERPRISE_CONTACT_EMAIL,
    get_limit_notification, get_feature_notification, has_feature_access
)
from stripe_service import PaymentService, get_test_card_info
from subscription_models import (
    TenantSubscription, TenantUsage, PaymentHistory, PendingSignup,
    ensure_subscription_schema, get_tenant_subscription,
    get_usage_summary, check_can_post_job, check_can_add_seat,
    increment_resume_usage
)

# Create Blueprint
billing_bp = Blueprint('billing', __name__, url_prefix='/billing')


# ─── Initialize Schema ──────────────────────────────────────────────────────

@billing_bp.before_app_request
def _init_subscription_schema():
    """Ensure subscription tables exist on first request."""
    if not getattr(g, '_subscription_schema_checked', False):
        ensure_subscription_schema()
        g._subscription_schema_checked = True


# ─── Context Processor ──────────────────────────────────────────────────────

@billing_bp.context_processor
def inject_billing_context():
    """Inject billing-related context into templates."""
    return {
        "is_mock_mode": PaymentService.is_mock_mode(),
        "test_card_info": get_test_card_info() if PaymentService.is_mock_mode() else None,
        "enterprise_email": ENTERPRISE_CONTACT_EMAIL,
        "extra_seat_price": EXTRA_SEAT_PRICE_MONTHLY,
        "yearly_discount": YEARLY_DISCOUNT_PERCENT,
        "now": datetime.now,  # For dynamic year calculations in templates
    }


# ─── Public Routes ──────────────────────────────────────────────────────────

@billing_bp.route('/pricing')
def pricing():
    """Public pricing page."""
    plans = get_all_plans_for_display()
    return render_template(
        'billing/pricing.html',
        plans=plans,
        yearly_discount=YEARLY_DISCOUNT_PERCENT,
    )


@billing_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    New user signup with plan selection.
    GET: Show plan selection and signup form
    POST: Process signup (redirect to Stripe payment link or create free account)
    """
    plans = get_all_plans_for_display()
    
    if request.method == 'POST':
        plan_tier = request.form.get('plan_tier', 'free')
        billing_cycle = request.form.get('billing_cycle', 'monthly')
        email = request.form.get('email', '').strip().lower()  # Normalize email
        password = request.form.get('password', '')
        company_name = request.form.get('company_name', '').strip()
        full_name = request.form.get('full_name', '').strip()
        
        # Validate inputs before proceeding
        errors = []
        if not email:
            errors.append('Email is required')
        elif '@' not in email:
            errors.append('Please enter a valid email address')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters')
        if not company_name:
            errors.append('Company name is required')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('billing.signup', plan=plan_tier, cycle=billing_cycle))
        
        # Store form data in session (for payment success page display)
        session['signup_data'] = {
            'plan_tier': plan_tier,
            'billing_cycle': billing_cycle,
            'email': email,
            'company_name': company_name,
            'full_name': full_name,
        }
        
        db = SessionLocal()
        try:
            # Check if email already exists
            existing_user = db.query(User).filter(User.username == email).first()
            if existing_user:
                flash('An account with this email already exists. Please log in.', 'error')
                session.pop('signup_data', None)
                return redirect(url_for('login'))
            
            # Store signup data for webhook to use (all plans go through Stripe payment links)
            existing_pending = db.query(PendingSignup).filter(
                PendingSignup.email == email
            ).first()
            
            if existing_pending:
                # Update existing pending signup
                existing_pending.plan_tier = plan_tier
                existing_pending.billing_cycle = billing_cycle
                existing_pending.company_name = company_name
                existing_pending.full_name = full_name
                existing_pending.password_hash = generate_password_hash(password)
                existing_pending.created_at = datetime.utcnow()
                existing_pending.expires_at = datetime.utcnow() + timedelta(hours=24)
                existing_pending.processed = False
            else:
                pending = PendingSignup(
                    email=email,
                    plan_tier=plan_tier,
                    billing_cycle=billing_cycle,
                    company_name=company_name,
                    full_name=full_name,
                    password_hash=generate_password_hash(password),
                    expires_at=datetime.utcnow() + timedelta(hours=24),
                )
                db.add(pending)
            
            db.commit()
        except Exception as e:
            db.rollback()
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('billing.signup'))
        finally:
            db.close()
        
        # Get Stripe payment link for paid plans
        from stripe_config import get_payment_link
        from urllib.parse import quote
        
        payment_link = get_payment_link(plan_tier, billing_cycle)
        
        if not payment_link:
            flash('Payment link not configured for this plan. Please contact support.', 'error')
            return redirect(url_for('billing.signup'))
        
        # Prefill email in Stripe payment link to ensure webhook can match the pending signup
        # Stripe Payment Links support ?prefilled_email= parameter
        payment_link_with_email = f"{payment_link}?prefilled_email={quote(email)}"
        
        # Redirect to Stripe payment link
        return redirect(payment_link_with_email)
    
    # Pre-select plan from query param
    selected_plan = request.args.get('plan', 'starter')
    selected_cycle = request.args.get('cycle', 'monthly')
    
    return render_template(
        'billing/signup.html',
        plans=plans,
        selected_plan=selected_plan,
        selected_cycle=selected_cycle,
        yearly_discount=YEARLY_DISCOUNT_PERCENT,
    )


@billing_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    """
    DEPRECATED: Payment checkout page with direct card entry.
    
    This route is kept for backwards compatibility but is no longer the
    primary signup flow. New signups use Stripe Payment Links instead.
    
    GET: Show payment form
    POST: Process payment
    """
    signup_data = session.get('signup_data')
    
    if not signup_data:
        flash('Please select a plan first.')
        return redirect(url_for('billing.signup'))
    
    plan_tier = signup_data.get('plan_tier', 'free')
    billing_cycle = signup_data.get('billing_cycle', 'monthly')
    amount = get_plan_price(plan_tier, billing_cycle)
    
    if request.method == 'POST':
        # Validate form data
        email = signup_data.get('email', '').strip()
        password = signup_data.get('password', '')
        company_name = signup_data.get('company_name', '').strip()
        full_name = signup_data.get('full_name', '').strip()
        
        # Card details from form
        card_number = request.form.get('card_number', '').strip()
        exp_month = request.form.get('exp_month', '')
        exp_year = request.form.get('exp_year', '')
        cvc = request.form.get('cvc', '').strip()
        
        # Validation
        errors = []
        if not email:
            errors.append('Email is required')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters')
        if not company_name:
            errors.append('Company name is required')
        if not card_number:
            errors.append('Card number is required')
        if not exp_month or not exp_year:
            errors.append('Expiration date is required')
        if not cvc:
            errors.append('CVC is required')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template(
                'billing/checkout.html',
                signup_data=signup_data,
                plan_tier=plan_tier,
                billing_cycle=billing_cycle,
                amount=amount,
                plan_display=PLAN_PRICING[plan_tier]['display_name'],
            )
        
        db = SessionLocal()
        try:
            # Check if email already exists
            existing_user = db.query(User).filter(User.username == email).first()
            if existing_user:
                flash('An account with this email already exists. Please log in.', 'error')
                return redirect(url_for('login'))
            
            # Process payment
            result = PaymentService.process_signup(
                email=email,
                name=full_name,
                company=company_name,
                plan_tier=plan_tier,
                billing_cycle=billing_cycle,
                card_number=card_number,
                exp_month=int(exp_month),
                exp_year=int(exp_year),
                cvc=cvc,
                amount=amount
            )
            
            if not result.success:
                flash(result.error_message or 'Payment failed. Please try again.', 'error')
                return render_template(
                    'billing/checkout.html',
                    signup_data=signup_data,
                    plan_tier=plan_tier,
                    billing_cycle=billing_cycle,
                    amount=amount,
                    plan_display=PLAN_PRICING[plan_tier]['display_name'],
                )
            
            # Create tenant
            tenant_slug = company_name.lower().replace(' ', '-').replace('.', '')[:20]
            # Ensure unique slug
            base_slug = tenant_slug
            counter = 1
            while db.query(Tenant).filter(Tenant.slug == tenant_slug).first():
                tenant_slug = f"{base_slug}-{counter}"
                counter += 1
            
            tenant = Tenant(
                slug=tenant_slug,
                display_name=company_name,
            )
            db.add(tenant)
            db.flush()  # Get tenant.id
            
            # Create user
            user = User(
                username=email,
                tenant_id=tenant.id,
            )
            user.set_pw(password)
            db.add(user)
            db.flush()  # Get user.id
            
            # Create subscription record
            now = datetime.utcnow()
            subscription = TenantSubscription(
                tenant_id=tenant.id,
                plan_tier=plan_tier,
                billing_cycle=billing_cycle,
                status='active',
                created_at=now,
                current_period_start=now,
                stripe_customer_id=result.customer_id,
                stripe_subscription_id=result.subscription_id,
                payment_method_last4=result.card_last4,
                payment_method_brand=result.card_brand,
                payment_method_exp_month=result.card_exp_month,
                payment_method_exp_year=result.card_exp_year,
            )
            db.add(subscription)
            
            # Record payment
            payment = PaymentHistory(
                tenant_id=tenant.id,
                amount=amount,
                currency='USD',
                description=f"{PLAN_PRICING[plan_tier]['display_name']} plan - {billing_cycle}",
                status='succeeded',
                plan_tier=plan_tier,
                billing_cycle=billing_cycle,
                stripe_payment_intent_id=result.payment_id,
                payment_method_last4=result.card_last4,
                payment_method_brand=result.card_brand,
            )
            db.add(payment)
            
            # Create initial usage record
            period_end = subscription.get_period_end_date()
            usage = TenantUsage(
                tenant_id=tenant.id,
                period_start=now,
                period_end=period_end,
                resumes_reviewed=0,
            )
            db.add(usage)
            
            db.commit()
            
            # Clear signup session data
            session.pop('signup_data', None)
            
            # Log in the new user
            login_user(user)
            session['tenant_slug'] = tenant.slug
            
            flash('Welcome! Your account has been created successfully.', 'success')
            return redirect(url_for('recruiter', tenant=tenant.slug))
            
        except Exception as e:
            db.rollback()
            flash(f'An error occurred: {str(e)}', 'error')
            return render_template(
                'billing/checkout.html',
                signup_data=signup_data,
                plan_tier=plan_tier,
                billing_cycle=billing_cycle,
                amount=amount,
                plan_display=PLAN_PRICING[plan_tier]['display_name'],
            )
        finally:
            db.close()
    
    return render_template(
        'billing/checkout.html',
        signup_data=signup_data,
        plan_tier=plan_tier,
        billing_cycle=billing_cycle,
        amount=amount,
        plan_display=PLAN_PRICING[plan_tier]['display_name'],
    )


@billing_bp.route('/payment-success')
def payment_success():
    """
    Handle successful payment from Stripe payment link.
    
    Note: Account creation happens asynchronously via webhook.
    This page informs the user their account is being set up.
    """
    # Check if we have signup data in session
    signup_data = session.get('signup_data')
    
    # Also check if user was created by webhook and try to log them in
    if signup_data:
        db = SessionLocal()
        try:
            user = db.query(User).filter(
                User.username == signup_data.get('email', '').lower()
            ).first()
            if user:
                # Account was created by webhook, log them in
                login_user(user)
                session.pop('signup_data', None)
                tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
                if tenant:
                    session['tenant_slug'] = tenant.slug
                    flash('Welcome! Your account has been created successfully.', 'success')
                    return redirect(url_for('recruiter', tenant=tenant.slug))
        finally:
            db.close()
    
    if not signup_data:
        # User might have come directly here - redirect to signup
        flash('Please complete your account setup first.', 'error')
        return redirect(url_for('billing.signup'))
    
    # Account creation will be handled by webhook when payment succeeds
    return render_template('billing/payment_success.html', signup_data=signup_data)


@billing_bp.route('/payment-cancel')
def payment_cancel():
    """Handle canceled payment from Stripe payment link."""
    # Clear signup data and redirect back to signup
    session.pop('signup_data', None)
    flash('Payment was canceled. Please try again when ready.', 'info')
    return redirect(url_for('billing.signup'))


@billing_bp.route('/api/check-account-status')
def check_account_status():
    """
    API endpoint to check if account has been created after Stripe payment.
    Used by payment_success page to poll for account creation.
    """
    signup_data = session.get('signup_data')
    if not signup_data:
        return jsonify({'account_created': False, 'error': 'No signup session'})
    
    email = signup_data.get('email', '').lower()
    if not email:
        return jsonify({'account_created': False, 'error': 'No email in session'})
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == email).first()
        if user:
            # Account was created! Auto-login the user
            login_user(user)
            session.pop('signup_data', None)
            
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            tenant_slug = tenant.slug if tenant else ''
            
            if tenant:
                session['tenant_slug'] = tenant.slug
            
            return jsonify({
                'account_created': True,
                'redirect_url': url_for('recruiter', tenant=tenant_slug),
                'message': 'Account created successfully!'
            })
        else:
            return jsonify({'account_created': False})
    finally:
        db.close()


@billing_bp.route('/enterprise')
def enterprise():
    """Enterprise contact page."""
    return render_template(
        'billing/enterprise.html',
        contact_email=ENTERPRISE_CONTACT_EMAIL,
    )


@billing_bp.route('/notifications-demo')
def notifications_demo():
    """Demo page showing all notification types (for reference/testing)."""
    return render_template('billing/notifications_demo.html')


# ─── Authenticated Routes ───────────────────────────────────────────────────

@billing_bp.route('/account')
@login_required
def account():
    """Account billing management page."""
    if not current_user.tenant_id:
        flash('No billing account found.')
        return redirect(url_for('home'))
    
    db = SessionLocal()
    try:
        summary = get_usage_summary(current_user.tenant_id, db)
        
        # Get payment history
        payments = db.query(PaymentHistory).filter(
            PaymentHistory.tenant_id == current_user.tenant_id
        ).order_by(PaymentHistory.created_at.desc()).limit(10).all()
        
        # Get subscription
        subscription = db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == current_user.tenant_id
        ).first()
        
        return render_template(
            'billing/account.html',
            summary=summary,
            payments=payments,
            subscription=subscription,
            plans=get_all_plans_for_display(),
        )
    finally:
        db.close()


@billing_bp.route('/change-plan', methods=['GET', 'POST'])
@login_required
def change_plan():
    """Change subscription plan."""
    if not current_user.tenant_id:
        flash('No billing account found.')
        return redirect(url_for('home'))
    
    db = SessionLocal()
    try:
        subscription = db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == current_user.tenant_id
        ).first()
        
        if not subscription:
            flash('No subscription found.')
            return redirect(url_for('billing.signup'))
        
        if subscription.status == 'grandfathered':
            flash('Your account has grandfathered access and cannot be changed.')
            return redirect(url_for('billing.account'))
        
        if request.method == 'POST':
            new_tier = request.form.get('plan_tier')
            new_cycle = request.form.get('billing_cycle', subscription.billing_cycle)
            
            if new_tier not in PLAN_TIERS:
                flash('Invalid plan selected.')
                return redirect(url_for('billing.change_plan'))
            
            # Calculate new price
            new_amount = get_plan_price(new_tier, new_cycle)
            old_amount = get_plan_price(subscription.plan_tier, subscription.billing_cycle)
            
            # Update Stripe subscription if we have one
            if subscription.stripe_subscription_id:
                success, error, sub_info = PaymentService.update_subscription(
                    subscription.stripe_subscription_id,
                    new_tier,
                    new_cycle
                )
                
                if not success:
                    flash(error or 'Failed to update subscription. Please try again.', 'error')
                    return redirect(url_for('billing.change_plan'))
            
            # Update local subscription record
            subscription.plan_tier = new_tier
            subscription.billing_cycle = new_cycle
            
            # Record the change
            payment = PaymentHistory(
                tenant_id=current_user.tenant_id,
                amount=new_amount - old_amount if new_amount > old_amount else 0,
                currency='USD',
                description=f"Plan change to {PLAN_PRICING[new_tier]['display_name']} ({new_cycle})",
                status='succeeded',
                plan_tier=new_tier,
                billing_cycle=new_cycle,
                payment_method_last4=subscription.payment_method_last4,
                payment_method_brand=subscription.payment_method_brand,
            )
            db.add(payment)
            
            db.commit()
            
            flash(f'Plan updated to {PLAN_PRICING[new_tier]["display_name"]}!')
            return redirect(url_for('billing.account'))
        
        return render_template(
            'billing/change_plan.html',
            subscription=subscription,
            plans=get_all_plans_for_display(),
            current_tier=subscription.plan_tier,
        )
    finally:
        db.close()


@billing_bp.route('/add-seats', methods=['GET', 'POST'])
@login_required
def add_seats():
    """Add additional seats to subscription."""
    if not current_user.tenant_id:
        flash('No billing account found.')
        return redirect(url_for('home'))
    
    db = SessionLocal()
    try:
        subscription = db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == current_user.tenant_id
        ).first()
        
        if not subscription:
            flash('No subscription found.')
            return redirect(url_for('billing.signup'))
        
        if subscription.status == 'grandfathered':
            flash('Your account has grandfathered access with unlimited seats.')
            return redirect(url_for('billing.account'))
        
        # Check if we have a Stripe customer to charge
        if not subscription.stripe_customer_id:
            flash('Unable to process payment. Please contact support.', 'error')
            return redirect(url_for('billing.account'))
        
        if request.method == 'POST':
            num_seats = int(request.form.get('num_seats', 1))
            
            if num_seats < 1 or num_seats > 10:
                flash('Please select between 1 and 10 seats.')
                return redirect(url_for('billing.add_seats'))
            
            amount = num_seats * EXTRA_SEAT_PRICE_MONTHLY
            
            # Process payment
            success, error, payment_id = PaymentService.charge_additional_seats(
                subscription.stripe_customer_id,
                num_seats,
                EXTRA_SEAT_PRICE_MONTHLY
            )
            
            if not success:
                flash(error or 'Payment failed. Please try again.', 'error')
                return redirect(url_for('billing.add_seats'))
            
            # Update subscription
            subscription.extra_seats = (subscription.extra_seats or 0) + num_seats
            
            # Record payment
            payment = PaymentHistory(
                tenant_id=current_user.tenant_id,
                amount=amount,
                currency='USD',
                description=f"Added {num_seats} additional seat(s)",
                status='succeeded',
                extra_seats=num_seats,
                stripe_payment_intent_id=payment_id,
                payment_method_last4=subscription.payment_method_last4,
                payment_method_brand=subscription.payment_method_brand,
            )
            db.add(payment)
            
            db.commit()
            
            flash(f'Successfully added {num_seats} seat(s)!')
            return redirect(url_for('billing.account'))
        
        summary = get_usage_summary(current_user.tenant_id, db)
        
        return render_template(
            'billing/add_seats.html',
            subscription=subscription,
            summary=summary,
            seat_price=EXTRA_SEAT_PRICE_MONTHLY,
        )
    finally:
        db.close()


@billing_bp.route('/cancel-subscription', methods=['GET', 'POST'])
@login_required
def cancel_subscription():
    """Cancel the current subscription."""
    if not current_user.tenant_id:
        flash('No billing account found.')
        return redirect(url_for('home'))
    
    db = SessionLocal()
    try:
        subscription = db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == current_user.tenant_id
        ).first()
        
        if not subscription:
            flash('No subscription found.')
            return redirect(url_for('billing.signup'))
        
        if subscription.status == 'grandfathered':
            flash('Grandfathered accounts cannot be canceled.')
            return redirect(url_for('billing.account'))
        
        if subscription.status == 'canceled':
            flash('Subscription is already canceled.')
            return redirect(url_for('billing.account'))
        
        if request.method == 'POST':
            confirm = request.form.get('confirm', '') == 'yes'
            
            if not confirm:
                flash('Please confirm the cancellation.', 'error')
                return redirect(url_for('billing.cancel_subscription'))
            
            # Cancel in Stripe
            if subscription.stripe_subscription_id:
                success, error = PaymentService.cancel_subscription(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True  # Cancel at end of billing period
                )
                
                if not success:
                    flash(error or 'Failed to cancel subscription. Please try again.', 'error')
                    return redirect(url_for('billing.cancel_subscription'))
            
            # Update local record
            subscription.status = 'canceled'
            subscription.canceled_at = datetime.utcnow()
            
            db.commit()
            
            flash('Your subscription has been canceled. You will have access until the end of your billing period.')
            return redirect(url_for('billing.account'))
        
        return render_template(
            'billing/cancel_subscription.html',
            subscription=subscription,
        )
    finally:
        db.close()


@billing_bp.route('/update-payment', methods=['GET', 'POST'])
@login_required
def update_payment():
    """Update payment method."""
    if not current_user.tenant_id:
        flash('No billing account found.')
        return redirect(url_for('home'))
    
    db = SessionLocal()
    try:
        subscription = db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == current_user.tenant_id
        ).first()
        
        if not subscription:
            flash('No subscription found.')
            return redirect(url_for('billing.signup'))
        
        # Check if we have a Stripe customer
        if not subscription.stripe_customer_id:
            flash('Unable to update payment method. Please contact support.', 'error')
            return redirect(url_for('billing.account'))
        
        if request.method == 'POST':
            card_number = request.form.get('card_number', '').strip()
            exp_month = request.form.get('exp_month', '')
            exp_year = request.form.get('exp_year', '')
            cvc = request.form.get('cvc', '').strip()
            
            success, error, pm_info = PaymentService.update_payment_method(
                subscription.stripe_customer_id,
                card_number,
                int(exp_month),
                int(exp_year),
                cvc
            )
            
            if not success:
                flash(error or 'Failed to update payment method.', 'error')
                return redirect(url_for('billing.update_payment'))
            
            # Update subscription record
            subscription.payment_method_last4 = pm_info.get('last4')
            subscription.payment_method_brand = pm_info.get('brand')
            subscription.payment_method_exp_month = pm_info.get('exp_month')
            subscription.payment_method_exp_year = pm_info.get('exp_year')
            
            db.commit()
            
            flash('Payment method updated successfully!')
            return redirect(url_for('billing.account'))
        
        return render_template(
            'billing/update_payment.html',
            subscription=subscription,
        )
    finally:
        db.close()


# ─── API Endpoints ──────────────────────────────────────────────────────────

@billing_bp.route('/api/usage')
@login_required
def api_usage():
    """Get current usage summary as JSON."""
    if not current_user.tenant_id:
        return jsonify({'error': 'No tenant'}), 400
    
    db = SessionLocal()
    try:
        summary = get_usage_summary(current_user.tenant_id, db)
        return jsonify(summary)
    finally:
        db.close()


@billing_bp.route('/api/check-limit/<limit_type>')
@login_required
def api_check_limit(limit_type):
    """
    Check if a specific limit is reached.
    Returns notification data if limit reached, empty object if OK.
    """
    if not current_user.tenant_id:
        return jsonify({'error': 'No tenant'}), 400
    
    db = SessionLocal()
    try:
        subscription = get_tenant_subscription(current_user.tenant_id, db)
        
        if not subscription:
            return jsonify({'error': 'No subscription'}), 400
        
        # Grandfathered users have no limits
        if subscription.status == 'grandfathered':
            return jsonify({'limit_reached': False})
        
        limit_reached = False
        notification = None
        
        if limit_type == 'jobs':
            can_post, current, limit = check_can_post_job(current_user.tenant_id, db)
            limit_reached = not can_post
            if limit_reached:
                notification = get_limit_notification(subscription.plan_tier, 'jobs', current)
        
        elif limit_type == 'resumes':
            summary = get_usage_summary(current_user.tenant_id, db)
            limit_reached = summary['resumes_used'] >= summary['resumes_limit']
            if limit_reached:
                notification = get_limit_notification(subscription.plan_tier, 'resumes', summary['resumes_used'])
        
        elif limit_type == 'seats':
            can_add, current, limit = check_can_add_seat(current_user.tenant_id, db)
            limit_reached = not can_add
            if limit_reached:
                notification = get_limit_notification(subscription.plan_tier, 'seats', current)
        
        return jsonify({
            'limit_reached': limit_reached,
            'notification': notification if limit_reached else None,
        })
    finally:
        db.close()


@billing_bp.route('/api/check-feature/<feature_key>')
@login_required
def api_check_feature(feature_key):
    """
    Check if a feature is available on current plan.
    Returns notification data if not available, empty object if OK.
    """
    if not current_user.tenant_id:
        return jsonify({'error': 'No tenant'}), 400
    
    db = SessionLocal()
    try:
        subscription = get_tenant_subscription(current_user.tenant_id, db)
        
        if not subscription:
            return jsonify({'error': 'No subscription'}), 400
        
        # Grandfathered users have all features
        if subscription.status == 'grandfathered':
            return jsonify({'has_access': True})
        
        has_access = has_feature_access(subscription.plan_tier, feature_key)
        
        return jsonify({
            'has_access': has_access,
            'notification': get_feature_notification(feature_key, subscription.plan_tier) if not has_access else None,
        })
    finally:
        db.close()


# ─── Helper for Limit Enforcement ───────────────────────────────────────────

def require_limit(limit_type: str):
    """
    Decorator to enforce limits on routes.
    Shows notification and blocks action if limit reached.
    
    Usage:
        @app.route('/post-job')
        @require_limit('jobs')
        def post_job():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.tenant_id:
                return f(*args, **kwargs)
            
            db = SessionLocal()
            try:
                subscription = get_tenant_subscription(current_user.tenant_id, db)
                
                if not subscription or subscription.status == 'grandfathered':
                    return f(*args, **kwargs)
                
                limit_reached = False
                notification = None
                
                if limit_type == 'jobs':
                    can_do, current, limit = check_can_post_job(current_user.tenant_id, db)
                    limit_reached = not can_do
                    if limit_reached:
                        notification = get_limit_notification(subscription.plan_tier, 'jobs')
                
                elif limit_type == 'resumes':
                    summary = get_usage_summary(current_user.tenant_id, db)
                    limit_reached = summary['resumes_used'] >= summary['resumes_limit']
                    if limit_reached:
                        notification = get_limit_notification(subscription.plan_tier, 'resumes')
                
                elif limit_type == 'seats':
                    can_do, current, limit = check_can_add_seat(current_user.tenant_id, db)
                    limit_reached = not can_do
                    if limit_reached:
                        notification = get_limit_notification(subscription.plan_tier, 'seats')
                
                if limit_reached:
                    # Store notification in session for display
                    session['limit_notification'] = notification
                    flash(notification['message'], 'limit_reached')
                    
                    # Redirect based on action type
                    if notification.get('cta_action') == 'contact_sales':
                        return redirect(url_for('billing.enterprise'))
                    elif notification.get('cta_action') == 'add_seat':
                        return redirect(url_for('billing.add_seats'))
                    else:
                        return redirect(url_for('billing.change_plan'))
                
                return f(*args, **kwargs)
            finally:
                db.close()
        return decorated_function
    return decorator


def require_feature(feature_key: str):
    """
    Decorator to require a specific feature.
    Shows notification and blocks access if feature not available.
    
    Usage:
        @app.route('/analytics')
        @require_feature('full_analytics_engine')
        def analytics():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.tenant_id:
                return f(*args, **kwargs)
            
            db = SessionLocal()
            try:
                subscription = get_tenant_subscription(current_user.tenant_id, db)
                
                if not subscription or subscription.status == 'grandfathered':
                    return f(*args, **kwargs)
                
                if not has_feature_access(subscription.plan_tier, feature_key):
                    notification = get_feature_notification(feature_key, subscription.plan_tier)
                    session['limit_notification'] = notification
                    flash(notification['message'], 'feature_unavailable')
                    return redirect(url_for('billing.change_plan'))
                
                return f(*args, **kwargs)
            finally:
                db.close()
        return decorated_function
    return decorator

