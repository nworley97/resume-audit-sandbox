# stripe_service.py
"""
Stripe payment service - Mock implementation with easy switch to real Stripe.

This module provides a payment processing interface that can work in two modes:
1. MOCK MODE (default): Simulates Stripe for testing without a real account
2. LIVE MODE: Uses real Stripe API (just set STRIPE_SECRET_KEY env var)

To switch to real Stripe:
1. Set environment variable: STRIPE_SECRET_KEY=sk_live_xxx or sk_test_xxx
2. Set environment variable: STRIPE_PUBLISHABLE_KEY=pk_live_xxx or pk_test_xxx
3. (Optional) Set STRIPE_WEBHOOK_SECRET for webhook verification

Test card numbers for Stripe Test Mode:
- Success: 4242 4242 4242 4242
- Decline: 4000 0000 0000 0002
- Requires Auth: 4000 0025 0000 3155
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# ─── Configuration ──────────────────────────────────────────────────────────

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Check if we should use real Stripe
USE_REAL_STRIPE = bool(STRIPE_SECRET_KEY and STRIPE_SECRET_KEY.startswith(("sk_test_", "sk_live_")))

if USE_REAL_STRIPE:
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        logger.info("Stripe initialized in LIVE/TEST mode")
    except ImportError:
        USE_REAL_STRIPE = False
        logger.warning("stripe package not installed, falling back to mock mode")
else:
    logger.info("Stripe running in MOCK mode (no API key set)")


# ─── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class PaymentResult:
    """Result of a payment attempt."""
    success: bool
    payment_id: str
    customer_id: str
    subscription_id: Optional[str] = None
    error_message: Optional[str] = None
    card_last4: Optional[str] = None
    card_brand: Optional[str] = None
    card_exp_month: Optional[int] = None
    card_exp_year: Optional[int] = None


@dataclass
class CustomerInfo:
    """Customer information for display."""
    customer_id: str
    email: str
    name: Optional[str] = None
    card_last4: Optional[str] = None
    card_brand: Optional[str] = None
    card_exp_month: Optional[int] = None
    card_exp_year: Optional[int] = None


# ─── Mock Stripe Implementation ─────────────────────────────────────────────

class MockStripe:
    """
    Mock Stripe implementation for testing.
    Simulates all Stripe operations locally.
    """
    
    # Test card numbers and their behaviors
    TEST_CARDS = {
        "4242424242424242": {"success": True, "brand": "visa"},
        "4000056655665556": {"success": True, "brand": "visa"},  # Visa Debit
        "5555555555554444": {"success": True, "brand": "mastercard"},
        "378282246310005": {"success": True, "brand": "amex"},
        "4000000000000002": {"success": False, "error": "Your card was declined."},
        "4000000000009995": {"success": False, "error": "Your card has insufficient funds."},
        "4000000000000069": {"success": False, "error": "Your card has expired."},
        "4000000000000127": {"success": False, "error": "Your card's security code is incorrect."},
    }
    
    # In-memory storage for mock data
    _customers: Dict[str, Dict] = {}
    _subscriptions: Dict[str, Dict] = {}
    _payment_methods: Dict[str, Dict] = {}
    
    @classmethod
    def validate_card(cls, card_number: str) -> Tuple[bool, Optional[str], str]:
        """
        Validate a card number.
        Returns (is_valid, error_message, brand)
        """
        # Remove spaces and dashes
        card_number = card_number.replace(" ", "").replace("-", "")
        
        # Check if it's a known test card
        if card_number in cls.TEST_CARDS:
            card_info = cls.TEST_CARDS[card_number]
            if card_info["success"]:
                return True, None, card_info["brand"]
            else:
                return False, card_info.get("error", "Card declined"), card_info.get("brand", "unknown")
        
        # For any other card that looks valid (16 digits, passes Luhn), accept it
        if len(card_number) >= 13 and len(card_number) <= 19 and card_number.isdigit():
            if cls._luhn_check(card_number):
                brand = cls._detect_brand(card_number)
                return True, None, brand
        
        return False, "Invalid card number", "unknown"
    
    @staticmethod
    def _luhn_check(card_number: str) -> bool:
        """Luhn algorithm for card validation."""
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return checksum % 10 == 0
    
    @staticmethod
    def _detect_brand(card_number: str) -> str:
        """Detect card brand from number."""
        if card_number.startswith("4"):
            return "visa"
        elif card_number.startswith(("51", "52", "53", "54", "55")):
            return "mastercard"
        elif card_number.startswith(("34", "37")):
            return "amex"
        elif card_number.startswith("6011"):
            return "discover"
        return "unknown"
    
    @classmethod
    def create_customer(cls, email: str, name: str = None) -> str:
        """Create a mock customer."""
        customer_id = f"cus_mock_{uuid.uuid4().hex[:14]}"
        cls._customers[customer_id] = {
            "id": customer_id,
            "email": email,
            "name": name,
            "created": datetime.utcnow().isoformat(),
        }
        return customer_id
    
    @classmethod
    def attach_payment_method(
        cls,
        customer_id: str,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvc: str
    ) -> Tuple[bool, Optional[str], Dict]:
        """
        Attach a payment method to a customer.
        Returns (success, error_message, payment_method_info)
        """
        is_valid, error, brand = cls.validate_card(card_number)
        
        if not is_valid:
            return False, error, {}
        
        pm_id = f"pm_mock_{uuid.uuid4().hex[:14]}"
        card_number_clean = card_number.replace(" ", "").replace("-", "")
        
        pm_info = {
            "id": pm_id,
            "customer_id": customer_id,
            "last4": card_number_clean[-4:],
            "brand": brand,
            "exp_month": exp_month,
            "exp_year": exp_year,
        }
        
        cls._payment_methods[pm_id] = pm_info
        
        # Update customer with default payment method
        if customer_id in cls._customers:
            cls._customers[customer_id]["default_payment_method"] = pm_id
        
        return True, None, pm_info
    
    @classmethod
    def create_subscription(
        cls,
        customer_id: str,
        plan_tier: str,
        billing_cycle: str,
        amount: float
    ) -> Tuple[bool, Optional[str], Dict]:
        """
        Create a mock subscription.
        Returns (success, error_message, subscription_info)
        """
        # Check customer has payment method
        customer = cls._customers.get(customer_id)
        if not customer:
            return False, "Customer not found", {}
        
        pm_id = customer.get("default_payment_method")
        if not pm_id or pm_id not in cls._payment_methods:
            return False, "No payment method on file", {}
        
        pm = cls._payment_methods[pm_id]
        
        # Create subscription
        sub_id = f"sub_mock_{uuid.uuid4().hex[:14]}"
        now = datetime.utcnow()
        
        if billing_cycle == "yearly":
            period_end = now.replace(year=now.year + 1)
        else:
            if now.month == 12:
                period_end = now.replace(year=now.year + 1, month=1)
            else:
                try:
                    period_end = now.replace(month=now.month + 1)
                except ValueError:
                    period_end = now.replace(month=now.month + 1, day=28)
        
        sub_info = {
            "id": sub_id,
            "customer_id": customer_id,
            "plan_tier": plan_tier,
            "billing_cycle": billing_cycle,
            "amount": amount,
            "status": "active",
            "current_period_start": now.isoformat(),
            "current_period_end": period_end.isoformat(),
            "payment_method": pm,
        }
        
        cls._subscriptions[sub_id] = sub_info
        
        return True, None, sub_info
    
    @classmethod
    def cancel_subscription(cls, subscription_id: str) -> Tuple[bool, Optional[str]]:
        """Cancel a subscription."""
        if subscription_id not in cls._subscriptions:
            return False, "Subscription not found"
        
        cls._subscriptions[subscription_id]["status"] = "canceled"
        cls._subscriptions[subscription_id]["canceled_at"] = datetime.utcnow().isoformat()
        
        return True, None
    
    @classmethod
    def update_subscription(
        cls,
        subscription_id: str,
        plan_tier: str = None,
        billing_cycle: str = None
    ) -> Tuple[bool, Optional[str], Dict]:
        """Update a subscription."""
        if subscription_id not in cls._subscriptions:
            return False, "Subscription not found", {}
        
        sub = cls._subscriptions[subscription_id]
        
        if plan_tier:
            sub["plan_tier"] = plan_tier
        if billing_cycle:
            sub["billing_cycle"] = billing_cycle
        
        return True, None, sub
    
    @classmethod
    def charge_for_seats(
        cls,
        customer_id: str,
        num_seats: int,
        price_per_seat: float
    ) -> Tuple[bool, Optional[str], str]:
        """
        Charge for additional seats.
        Returns (success, error_message, payment_id)
        """
        customer = cls._customers.get(customer_id)
        if not customer:
            return False, "Customer not found", ""
        
        pm_id = customer.get("default_payment_method")
        if not pm_id:
            return False, "No payment method on file", ""
        
        payment_id = f"pi_mock_{uuid.uuid4().hex[:14]}"
        return True, None, payment_id


# ─── Unified Payment Service ────────────────────────────────────────────────

class PaymentService:
    """
    Unified payment service that works with both mock and real Stripe.
    """
    
    @staticmethod
    def is_mock_mode() -> bool:
        """Check if running in mock mode."""
        return not USE_REAL_STRIPE
    
    @staticmethod
    def get_publishable_key() -> str:
        """Get the publishable key for frontend."""
        if USE_REAL_STRIPE:
            return STRIPE_PUBLISHABLE_KEY or ""
        return "pk_mock_test_key"
    
    @staticmethod
    def create_customer(email: str, name: str = None, company: str = None) -> str:
        """Create a customer in Stripe/Mock."""
        if USE_REAL_STRIPE:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"company": company} if company else {}
            )
            return customer.id
        else:
            return MockStripe.create_customer(email, name)
    
    @staticmethod
    def process_signup(
        email: str,
        name: str,
        company: str,
        plan_tier: str,
        billing_cycle: str,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvc: str,
        amount: float
    ) -> PaymentResult:
        """
        Process a complete signup with payment.
        
        This is the main entry point for new customer registration.
        """
        if USE_REAL_STRIPE:
            return PaymentService._process_signup_stripe(
                email, name, company, plan_tier, billing_cycle,
                card_number, exp_month, exp_year, cvc, amount
            )
        else:
            return PaymentService._process_signup_mock(
                email, name, company, plan_tier, billing_cycle,
                card_number, exp_month, exp_year, cvc, amount
            )
    
    @staticmethod
    def _process_signup_mock(
        email: str,
        name: str,
        company: str,
        plan_tier: str,
        billing_cycle: str,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvc: str,
        amount: float
    ) -> PaymentResult:
        """Process signup using mock Stripe."""
        
        # Create customer
        customer_id = MockStripe.create_customer(email, name)
        
        # Attach payment method
        success, error, pm_info = MockStripe.attach_payment_method(
            customer_id, card_number, exp_month, exp_year, cvc
        )
        
        if not success:
            return PaymentResult(
                success=False,
                payment_id="",
                customer_id=customer_id,
                error_message=error
            )
        
        # Create subscription
        success, error, sub_info = MockStripe.create_subscription(
            customer_id, plan_tier, billing_cycle, amount
        )
        
        if not success:
            return PaymentResult(
                success=False,
                payment_id="",
                customer_id=customer_id,
                error_message=error
            )
        
        return PaymentResult(
            success=True,
            payment_id=f"pi_mock_{uuid.uuid4().hex[:14]}",
            customer_id=customer_id,
            subscription_id=sub_info["id"],
            card_last4=pm_info["last4"],
            card_brand=pm_info["brand"],
            card_exp_month=pm_info["exp_month"],
            card_exp_year=pm_info["exp_year"]
        )
    
    @staticmethod
    def _process_signup_stripe(
        email: str,
        name: str,
        company: str,
        plan_tier: str,
        billing_cycle: str,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvc: str,
        amount: float
    ) -> PaymentResult:
        """
        Process signup using real Stripe.
        
        Note: In production, you'd typically use Stripe Elements or Checkout
        instead of handling raw card numbers. This is simplified for the
        migration path.
        """
        try:
            # Create customer
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"company": company}
            )
            
            # Create payment method (in production, use Stripe.js/Elements)
            # This is a simplified flow - real implementation would use tokens
            payment_method = stripe.PaymentMethod.create(
                type="card",
                card={
                    "number": card_number.replace(" ", "").replace("-", ""),
                    "exp_month": exp_month,
                    "exp_year": exp_year,
                    "cvc": cvc,
                },
            )
            
            # Attach to customer
            stripe.PaymentMethod.attach(
                payment_method.id,
                customer=customer.id,
            )
            
            # Set as default
            stripe.Customer.modify(
                customer.id,
                invoice_settings={"default_payment_method": payment_method.id},
            )
            
            # Create subscription (you'd need to set up products/prices in Stripe)
            # For now, create a one-time payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Stripe uses cents
                currency="usd",
                customer=customer.id,
                payment_method=payment_method.id,
                confirm=True,
                metadata={
                    "plan_tier": plan_tier,
                    "billing_cycle": billing_cycle,
                }
            )
            
            return PaymentResult(
                success=True,
                payment_id=intent.id,
                customer_id=customer.id,
                subscription_id=None,  # Would be set if using Stripe Subscriptions
                card_last4=payment_method.card.last4,
                card_brand=payment_method.card.brand,
                card_exp_month=payment_method.card.exp_month,
                card_exp_year=payment_method.card.exp_year
            )
            
        except stripe.error.CardError as e:
            return PaymentResult(
                success=False,
                payment_id="",
                customer_id="",
                error_message=str(e.user_message)
            )
        except Exception as e:
            logger.error(f"Stripe error: {e}")
            return PaymentResult(
                success=False,
                payment_id="",
                customer_id="",
                error_message="Payment processing failed. Please try again."
            )
    
    @staticmethod
    def charge_additional_seats(
        customer_id: str,
        num_seats: int,
        price_per_seat: float = 20.0
    ) -> Tuple[bool, Optional[str], str]:
        """
        Charge for additional seats.
        Returns (success, error_message, payment_id)
        """
        amount = num_seats * price_per_seat
        
        if USE_REAL_STRIPE:
            try:
                intent = stripe.PaymentIntent.create(
                    amount=int(amount * 100),
                    currency="usd",
                    customer=customer_id,
                    confirm=True,
                    metadata={"type": "extra_seats", "quantity": num_seats}
                )
                return True, None, intent.id
            except stripe.error.CardError as e:
                return False, str(e.user_message), ""
            except Exception as e:
                logger.error(f"Stripe error charging for seats: {e}")
                return False, "Payment failed", ""
        else:
            return MockStripe.charge_for_seats(customer_id, num_seats, price_per_seat)
    
    @staticmethod
    def update_payment_method(
        customer_id: str,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvc: str
    ) -> Tuple[bool, Optional[str], Dict]:
        """Update the payment method for a customer."""
        if USE_REAL_STRIPE:
            try:
                payment_method = stripe.PaymentMethod.create(
                    type="card",
                    card={
                        "number": card_number.replace(" ", "").replace("-", ""),
                        "exp_month": exp_month,
                        "exp_year": exp_year,
                        "cvc": cvc,
                    },
                )
                
                stripe.PaymentMethod.attach(
                    payment_method.id,
                    customer=customer_id,
                )
                
                stripe.Customer.modify(
                    customer_id,
                    invoice_settings={"default_payment_method": payment_method.id},
                )
                
                return True, None, {
                    "last4": payment_method.card.last4,
                    "brand": payment_method.card.brand,
                    "exp_month": payment_method.card.exp_month,
                    "exp_year": payment_method.card.exp_year,
                }
            except stripe.error.CardError as e:
                return False, str(e.user_message), {}
            except Exception as e:
                logger.error(f"Stripe error updating payment method: {e}")
                return False, "Failed to update payment method", {}
        else:
            return MockStripe.attach_payment_method(
                customer_id, card_number, exp_month, exp_year, cvc
            )


# ─── Utility Functions ──────────────────────────────────────────────────────

def format_card_display(brand: str, last4: str) -> str:
    """Format card for display (e.g., 'Visa ending in 4242')."""
    brand_display = {
        "visa": "Visa",
        "mastercard": "Mastercard",
        "amex": "American Express",
        "discover": "Discover",
    }.get(brand.lower(), brand.title())
    
    return f"{brand_display} ending in {last4}"


def get_test_card_info() -> Dict[str, str]:
    """Get test card information for display in mock mode."""
    return {
        "success_card": "4242 4242 4242 4242",
        "decline_card": "4000 0000 0000 0002",
        "exp_date": "Any future date (e.g., 12/25)",
        "cvc": "Any 3 digits (e.g., 123)",
        "zip": "Any 5 digits (e.g., 12345)",
    }

