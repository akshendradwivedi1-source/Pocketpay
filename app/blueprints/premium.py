from flask import Blueprint, request
from flask_login import current_user
from app.utils.helpers import json_response, error_response, validate_required_fields, api_login_required
from app.services.premium_service import PremiumService

bp = Blueprint('premium', __name__)


@bp.route('/status', methods=['GET'])
@api_login_required
def get_premium_status():
    """Returns current user's subscription tier, features, and active status"""
    sub = current_user.current_subscription
    is_active = current_user.is_premium_active
    return json_response({
        'is_premium': is_active,
        'subscription': sub.to_dict() if sub else None,
        'subscription_status': sub.status if sub else ('ACTIVE' if is_active else 'NONE'),
        'plans': PremiumService.get_plans()
    })


@bp.route('/plans', methods=['GET'])
def get_premium_plans():
    """Returns available subscription tiers and pricing"""
    return json_response({
        'plans': PremiumService.get_plans(),
        'currency': 'INR'
    })


@bp.route('/create-checkout-order', methods=['POST'])
@api_login_required
def create_checkout_order():
    """
    Creates a legitimate payment gateway order (Razorpay / Stripe) for Premium checkout.
    No card or sensitive financial details are handled by PocketPay.
    """
    data = request.get_json() or {}
    plan_id = data.get('plan_id') or data.get('plan') or 'monthly'

    try:
        order = PremiumService.create_order(current_user, plan_id=plan_id)
        return json_response(order, "Checkout order created successfully", 201)
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        return error_response(f"Failed to create checkout order: {str(e)}", 500)


@bp.route('/verify-payment', methods=['POST'])
@api_login_required
def verify_payment():
    """
    Verifies cryptographic payment signature from payment gateway and activates Premium.
    """
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['order_id', 'payment_id'])
    if not valid:
        return error_response(msg, 400)

    order_id = str(data.get('order_id', '')).strip()
    payment_id = str(data.get('payment_id', '')).strip()
    signature = str(data.get('signature', '')).strip()

    res = PremiumService.verify_payment(current_user, order_id, payment_id, signature)
    if not res.get('success'):
        return error_response(res.get('error', 'Payment verification failed'), 400, code=res.get('code'))

    return json_response(res, res.get('message', 'Premium activated successfully'))


@bp.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Payment gateway webhook endpoint with signature verification.
    Processes subscription payments, renewals, and cancellations idempotently.
    """
    raw_payload = request.get_data()
    signature = request.headers.get('X-Razorpay-Signature') or request.headers.get('Stripe-Signature') or ''

    res = PremiumService.process_webhook(raw_payload, signature)
    if not res.get('success'):
        return error_response(res.get('error', 'Webhook processing failed'), 400, code=res.get('code'))

    return json_response(res, 'Webhook processed successfully')


@bp.route('/cancel', methods=['POST'])
@api_login_required
def cancel_subscription():
    """Cancels renewal while maintaining access until expiry date"""
    res = PremiumService.cancel_subscription(current_user)
    if not res.get('success'):
        return error_response(res.get('error', 'Failed to cancel subscription'), 400, code=res.get('code'))

    return json_response(res, res.get('message', 'Subscription cancelled'))
