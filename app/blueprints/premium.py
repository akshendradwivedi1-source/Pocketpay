from flask import Blueprint, request
from flask_login import current_user
from app.utils.helpers import (
    json_response, error_response, validate_required_fields,
    api_login_required, premium_required
)
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
        return error_response(f"Unable to create payment order: {str(e)}", 500)


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
        return error_response(res.get('error', 'Payment verification failed. Your Premium plan has not been activated.'), 400, code=res.get('code'))

    return json_response(res, res.get('message', 'Premium activated successfully'))


@bp.route('/pocketpay/initiate', methods=['POST'])
@bp.route('/pay/pocketpay/initiate', methods=['POST'])
@api_login_required
def initiate_pocketpay_payment():
    """
    Step 1 of PocketPay payment method:
    - Resolves PocketPay ID or UPI ID
    - Verifies sufficient balance
    - Generates and emails OTP to registered address
    """
    data = request.get_json() or {}
    plan_id = str(data.get('plan_id') or data.get('plan') or 'monthly').strip().lower()
    identifier = str(data.get('identifier') or data.get('pocketpay_id') or data.get('upi_id') or '').strip()

    res = PremiumService.initiate_pocketpay_payment(current_user, plan_id=plan_id, identifier=identifier)
    if not res.get('success'):
        return error_response(res.get('error', 'Unable to initiate PocketPay payment'), res.get('status_code', 400), code=res.get('code'), data=res.get('data'))

    return json_response(res, res.get('message', 'OTP sent to registered email'))


@bp.route('/pocketpay/confirm', methods=['POST'])
@bp.route('/pay/pocketpay/confirm', methods=['POST'])
@api_login_required
def confirm_pocketpay_payment():
    """
    Step 2 of PocketPay payment method:
    - Verifies OTP
    - Atomically checks balance and deducts subscription amount
    - Records proper Transaction in ledger
    - Activates Premium subscription
    """
    data = request.get_json() or {}
    plan_id = str(data.get('plan_id') or data.get('plan') or 'monthly').strip().lower()
    identifier = str(data.get('identifier') or data.get('pocketpay_id') or data.get('upi_id') or '').strip()
    otp = str(data.get('otp') or '').strip()

    if not otp:
        return error_response("Verification OTP is required to complete payment", 400, code="MISSING_OTP")

    res = PremiumService.confirm_pocketpay_payment(current_user, plan_id=plan_id, identifier=identifier, otp=otp)
    if not res.get('success'):
        return error_response(res.get('error', 'PocketPay payment failed'), res.get('status_code', 400), code=res.get('code'), data=res.get('data'))

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


# =============================================================================
# PART 2 & PART 4: PREMIUM PROTECTED API ENDPOINTS (@premium_required)
# =============================================================================

# 1. POCKET RULES ENGINE
@bp.route('/rules', methods=['GET'])
@premium_required
def list_rules():
    rules = PremiumService.get_rules(current_user)
    return json_response({'rules': rules})


@bp.route('/rules', methods=['POST'])
@premium_required
def create_rule():
    data = request.get_json() or {}
    try:
        rule = PremiumService.create_rule(current_user, data)
        return json_response({'rule': rule}, "Rule created successfully", 201)
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route('/rules/<int:rule_id>', methods=['PUT'])
@premium_required
def update_rule(rule_id):
    data = request.get_json() or {}
    try:
        rule = PremiumService.update_rule(current_user, rule_id, data)
        return json_response({'rule': rule}, "Rule updated successfully")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route('/rules/<int:rule_id>', methods=['DELETE'])
@premium_required
def delete_rule(rule_id):
    try:
        res = PremiumService.delete_rule(current_user, rule_id)
        return json_response(res, "Rule deleted successfully")
    except ValueError as e:
        return error_response(str(e), 404)


@bp.route('/rules/<int:rule_id>/toggle', methods=['POST'])
@premium_required
def toggle_rule(rule_id):
    data = request.get_json() or {}
    try:
        rule = PremiumService.toggle_rule(current_user, rule_id, data.get('is_active'))
        return json_response({'rule': rule}, "Rule status updated")
    except ValueError as e:
        return error_response(str(e), 404)


@bp.route('/rules/history', methods=['GET'])
@premium_required
def get_rule_history():
    rule_id = request.args.get('rule_id', type=int)
    history = PremiumService.get_rule_history(current_user, rule_id=rule_id)
    return json_response({'history': history})


# 2. POCKET LOCK
@bp.route('/pockets/<int:pocket_id>/lock', methods=['POST'])
@premium_required
def lock_pocket(pocket_id):
    data = request.get_json() or {}
    try:
        pocket = PremiumService.lock_pocket(current_user, pocket_id, data)
        return json_response({'pocket': pocket}, f'Pocket "{pocket["name"]}" is now locked.')
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route('/pockets/<int:pocket_id>/unlock', methods=['POST'])
@premium_required
def unlock_pocket(pocket_id):
    try:
        pocket = PremiumService.unlock_pocket(current_user, pocket_id)
        return json_response({'pocket': pocket}, f'Pocket "{pocket["name"]}" is now unlocked.')
    except ValueError as e:
        return error_response(str(e), 400)


# 3. FUTURE BALANCE FORECAST
@bp.route('/forecast', methods=['GET'])
@premium_required
def get_forecast():
    days = request.args.get('days', 30, type=int)
    forecast = PremiumService.get_balance_forecast(current_user, days=days)
    return json_response(forecast)


# 4. SUBSCRIPTION DETECTOR
@bp.route('/subscriptions/detected', methods=['GET'])
@premium_required
def get_detected_subscriptions():
    subs = PremiumService.detect_subscriptions(current_user)
    return json_response({'subscriptions': subs, 'total_detected': len(subs)})


@bp.route('/subscriptions/detected/<int:sub_id>/update', methods=['POST'])
@premium_required
def update_detected_sub(sub_id):
    data = request.get_json() or {}
    try:
        sub = PremiumService.update_detected_subscription(
            current_user,
            sub_id,
            is_confirmed=data.get('is_confirmed'),
            is_ignored=data.get('is_ignored')
        )
        return json_response({'subscription': sub}, "Subscription preference updated")
    except ValueError as e:
        return error_response(str(e), 404)


# 5. PAYMENT APPROVAL MODE
@bp.route('/approval-mode/settings', methods=['GET'])
@premium_required
def get_approval_settings():
    settings = PremiumService.get_approval_settings(current_user)
    return json_response(settings)


@bp.route('/approval-mode/settings', methods=['POST'])
@premium_required
def update_approval_settings():
    data = request.get_json() or {}
    enabled = data.get('require_payment_approval', data.get('enabled', False))
    threshold = data.get('payment_approval_threshold', data.get('threshold', 5000.0))
    try:
        res = PremiumService.update_approval_settings(current_user, enabled, threshold)
        return json_response(res, "Payment approval mode settings saved")
    except Exception as e:
        return error_response(str(e), 400)


# 6. POCKET SIMULATOR
@bp.route('/simulator/calculate', methods=['POST'])
@premium_required
def calculate_simulation():
    data = request.get_json() or {}
    income = data.get('income', 0.0)
    expenses = data.get('fixed_expenses', data.get('expenses', {}))
    res = PremiumService.calculate_simulation(income, expenses)
    return json_response(res)


@bp.route('/simulator/apply', methods=['POST'])
@premium_required
def apply_simulation():
    data = request.get_json() or {}
    try:
        res = PremiumService.apply_simulation(current_user, data)
        return json_response(res, "Simulation plan applied to your Pockets")
    except Exception as e:
        return error_response(str(e), 400)


# 7. PAYMENT ROUTING
@bp.route('/routing/preview', methods=['POST'])
@premium_required
def preview_payment_routing():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['amount'])
    if not valid:
        return error_response(msg, 400)
    amount = float(data.get('amount', 0))
    pref_ids = data.get('preferred_pocket_ids', [])
    res = PremiumService.preview_payment_routing(current_user, amount, preferred_pocket_ids=pref_ids)
    return json_response(res)


# 8. MONEY CONCIERGE
@bp.route('/concierge/ask', methods=['POST'])
@premium_required
def ask_concierge():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['question'])
    if not valid:
        return error_response(msg, 400)
    question = str(data.get('question', '')).strip()
    res = PremiumService.get_concierge_analysis(current_user, question)
    return json_response(res)
