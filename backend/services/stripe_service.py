"""
Stripe Service - Payment and subscription management.
"""
import stripe
from typing import Optional
from backend.config import settings

# Initialize Stripe
stripe.api_key = settings.STRIPE_API_KEY


def create_checkout_session(
    user_id: str,
    user_email: str,
    tier: str,
    success_url: str,
    cancel_url: str,
    stripe_customer_id: Optional[str] = None,
) -> dict:
    """
    Create a Stripe Checkout session for subscription.
    
    Args:
        user_id: Internal user ID (stored in metadata)
        user_email: User's email for Stripe customer
        tier: Subscription tier (pro, unlimited)
        success_url: Redirect URL on successful payment
        cancel_url: Redirect URL on cancelled payment
        stripe_customer_id: Existing Stripe customer ID if available
    
    Returns:
        dict with session_id and url
    """
    if not settings.STRIPE_API_KEY:
        raise ValueError("Stripe API key not configured")

    # Determine price ID based on tier
    price_id = None
    if tier == "pro":
        price_id = settings.STRIPE_PRO_PRICE_ID
    elif tier == "unlimited":
        price_id = settings.STRIPE_UNLIMITED_PRICE_ID
    
    if not price_id:
        raise ValueError(f"No price configured for tier: {tier}")

    # Create or reuse customer
    customer_id = stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            email=user_email,
            metadata={"user_id": user_id},
        )
        customer_id = customer.id

    # Create checkout session
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[
            {
                "price": price_id,
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user_id, "tier": tier},
    )

    return {
        "session_id": session.id,
        "url": session.url,
        "customer_id": customer_id,
    }


def handle_webhook(payload: bytes, signature: str) -> dict:
    """
    Process Stripe webhook events.
    
    Args:
        payload: Raw webhook payload bytes
        signature: Stripe-Signature header value
    
    Returns:
        dict with event type and relevant data
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise ValueError("Stripe webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]

    result = {"event_type": event_type, "processed": False}

    if event_type == "checkout.session.completed":
        # Payment successful, activate subscription
        result["user_id"] = data.get("metadata", {}).get("user_id")
        result["tier"] = data.get("metadata", {}).get("tier")
        result["customer_id"] = data.get("customer")
        result["subscription_id"] = data.get("subscription")
        result["processed"] = True

    elif event_type == "customer.subscription.updated":
        # Subscription changed (upgrade/downgrade)
        result["subscription_id"] = data.get("id")
        result["status"] = data.get("status")
        result["processed"] = True

    elif event_type == "customer.subscription.deleted":
        # Subscription cancelled
        result["subscription_id"] = data.get("id")
        result["cancelled"] = True
        result["processed"] = True

    elif event_type == "invoice.payment_failed":
        # Payment failed
        result["customer_id"] = data.get("customer")
        result["subscription_id"] = data.get("subscription")
        result["payment_failed"] = True
        result["processed"] = True

    return result


def create_portal_session(stripe_customer_id: str, return_url: str) -> str:
    """
    Create a Stripe Customer Portal session for subscription management.
    
    Args:
        stripe_customer_id: Stripe customer ID
        return_url: URL to return to after portal session
    
    Returns:
        Portal session URL
    """
    if not stripe_customer_id:
        raise ValueError("No Stripe customer ID provided")

    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=return_url,
    )

    return session.url


def cancel_subscription(stripe_subscription_id: str) -> dict:
    """
    Cancel a Stripe subscription at period end.
    
    Args:
        stripe_subscription_id: Stripe subscription ID
    
    Returns:
        Cancelled subscription details
    """
    if not stripe_subscription_id:
        raise ValueError("No subscription ID provided")

    subscription = stripe.Subscription.modify(
        stripe_subscription_id,
        cancel_at_period_end=True,
    )

    return {
        "id": subscription.id,
        "status": subscription.status,
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "current_period_end": subscription.current_period_end,
    }


def reactivate_subscription(stripe_subscription_id: str) -> dict:
    """
    Reactivate a subscription that was set to cancel.
    
    Args:
        stripe_subscription_id: Stripe subscription ID
    
    Returns:
        Updated subscription details
    """
    subscription = stripe.Subscription.modify(
        stripe_subscription_id,
        cancel_at_period_end=False,
    )

    return {
        "id": subscription.id,
        "status": subscription.status,
        "cancel_at_period_end": subscription.cancel_at_period_end,
    }


# ============================================================================
# REFUND HANDLING
# ============================================================================

def create_refund(
    payment_intent_id: str,
    amount_cents: Optional[int] = None,
    reason: str = "requested_by_customer",
) -> dict:
    """
    Create a refund for a payment.
    
    Args:
        payment_intent_id: Stripe PaymentIntent ID to refund
        amount_cents: Amount to refund in cents (None = full refund)
        reason: Reason code (requested_by_customer, duplicate, fraudulent)
    
    Returns:
        Refund details including id, amount, and status
    
    Example:
        # Full refund
        create_refund("pi_xxx")
        
        # Partial refund of $25
        create_refund("pi_xxx", amount_cents=2500)
    """
    if not payment_intent_id:
        raise ValueError("No payment intent ID provided")
    
    refund_params = {
        "payment_intent": payment_intent_id,
        "reason": reason,
    }
    
    if amount_cents is not None:
        refund_params["amount"] = amount_cents
    
    refund = stripe.Refund.create(**refund_params)
    
    return {
        "id": refund.id,
        "amount": refund.amount,
        "currency": refund.currency,
        "status": refund.status,  # succeeded, pending, failed
        "reason": refund.reason,
        "created": refund.created,
    }


def get_refund_status(refund_id: str) -> dict:
    """
    Get the status of a refund.
    
    Args:
        refund_id: Stripe Refund ID
    
    Returns:
        Refund details
    """
    refund = stripe.Refund.retrieve(refund_id)
    
    return {
        "id": refund.id,
        "amount": refund.amount,
        "status": refund.status,
        "failure_reason": refund.failure_reason,
    }


def list_refunds_for_payment(payment_intent_id: str) -> list:
    """
    List all refunds for a payment intent.
    
    Args:
        payment_intent_id: Stripe PaymentIntent ID
    
    Returns:
        List of refund objects
    """
    refunds = stripe.Refund.list(payment_intent=payment_intent_id)
    
    return [
        {
            "id": r.id,
            "amount": r.amount,
            "status": r.status,
            "created": r.created,
        }
        for r in refunds.data
    ]


# ============================================================================
# PAYMENT FAILURE HANDLING
# ============================================================================

def retry_invoice_payment(invoice_id: str) -> dict:
    """
    Retry payment for a failed invoice.
    
    Args:
        invoice_id: Stripe Invoice ID
    
    Returns:
        Invoice status after retry attempt
    """
    invoice = stripe.Invoice.pay(invoice_id)
    
    return {
        "id": invoice.id,
        "status": invoice.status,
        "paid": invoice.paid,
        "amount_due": invoice.amount_due,
        "amount_paid": invoice.amount_paid,
    }


def get_failed_invoices(customer_id: str) -> list:
    """
    Get list of failed/unpaid invoices for a customer.
    
    Args:
        customer_id: Stripe Customer ID
    
    Returns:
        List of unpaid invoices
    """
    invoices = stripe.Invoice.list(
        customer=customer_id,
        status="open",  # Unpaid invoices
    )
    
    return [
        {
            "id": inv.id,
            "amount_due": inv.amount_due,
            "currency": inv.currency,
            "due_date": inv.due_date,
            "attempt_count": inv.attempt_count,
            "next_payment_attempt": inv.next_payment_attempt,
        }
        for inv in invoices.data
    ]


def update_payment_method(
    customer_id: str,
    payment_method_id: str,
    set_as_default: bool = True,
) -> dict:
    """
    Update a customer's payment method.
    
    Args:
        customer_id: Stripe Customer ID
        payment_method_id: New Stripe PaymentMethod ID
        set_as_default: Whether to set as default payment method
    
    Returns:
        Updated customer info
    """
    # Attach payment method to customer
    stripe.PaymentMethod.attach(
        payment_method_id,
        customer=customer_id,
    )
    
    if set_as_default:
        # Set as default for invoices
        stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": payment_method_id},
        )
    
    return {
        "customer_id": customer_id,
        "payment_method_id": payment_method_id,
        "set_as_default": set_as_default,
    }

