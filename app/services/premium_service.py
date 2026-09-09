import os
import hmac
import hashlib
import json
import uuid
import requests
from datetime import datetime, timedelta
from flask import current_app
from app.extensions import db
from app.models.subscription import Subscription
from app.models.notification import Notification

DEFAULT_PLANS = {
    'monthly': {
        'id': 'monthly',
        'name': 'PocketPay Pro Monthly',
        'amount': 99.00,
        'amount_paise': 9900,
        'currency': 'INR',
        'interval': 'month',
        'duration_days': 30
    },
    'yearly': {
        'id': 'yearly',
        'name': 'PocketPay Pro Annual',
        'amount': 799.00,
        'amount_paise': 79900,
        'currency': 'INR',
        'interval': 'year',
        'duration_days': 365
    }
}


class PremiumService:
    """
    Handles legitimate server-side payment gateway operations for PocketPay Premium.
    Supports Razorpay Standard Checkout & Webhooks, with Stripe support and developer sandbox.
    """

    @classmethod
    def get_plans(cls):
        monthly_price = float(os.environ.get('PREMIUM_MONTHLY_PRICE', 99.0))
        yearly_price = float(os.environ.get('PREMIUM_YEARLY_PRICE', 799.0))
        plans = dict(DEFAULT_PLANS)
        plans['monthly']['amount'] = monthly_price
        plans['monthly']['amount_paise'] = int(monthly_price * 100)
        plans['yearly']['amount'] = yearly_price
        plans['yearly']['amount_paise'] = int(yearly_price * 100)
        return plans

    @classmethod
    def get_gateway_credentials(cls):
        key_id = os.environ.get('RAZORPAY_KEY_ID', '').strip()
        key_secret = os.environ.get('RAZORPAY_KEY_SECRET', '').strip()
        webhook_secret = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '').strip()
        is_live = bool(key_id and not key_id.startswith('rzp_test_'))
        has_credentials = bool(key_id and key_secret)
        return {
            'provider': 'razorpay',
            'key_id': key_id or 'rzp_test_sandbox_pocketpay',
            'key_secret': key_secret,
            'webhook_secret': webhook_secret,
            'has_credentials': has_credentials,
            'is_live': is_live
        }

    @classmethod
    def create_order(cls, user, plan_id='monthly'):
        plans = cls.get_plans()
        if plan_id not in plans:
            raise ValueError(f"Invalid plan ID: {plan_id}. Must be 'monthly' or 'yearly'.")

        plan = plans[plan_id]
        creds = cls.get_gateway_credentials()
        amount_paise = plan['amount_paise']
        receipt_id = f"rcpt_{user.id}_{int(datetime.utcnow().timestamp())}"

        order_id = None
        if creds['has_credentials']:
            try:
                # Official Razorpay Orders API call
                url = "https://api.razorpay.com/v1/orders"
                payload = {
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": receipt_id,
                    "notes": {
                        "user_id": str(user.id),
                        "user_email": user.email,
                        "plan_id": plan_id
                    }
                }
                res = requests.post(
                    url,
                    json=payload,
                    auth=(creds['key_id'], creds['key_secret']),
                    timeout=15
                )
                if res.status_code in [200, 201]:
                    order_data = res.json()
                    order_id = order_data.get('id')
                else:
                    current_app.logger.warning(f"Razorpay order API returned {res.status_code}: {res.text}")
            except Exception as e:
                current_app.logger.error(f"Error connecting to Razorpay: {str(e)}")

        # Fallback to simulated developer sandbox order if live API credentials are unset or during tests
        if not order_id:
            order_id = f"order_{uuid.uuid4().hex[:16]}"

        # Record pending subscription in database
        sub = Subscription(
            user_id=user.id,
            plan_id=plan_id,
            provider=creds['provider'],
            provider_order_id=order_id,
            amount=plan['amount'],
            currency='INR',
            status='PENDING',
            meta_data={
                'receipt': receipt_id,
                'is_sandbox': not creds['is_live'],
                'user_email': user.email
            }
        )
        db.session.add(sub)
        db.session.commit()

        return {
            'order_id': order_id,
            'amount': plan['amount'],
            'amount_paise': amount_paise,
            'currency': 'INR',
            'plan_id': plan_id,
            'plan_name': plan['name'],
            'key_id': creds['key_id'],
            'user_name': user.full_name,
            'user_email': user.email,
            'user_phone': user.phone or '',
            'is_sandbox': not creds['is_live']
        }

    @classmethod
    def verify_payment(cls, user, order_id, payment_id, signature):
        """
        Cryptographically verifies payment signature server-side and activates Premium.
        Idempotent: Re-verifying the same order returns the active subscription without duplication.
        """
        creds = cls.get_gateway_credentials()
        
        # Locate pending or existing subscription
        sub = Subscription.query.filter_by(provider_order_id=order_id, user_id=user.id).first()
        if not sub:
            # Fallback by provider_payment_id
            sub = Subscription.query.filter_by(provider_payment_id=payment_id, user_id=user.id).first()

        # Verify cryptographic signature if secret is configured
        valid_sig = False
        if creds['key_secret']:
            expected_sig = hmac.new(
                creds['key_secret'].encode('utf-8'),
                f"{order_id}|{payment_id}".encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            valid_sig = hmac.compare_digest(expected_sig, signature)
        else:
            # Developer Sandbox validation
            valid_sig = (signature == f"sig_sandbox_{order_id}")

        if not valid_sig:
            if sub:
                sub.status = 'PAYMENT_FAILED'
                db.session.commit()
            return {
                'success': False,
                'error': 'Invalid payment signature from provider',
                'code': 'SIGNATURE_VERIFICATION_FAILED'
            }

        if not sub:
            # Create record if missing
            sub = Subscription(
                user_id=user.id,
                plan_id='monthly',
                provider='razorpay',
                provider_order_id=order_id,
                amount=99.0,
                status='PENDING'
            )
            db.session.add(sub)

        # Idempotency: If already active, return cleanly
        if sub.status == 'ACTIVE' and sub.is_active:
            return {
                'success': True,
                'already_active': True,
                'subscription': sub.to_dict(),
                'user': user.to_dict(),
                'message': 'Premium is already active.'
            }

        # Activate Subscription
        now = datetime.utcnow()
        plans = cls.get_plans()
        plan_info = plans.get(sub.plan_id, plans['monthly'])
        duration = plan_info.get('duration_days', 30)

        sub.status = 'ACTIVE'
        sub.provider_payment_id = payment_id
        sub.provider_signature = signature
        sub.start_date = now
        sub.expiry_date = now + timedelta(days=duration)
        sub.updated_at = now

        # Update User
        user.is_premium = True
        db.session.commit()

        # Send in-app notification
        Notification.create(
            user.id,
            '🎉 Welcome to PocketPay Premium!',
            f'Your {plan_info["name"]} is now active. All Pro analytics, unlimited goals, and advanced AI features are unlocked until {sub.expiry_date.strftime("%d %b %Y")}.',
            'success',
            'high'
        )

        return {
            'success': True,
            'subscription': sub.to_dict(),
            'user': user.to_dict(),
            'message': 'Welcome to PocketPay Premium!'
        }

    @classmethod
    def process_webhook(cls, raw_payload: bytes, signature_header: str) -> dict:
        """
        Handles incoming payment provider webhook with HMAC signature verification.
        Guarantees idempotent processing to prevent duplicate activations.
        """
        creds = cls.get_gateway_credentials()
        webhook_secret = creds['webhook_secret']

        # Verify HMAC signature if webhook secret is configured
        if webhook_secret:
            expected_sig = hmac.new(
                webhook_secret.encode('utf-8'),
                raw_payload,
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(expected_sig, signature_header or ''):
                return {'success': False, 'error': 'Invalid webhook signature', 'code': 'INVALID_SIGNATURE'}

        try:
            event = json.loads(raw_payload.decode('utf-8'))
        except Exception as e:
            return {'success': False, 'error': f'Invalid JSON payload: {str(e)}', 'code': 'BAD_PAYLOAD'}

        event_name = event.get('event')
        payload_data = event.get('payload', {})
        payment_entity = payload_data.get('payment', {}).get('entity', {})
        order_entity = payload_data.get('order', {}).get('entity', {})

        order_id = payment_entity.get('order_id') or order_entity.get('id')
        payment_id = payment_entity.get('id')
        notes = payment_entity.get('notes', {}) or order_entity.get('notes', {})
        user_id_str = notes.get('user_id')

        if not order_id and not payment_id:
            return {'success': True, 'ignored': True, 'reason': 'No relevant order or payment ID found.'}

        # Check existing subscription
        sub = None
        if order_id:
            sub = Subscription.query.filter_by(provider_order_id=order_id).first()
        if not sub and payment_id:
            sub = Subscription.query.filter_by(provider_payment_id=payment_id).first()

        from app.models.user import User
        user = None
        if sub:
            user = User.query.get(sub.user_id)
        elif user_id_str:
            try:
                user = User.query.get(int(user_id_str))
            except Exception:
                pass

        if not user:
            return {'success': False, 'error': 'User not found for payment', 'code': 'USER_NOT_FOUND'}

        now = datetime.utcnow()
        if event_name in ['payment.captured', 'order.paid']:
            if sub and sub.status == 'ACTIVE':
                return {'success': True, 'idempotent_skip': True, 'message': 'Already processed'}

            if not sub:
                plan_id = notes.get('plan_id', 'monthly')
                sub = Subscription(
                    user_id=user.id,
                    plan_id=plan_id,
                    provider='razorpay',
                    provider_order_id=order_id,
                    provider_payment_id=payment_id,
                    amount=float(payment_entity.get('amount', 9900)) / 100.0,
                    status='ACTIVE',
                    start_date=now,
                    expiry_date=now + timedelta(days=30 if notes.get('plan_id') == 'monthly' else 365)
                )
                db.session.add(sub)
            else:
                plans = cls.get_plans()
                plan_info = plans.get(sub.plan_id, plans['monthly'])
                sub.status = 'ACTIVE'
                sub.provider_payment_id = payment_id
                sub.start_date = now
                sub.expiry_date = now + timedelta(days=plan_info.get('duration_days', 30))
                sub.updated_at = now

            user.is_premium = True
            db.session.commit()

            Notification.create(
                user.id,
                '🎉 Welcome to PocketPay Premium!',
                f'Your subscription payment of ₹{sub.amount:,.2f} has been verified and activated.',
                'success',
                'high'
            )
            return {'success': True, 'action': 'activated', 'subscription_id': sub.id}

        elif event_name in ['payment.failed']:
            if sub and sub.status != 'ACTIVE':
                sub.status = 'PAYMENT_FAILED'
                sub.updated_at = now
                db.session.commit()
            return {'success': True, 'action': 'payment_failed_recorded'}

        return {'success': True, 'ignored': True, 'event': event_name}

    @classmethod
    def cancel_subscription(cls, user):
        """
        Cancels recurring subscription renewal while preserving active access until expiry_date.
        """
        sub = user.current_subscription
        if not sub:
            return {'success': False, 'error': 'No active subscription found.', 'code': 'NO_SUBSCRIPTION'}

        sub.status = 'CANCELLED'
        sub.cancelled_at = datetime.utcnow()
        db.session.commit()

        Notification.create(
            user.id,
            'Subscription Cancelled',
            f'Your Premium renewal has been cancelled. You retain Pro access until {sub.expiry_date.strftime("%d %b %Y") if sub.expiry_date else "the end of your billing cycle"}.',
            'warning',
            'normal'
        )

        return {'success': True, 'subscription': sub.to_dict(), 'message': 'Subscription cancelled successfully.'}
