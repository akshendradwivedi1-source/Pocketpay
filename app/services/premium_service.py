import os
import re
import hmac
import hashlib
import json
import uuid
import requests
from datetime import datetime, timedelta
from flask import current_app
from app.extensions import db
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.subscription import Subscription, PocketRule, PocketRuleExecution, DetectedSubscription
from app.models.notification import Notification
from app.models.goal import SavingsGoal

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
    Also houses the backend logic for Part 2 Premium Suite features.
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
        # Check if already active
        if user.is_premium_active:
            raise ValueError("You already have an active PocketPay Premium membership.")

        plans = cls.get_plans()
        if plan_id not in plans:
            raise ValueError(f"Invalid plan ID: {plan_id}. Must be 'monthly' or 'yearly'.")

        plan = plans[plan_id]
        creds = cls.get_gateway_credentials()
        amount_paise = plan['amount_paise']
        receipt_id = f"rcpt_{user.id}_{int(datetime.utcnow().timestamp())}"

        # If strict live gateway is mandated via env, check credentials explicitly
        require_live = os.environ.get('REQUIRE_LIVE_PAYMENT', '').lower() in ['1', 'true']
        if require_live and not creds['has_credentials']:
            raise ValueError("Payment gateway configuration is incomplete. Razorpay credentials (RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET) are missing.")

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

        # Clean sandbox fallback order if live API credentials are unset or during development/testing
        is_sandbox = not creds['is_live'] or not order_id
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
                'is_sandbox': is_sandbox,
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
            'is_sandbox': is_sandbox,
            'sandbox': is_sandbox
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

    # =========================================================================
    # PART 2.1: POCKET RULES ENGINE
    # =========================================================================
    @classmethod
    def get_rules(cls, user):
        rules = PocketRule.query.filter_by(user_id=user.id).order_by(PocketRule.created_at.desc()).all()
        return [r.to_dict() for r in rules]

    @classmethod
    def create_rule(cls, user, data):
        target_pocket_id = data.get('target_pocket_id')
        if not target_pocket_id:
            raise ValueError("Target pocket is required for an automation rule.")

        target_pocket = Pocket.query.filter_by(id=target_pocket_id, user_id=user.id, archived=False).first()
        if not target_pocket:
            raise ValueError("Target pocket not found or not owned by user.")

        source_pocket_id = data.get('source_pocket_id')
        if source_pocket_id:
            source_pocket = Pocket.query.filter_by(id=source_pocket_id, user_id=user.id, archived=False).first()
            if not source_pocket:
                raise ValueError("Source pocket not found or not owned by user.")

        name = str(data.get('name', '')).strip() or f"Rule to {target_pocket.name}"
        trigger_type = data.get('trigger_type', 'INCOME_RECEIVED')
        action_type = data.get('action_type', 'ALLOCATE_PERCENT')

        trigger_threshold = data.get('trigger_threshold')
        if trigger_threshold is not None:
            trigger_threshold = round(float(trigger_threshold), 2)

        action_value = float(data.get('action_value', data.get('percentage', data.get('amount', 0.0))))
        if action_value <= 0:
            raise ValueError("Action value must be greater than zero.")

        rule = PocketRule(
            user_id=user.id,
            name=name,
            source_pocket_id=source_pocket_id,
            target_pocket_id=target_pocket_id,
            rule_type=data.get('rule_type', 'smart_allocation'),
            trigger_type=trigger_type,
            trigger_threshold=trigger_threshold,
            action_type=action_type,
            action_value=action_value,
            percentage=action_value if action_type == 'ALLOCATE_PERCENT' else None,
            amount=action_value if action_type == 'MOVE_FIXED_AMOUNT' else 0.0,
            is_active=bool(data.get('is_active', True)),
            description=data.get('description', '')
        )
        db.session.add(rule)
        db.session.commit()
        return rule.to_dict()

    @classmethod
    def update_rule(cls, user, rule_id, data):
        rule = PocketRule.query.filter_by(id=rule_id, user_id=user.id).first()
        if not rule:
            raise ValueError("Automation rule not found.")

        if 'name' in data:
            rule.name = str(data['name']).strip() or rule.name
        if 'is_active' in data:
            rule.is_active = bool(data['is_active'])
        if 'trigger_type' in data:
            rule.trigger_type = data['trigger_type']
        if 'trigger_threshold' in data:
            rule.trigger_threshold = round(float(data['trigger_threshold']), 2) if data['trigger_threshold'] is not None else None
        if 'action_type' in data:
            rule.action_type = data['action_type']
        if 'action_value' in data:
            val = float(data['action_value'])
            rule.action_value = val
            if rule.action_type == 'ALLOCATE_PERCENT':
                rule.percentage = val
            else:
                rule.amount = val
        if 'target_pocket_id' in data:
            tp = Pocket.query.filter_by(id=data['target_pocket_id'], user_id=user.id, archived=False).first()
            if not tp:
                raise ValueError("Target pocket not found.")
            rule.target_pocket_id = tp.id
        if 'source_pocket_id' in data:
            sp_id = data['source_pocket_id']
            if sp_id:
                sp = Pocket.query.filter_by(id=sp_id, user_id=user.id, archived=False).first()
                if not sp:
                    raise ValueError("Source pocket not found.")
                rule.source_pocket_id = sp.id
            else:
                rule.source_pocket_id = None
        if 'description' in data:
            rule.description = data['description']

        rule.updated_at = datetime.utcnow()
        db.session.commit()
        return rule.to_dict()

    @classmethod
    def delete_rule(cls, user, rule_id):
        rule = PocketRule.query.filter_by(id=rule_id, user_id=user.id).first()
        if not rule:
            raise ValueError("Automation rule not found.")
        db.session.delete(rule)
        db.session.commit()
        return {'success': True, 'deleted_rule_id': rule_id}

    @classmethod
    def toggle_rule(cls, user, rule_id, is_active=None):
        rule = PocketRule.query.filter_by(id=rule_id, user_id=user.id).first()
        if not rule:
            raise ValueError("Automation rule not found.")
        if is_active is None:
            rule.is_active = not rule.is_active
        else:
            rule.is_active = bool(is_active)
        rule.updated_at = datetime.utcnow()
        db.session.commit()
        return rule.to_dict()

    @classmethod
    def get_rule_history(cls, user, rule_id=None):
        query = PocketRuleExecution.query.filter_by(user_id=user.id)
        if rule_id:
            query = query.filter_by(rule_id=rule_id)
        executions = query.order_by(PocketRuleExecution.created_at.desc()).limit(50).all()
        return [e.to_dict() for e in executions]

    @classmethod
    def evaluate_rules_on_credit(cls, user, transaction):
        """
        Evaluates active rules when money is deposited or received.
        Idempotent: Guarantees no rule is ever executed twice for the same qualifying transaction.
        """
        if not user.is_premium_active:
            return []

        active_rules = PocketRule.query.filter_by(user_id=user.id, is_active=True).all()
        executed_records = []

        for rule in active_rules:
            # 1. Check idempotency: Never execute twice for same transaction
            existing_exec = PocketRuleExecution.query.filter_by(
                rule_id=rule.id,
                trigger_transaction_id=transaction.id
            ).first()
            if existing_exec:
                continue

            # 2. Check trigger conditions
            qualifies = False
            amount_to_move = 0.0

            if rule.trigger_type in ['INCOME_RECEIVED', 'RECURRING_INCOME']:
                if transaction.type in ['income', 'topup', 'peer_receive']:
                    qualifies = True
                    if rule.action_type == 'ALLOCATE_PERCENT':
                        pct = float(rule.action_value or rule.percentage or 0.0)
                        amount_to_move = round(transaction.amount * (pct / 100.0), 2)
                    else:
                        amount_to_move = round(float(rule.action_value or rule.amount or 0.0), 2)
            elif rule.trigger_type == 'BALANCE_EXCEEDS':
                threshold = float(rule.trigger_threshold or 0.0)
                current_bal = float(user.wallet_balance or 0.0)
                if current_bal > threshold:
                    qualifies = True
                    if rule.action_type == 'ALLOCATE_PERCENT':
                        excess = current_bal - threshold
                        amount_to_move = round(excess * (float(rule.action_value or 0.0) / 100.0), 2)
                    else:
                        amount_to_move = min(round(float(rule.action_value or 0.0), 2), current_bal)

            if not qualifies or amount_to_move <= 0:
                continue

            # 3. Check target pocket availability
            target_pocket = Pocket.query.filter_by(id=rule.target_pocket_id, user_id=user.id, archived=False).first()
            if not target_pocket:
                continue

            # 4. Check available funds
            avail = float(user.wallet_balance or 0.0)
            if avail < amount_to_move:
                amount_to_move = avail  # allocate remaining available or skip

            if amount_to_move <= 0:
                continue

            # 5. Execute atomic transfer
            try:
                user.wallet_balance = round(avail - amount_to_move, 2)
                target_pocket.current_balance = round(float(target_pocket.current_balance or 0.0) + amount_to_move, 2)
                target_pocket.total_received = round(float(target_pocket.total_received or 0.0) + amount_to_move, 2)

                # Record rule execution
                execution = PocketRuleExecution(
                    rule_id=rule.id,
                    user_id=user.id,
                    trigger_transaction_id=transaction.id,
                    executed_amount=amount_to_move,
                    status='SUCCESS',
                    details=f"Auto-allocated ₹{amount_to_move:,.2f} to {target_pocket.name} via Rule #{rule.id} ({rule.name})"
                )
                db.session.add(execution)

                rule.last_executed_at = datetime.utcnow()
                rule.execution_count = (rule.execution_count or 0) + 1
                rule.last_status = 'EXECUTED'
                db.session.commit()

                Notification.create(
                    user.id,
                    '⚡ Smart Rule Executed',
                    f'PocketPay Rule "{rule.name}" moved ₹{amount_to_move:,.2f} to {target_pocket.name}.',
                    'success',
                    'normal',
                    pocket_id=target_pocket.id
                )
                executed_records.append(execution.to_dict())
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Rule execution failed: {str(e)}")

        return executed_records

    # =========================================================================
    # PART 2.2: POCKET LOCK
    # =========================================================================
    @classmethod
    def lock_pocket(cls, user, pocket_id, data):
        pocket = Pocket.query.filter_by(id=pocket_id, user_id=user.id).first()
        if not pocket:
            raise ValueError("Pocket not found.")
        if pocket.archived:
            raise ValueError("Archived pockets cannot be locked.")

        until_date_str = data.get('locked_until_date') or data.get('until_date')
        goal_amount = data.get('locked_goal_amount') or data.get('goal_amount')
        reason = str(data.get('lock_reason') or data.get('reason') or '').strip()

        until_date = None
        if until_date_str:
            try:
                until_date = datetime.fromisoformat(until_date_str.replace('Z', '+00:00'))
            except Exception:
                until_date = datetime.strptime(until_date_str[:10], '%Y-%m-%d')

        pocket.is_locked = True
        pocket.locked_until_date = until_date
        pocket.locked_goal_amount = round(float(goal_amount), 2) if goal_amount else None
        pocket.lock_reason = reason or "Protected savings goal"
        pocket.updated_at = datetime.utcnow()
        db.session.commit()

        Notification.create(
            user.id,
            '🔒 Pocket Locked',
            f'"{pocket.name}" has been locked ({pocket.lock_reason}). Its funds cannot be spent in normal payments until unlocked.',
            'info',
            'high',
            pocket_id=pocket.id
        )

        return pocket.to_dict()

    @classmethod
    def unlock_pocket(cls, user, pocket_id):
        pocket = Pocket.query.filter_by(id=pocket_id, user_id=user.id).first()
        if not pocket:
            raise ValueError("Pocket not found.")

        pocket.is_locked = False
        pocket.locked_until_date = None
        pocket.locked_goal_amount = None
        pocket.lock_reason = None
        pocket.updated_at = datetime.utcnow()
        db.session.commit()

        Notification.create(
            user.id,
            '🔓 Pocket Unlocked',
            f'"{pocket.name}" has been unlocked. Its funds are now available for payments.',
            'success',
            'normal',
            pocket_id=pocket.id
        )

        return pocket.to_dict()

    # =========================================================================
    # PART 2.3: FUTURE BALANCE FORECAST
    # =========================================================================
    @classmethod
    def get_balance_forecast(cls, user, days=30):
        wallet_bal = round(float(user.wallet_balance or 0.0), 2)
        active_pockets = Pocket.query.filter_by(user_id=user.id, archived=False).all()
        pockets_bal = round(sum(float(p.current_balance or 0.0) for p in active_pockets), 2)
        locked_bal = round(sum(float(p.current_balance or 0.0) for p in active_pockets if p.is_currently_locked()), 2)
        actual_total_balance = round(wallet_bal + pockets_bal, 2)

        # Look back over past 60 days
        sixty_days_ago = datetime.utcnow() - timedelta(days=60)
        recent_txs = Transaction.query.filter(
            Transaction.user_id == user.id,
            Transaction.created_at >= sixty_days_ago,
            Transaction.status == 'completed'
        ).all()

        total_income_60d = sum(float(t.amount) for t in recent_txs if t.type in ['income', 'topup', 'peer_receive'])
        total_expense_60d = sum(float(t.amount) for t in recent_txs if t.type in ['expense'])

        # Monthly averages
        monthly_income_avg = round((total_income_60d / 2.0) if total_income_60d > 0 else 0.0, 2)
        monthly_expense_avg = round((total_expense_60d / 2.0) if total_expense_60d > 0 else 0.0, 2)

        # Detect active subscriptions
        subs = DetectedSubscription.query.filter_by(user_id=user.id, is_ignored=False).all()
        upcoming_commitments = round(sum(float(s.estimated_monthly_cost or s.amount or 0.0) for s in subs), 2)

        # Baseline projection: Actual + Expected Income - Expected Expenses - Upcoming Commitments
        # If user has no tx history, fallback to gentle estimate
        expected_income = monthly_income_avg if monthly_income_avg > 0 else (15000.0 if actual_total_balance > 5000 else 0.0)
        expected_expenses = max(0.0, monthly_expense_avg - upcoming_commitments) if monthly_expense_avg > upcoming_commitments else monthly_expense_avg

        projected_balance = round(max(0.0, actual_total_balance + expected_income - expected_expenses - upcoming_commitments), 2)

        return {
            'actual_balance': actual_total_balance,
            'wallet_balance': wallet_bal,
            'pockets_balance': pockets_bal,
            'locked_balance': locked_bal,
            'available_liquid_balance': round(actual_total_balance - locked_bal, 2),
            'expected_income': expected_income,
            'expected_expenses': expected_expenses,
            'upcoming_commitments': upcoming_commitments,
            'projected_balance': projected_balance,
            'forecast_days': days,
            'disclaimer': 'Forecast values are estimates calculated from historical transactions and recurring patterns. Not guaranteed financial advice.',
            'is_guaranteed': False
        }

    # =========================================================================
    # PART 2.4: SUBSCRIPTION DETECTOR
    # =========================================================================
    @classmethod
    def detect_subscriptions(cls, user):
        """
        Scans transaction history, groups recurring merchants, and identifies subscriptions.
        """
        txs = Transaction.query.filter_by(user_id=user.id, status='completed')\
            .filter(Transaction.type.in_(['expense', 'debit']))\
            .order_by(Transaction.created_at.desc()).all()

        KNOWN_SUBSCRIPTION_KEYWORDS = [
            'netflix', 'spotify', 'prime', 'amazon prime', 'hotstar', 'disney',
            'youtube', 'google', 'apple', 'icloud', 'chatgpt', 'openai', 'gym',
            'swiggy one', 'zomato gold', 'broadband', 'wifi', 'jio', 'airtel'
        ]

        merchant_map = {}
        for t in txs:
            merchant = (t.merchant or t.description or 'Unknown').strip()
            clean_m = merchant.lower()
            # Match known keywords or recurring merchant names
            matched_key = None
            for kw in KNOWN_SUBSCRIPTION_KEYWORDS:
                if kw in clean_m:
                    matched_key = kw.title()
                    break
            if not matched_key:
                matched_key = merchant.title()

            if matched_key not in merchant_map:
                merchant_map[matched_key] = []
            merchant_map[matched_key].append(t)

        detected_list = []
        for merchant_name, t_list in merchant_map.items():
            # A pattern is detected if either: matches known subscription keyword, or appears >= 2 times
            is_known = any(kw in merchant_name.lower() for kw in KNOWN_SUBSCRIPTION_KEYWORDS)
            if is_known or len(t_list) >= 2:
                latest_tx = t_list[0]
                avg_amount = round(sum(float(t.amount) for t in t_list) / float(len(t_list)), 2)
                last_date = latest_tx.created_at
                next_date = last_date + timedelta(days=30)

                # Upsert into DetectedSubscription
                existing = DetectedSubscription.query.filter_by(user_id=user.id, merchant_name=merchant_name).first()
                if not existing:
                    existing = DetectedSubscription(
                        user_id=user.id,
                        merchant_name=merchant_name,
                        amount=avg_amount,
                        frequency='monthly',
                        estimated_monthly_cost=avg_amount,
                        last_payment_date=last_date,
                        next_expected_date=next_date,
                        is_confirmed=True,
                        is_ignored=False
                    )
                    db.session.add(existing)
                else:
                    existing.amount = avg_amount
                    existing.estimated_monthly_cost = avg_amount
                    existing.last_payment_date = last_date
                    existing.next_expected_date = next_date

                db.session.commit()
                detected_list.append(existing.to_dict())

        # Return all detected subscriptions for user
        all_subs = DetectedSubscription.query.filter_by(user_id=user.id).order_by(DetectedSubscription.estimated_monthly_cost.desc()).all()
        return [s.to_dict() for s in all_subs]

    @classmethod
    def update_detected_subscription(cls, user, subscription_id, is_confirmed=None, is_ignored=None):
        sub = DetectedSubscription.query.filter_by(id=subscription_id, user_id=user.id).first()
        if not sub:
            raise ValueError("Subscription not found.")
        if is_confirmed is not None:
            sub.is_confirmed = bool(is_confirmed)
            if sub.is_confirmed:
                sub.is_ignored = False
        if is_ignored is not None:
            sub.is_ignored = bool(is_ignored)
            if sub.is_ignored:
                sub.is_confirmed = False

        sub.updated_at = datetime.utcnow()
        db.session.commit()
        return sub.to_dict()

    # =========================================================================
    # PART 2.5: PAYMENT APPROVAL MODE
    # =========================================================================
    @classmethod
    def update_approval_settings(cls, user, enabled, threshold):
        user.require_payment_approval = bool(enabled)
        user.payment_approval_threshold = round(max(1.0, float(threshold)), 2)
        db.session.commit()
        return {
            'require_payment_approval': bool(user.require_payment_approval),
            'payment_approval_threshold': float(user.payment_approval_threshold)
        }

    @classmethod
    def get_approval_settings(cls, user):
        return {
            'require_payment_approval': bool(getattr(user, 'require_payment_approval', False)),
            'payment_approval_threshold': float(getattr(user, 'payment_approval_threshold', 5000.0) or 5000.0)
        }

    # =========================================================================
    # PART 2.6: POCKET SIMULATOR
    # =========================================================================
    @classmethod
    def calculate_simulation(cls, income, fixed_expenses=None):
        """
        Purely hypothetical simulation tool.
        Does NOT modify actual balances.
        """
        inc = round(max(0.0, float(income or 0.0)), 2)
        exp_dict = fixed_expenses or {}

        rent = round(float(exp_dict.get('rent', 0.0)), 2)
        food = round(float(exp_dict.get('food', 0.0)), 2)
        travel = round(float(exp_dict.get('travel', 0.0)), 2)
        other = round(float(exp_dict.get('other', 0.0)), 2)

        total_fixed = round(rent + food + travel + other, 2)
        net_surplus = round(max(0.0, inc - total_fixed), 2)

        # Proposed 50/30/20 style allocation on remaining surplus
        savings = round(net_surplus * 0.40, 2)
        emergency = round(net_surplus * 0.25, 2)
        entertainment = round(net_surplus * 0.20, 2)
        buffer_remaining = round(max(0.0, net_surplus - (savings + emergency + entertainment)), 2)

        return {
            'is_hypothetical': True,
            'disclaimer': 'Hypothetical simulation only. Does not alter your live balances unless explicitly applied.',
            'income': inc,
            'fixed_expenses': {
                'rent': rent,
                'food': food,
                'travel': travel,
                'other': other,
                'total': total_fixed
            },
            'net_surplus': net_surplus,
            'suggested_allocation': {
                'savings': savings,
                'emergency': emergency,
                'entertainment': entertainment,
                'buffer': buffer_remaining
            }
        }

    @classmethod
    def apply_simulation(cls, user, plan):
        """
        Explicitly applies simulation targets to user pockets (sets budget_amount).
        """
        allocs = plan.get('suggested_allocation', {})
        results = []

        mapping = {
            'savings': ('Savings Pocket', '#10b981', 'piggy-bank'),
            'emergency': ('Emergency Pocket', '#f59e0b', 'shield'),
            'entertainment': ('Entertainment Pocket', '#ec4899', 'film'),
            'buffer': ('General Buffer', '#6366f1', 'wallet')
        }

        for key, amt in allocs.items():
            if amt <= 0:
                continue
            name, col, ic = mapping.get(key, (key.title(), '#6366f1', 'wallet'))
            # Find or create pocket
            pocket = Pocket.query.filter_by(user_id=user.id, name=name, archived=False).first()
            if not pocket:
                pocket = Pocket(
                    user_id=user.id,
                    name=name,
                    color=col,
                    icon=ic,
                    budget_amount=round(float(amt), 2),
                    monthly_limit=round(float(amt), 2)
                )
                db.session.add(pocket)
            else:
                pocket.budget_amount = round(float(amt), 2)
                pocket.monthly_limit = round(float(amt), 2)

            results.append({'pocket': name, 'budget_target': amt})

        db.session.commit()
        return {'success': True, 'applied_targets': results}

    # =========================================================================
    # PART 2.7: PAYMENT ROUTING
    # =========================================================================
    @classmethod
    def preview_payment_routing(cls, user, amount, preferred_pocket_ids=None):
        """
        Previews payment source distribution across eligible, unlocked pockets.
        Respects locked pockets and insufficient balances.
        """
        amt = round(max(0.01, float(amount)), 2)
        all_pockets = Pocket.query.filter_by(user_id=user.id, archived=False).all()

        # Eligible pockets: unlocked, positive balance
        unlocked = [p for p in all_pockets if not p.is_currently_locked() and float(p.current_balance or 0.0) > 0]

        # Order by preferred pockets first
        pref_ids = [int(x) for x in (preferred_pocket_ids or [])]
        preferred = [p for p in unlocked if p.id in pref_ids]
        others = [p for p in unlocked if p.id not in pref_ids]
        ordered_pockets = preferred + others

        routes = []
        remaining = amt

        for p in ordered_pockets:
            if remaining <= 0:
                break
            p_bal = float(p.current_balance or 0.0)
            take = min(p_bal, remaining)
            routes.append({
                'pocket_id': p.id,
                'pocket_name': p.name,
                'color': p.color,
                'available_balance': p_bal,
                'amount_to_debit': round(take, 2)
            })
            remaining = round(remaining - take, 2)

        total_routed = round(amt - remaining, 2)
        can_fulfill = (remaining <= 0)

        # Locked pockets summary for transparency
        locked_pockets = [
            {'id': p.id, 'name': p.name, 'balance': float(p.current_balance or 0.0), 'reason': p.lock_reason or 'Locked'}
            for p in all_pockets if p.is_currently_locked()
        ]

        return {
            'amount': amt,
            'can_fulfill': can_fulfill,
            'total_routed': total_routed,
            'shortage': remaining if remaining > 0 else 0.0,
            'routes': routes,
            'locked_pockets_excluded': locked_pockets
        }

    # =========================================================================
    # PART 2.8: MONEY CONCIERGE (PREMIUM FINANCIAL ASSISTANT)
    # =========================================================================
    @classmethod
    def get_concierge_analysis(cls, user, query_str):
        q = str(query_str).strip().lower()

        # 1. "Can I afford ₹X this month?"
        afford_match = re.search(r'afford\s*(?:rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', q)
        if afford_match:
            val = float(afford_match.group(1).replace(',', ''))
            forecast = cls.get_balance_forecast(user)
            avail_liquid = forecast['available_liquid_balance']
            commitments = forecast['upcoming_commitments']
            safe_buffer = round(avail_liquid - commitments, 2)
            can_afford = safe_buffer >= val

            return {
                'type': 'affordability',
                'question': query_str,
                'requested_amount': val,
                'available_liquid': avail_liquid,
                'upcoming_commitments': commitments,
                'safe_spending_capacity': safe_buffer,
                'can_afford': can_afford,
                'answer': (
                    f"✅ **Yes, you can afford ₹{val:,.2f} this month.** Your liquid balance is ₹{avail_liquid:,.2f} "
                    f"with ₹{commitments:,.2f} in upcoming commitments, leaving a safe capacity of ₹{safe_buffer:,.2f}."
                    if can_afford else
                    f"⚠️ **Careful:** An expenditure of ₹{val:,.2f} exceeds your safe liquid capacity of ₹{safe_buffer:,.2f} "
                    f"(Liquid funds: ₹{avail_liquid:,.2f}, Upcoming commitments: ₹{commitments:,.2f})."
                ),
                'disclaimer': 'Calculation based on active wallet and unlocked pocket funds.'
            }

        # 2. "Which pocket am I spending the most from?"
        if 'which pocket' in q or 'spending the most' in q:
            pockets = Pocket.query.filter_by(user_id=user.id, archived=False).order_by(Pocket.total_spent.desc()).all()
            if pockets and float(pockets[0].total_spent or 0.0) > 0:
                top = pockets[0]
                return {
                    'type': 'top_spending_pocket',
                    'question': query_str,
                    'pocket_id': top.id,
                    'pocket_name': top.name,
                    'total_spent': float(top.total_spent or 0.0),
                    'answer': f"📊 You are spending the most from your **{top.name}** Pocket, with a total expenditure of **₹{float(top.total_spent or 0.0):,.2f}**."
                }
            return {
                'type': 'top_spending_pocket',
                'answer': "You haven't recorded significant expenses from your pockets yet."
            }

        # 3. "Why did my balance decrease this month?"
        if 'balance decrease' in q or 'why did my balance drop' in q or 'why balance decreased' in q:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            top_expenses = Transaction.query.filter(
                Transaction.user_id == user.id,
                Transaction.type == 'expense',
                Transaction.created_at >= thirty_days_ago,
                Transaction.status == 'completed'
            ).order_by(Transaction.amount.desc()).limit(3).all()

            total_outflow = sum(float(t.amount) for t in top_expenses)
            items_str = ", ".join([f"{t.merchant or t.category} (₹{float(t.amount):,.2f})" for t in top_expenses])
            return {
                'type': 'balance_decrease_explanation',
                'question': query_str,
                'answer': (
                    f"📉 Over the past 30 days, your largest outflows were from: {items_str}. "
                    f"These top items contributed ₹{total_outflow:,.2f} to your total spending."
                    if top_expenses else
                    "Your balance has remained stable with no major debits in the last 30 days."
                )
            }

        # 4. "How much did I spend on subscriptions?"
        if 'subscription' in q and ('spend' in q or 'cost' in q or 'how much' in q):
            subs = DetectedSubscription.query.filter_by(user_id=user.id, is_ignored=False).all()
            total_sub = sum(float(s.estimated_monthly_cost or 0.0) for s in subs)
            sub_names = ", ".join([f"{s.merchant_name} (₹{float(s.amount):,.2f})" for s in subs])
            return {
                'type': 'subscription_spending',
                'question': query_str,
                'total_monthly_subscriptions': total_sub,
                'answer': (
                    f"💳 You are currently spending approximately **₹{total_sub:,.2f}/month** on subscriptions: {sub_names}."
                    if subs else
                    "No active recurring subscriptions detected in your recent transaction ledger."
                )
            }

        # 5. "Show my upcoming commitments"
        if 'commitment' in q or 'upcoming' in q:
            subs = DetectedSubscription.query.filter_by(user_id=user.id, is_ignored=False).all()
            total_sub = sum(float(s.estimated_monthly_cost or 0.0) for s in subs)
            return {
                'type': 'upcoming_commitments',
                'question': query_str,
                'commitments': [s.to_dict() for s in subs],
                'total_amount': total_sub,
                'answer': f"📅 You have **{len(subs)} upcoming recurring commitments** totaling **₹{total_sub:,.2f}** this month."
            }

        # 6. "How much have I saved toward my goals?"
        if 'goal' in q or 'saved' in q:
            goals = SavingsGoal.query.filter_by(user_id=user.id).all()
            total_saved = sum(float(g.current_amount or 0.0) for g in goals)
            target_sum = sum(float(g.target_amount or 0.0) for g in goals)
            return {
                'type': 'goal_savings',
                'question': query_str,
                'total_saved': total_saved,
                'target_total': target_sum,
                'answer': f"🎯 You have saved **₹{total_saved:,.2f}** across your goals (target: ₹{target_sum:,.2f})."
            }

        # Fallback to general concierge overview
        forecast = cls.get_balance_forecast(user)
        return {
            'type': 'general_financial_summary',
            'question': query_str,
            'forecast': forecast,
            'answer': (
                f"PocketPay Money Concierge Report:\n"
                f"• Total Balance: ₹{forecast['actual_balance']:,.2f} (Liquid: ₹{forecast['available_liquid_balance']:,.2f})\n"
                f"• Locked Funds: ₹{forecast['locked_balance']:,.2f}\n"
                f"• Projected 30-Day Balance: ₹{forecast['projected_balance']:,.2f}\n"
                f"• Monthly Commitments: ₹{forecast['upcoming_commitments']:,.2f}"
            )
        }
