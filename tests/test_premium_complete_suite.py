import os
import sys
import unittest
from datetime import datetime, timedelta

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set environment configuration
os.environ['FLASK_CONFIG'] = 'testing'
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.subscription import Subscription, PocketRule, PocketRuleExecution, DetectedSubscription
from app.services.premium_service import PremiumService
from app.services.ledger_service import LedgerService, FinancialInvariantError


class PremiumCompleteTestSuite(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config.update({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'WTF_CSRF_ENABLED': False,
            'SECRET_KEY': 'test-secret-key-premium'
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def create_test_user(self, email="test@pocketpay.app", is_premium=False, wallet_balance=25000.0, phone=None):
        if not phone:
            import random
            phone = f"98{random.randint(10000000, 99999999)}"
        user = User(
            email=email,
            full_name="Alex Mercer",
            phone=phone,
            is_premium=is_premium,
            wallet_balance=wallet_balance,
            security_setup_completed=True
        )
        user.set_password("SecurePass@123")
        user.set_transaction_pin("1234")
        db.session.add(user)
        db.session.commit()
        return user

    def login_user(self, user):
        return self.client.post('/auth/login', json={
            'email': user.email,
            'password': 'SecurePass@123'
        })

    # =========================================================================
    # PART 4: ACCESS CONTROL (Standard User 403 Forbidden on Premium APIs)
    # =========================================================================
    def test_01_standard_user_blocked_from_premium_endpoints(self):
        """Verify Standard user cannot access Premium APIs directly (403 FORBIDDEN)."""
        standard_user = self.create_test_user("standard@pocketpay.app", is_premium=False)
        self.login_user(standard_user)

        endpoints = [
            ('/api/premium/rules', 'GET'),
            ('/api/premium/forecast', 'GET'),
            ('/api/premium/subscriptions/detected', 'GET'),
            ('/api/premium/approval-mode/settings', 'GET'),
            ('/api/premium/simulator/calculate', 'POST'),
            ('/api/premium/routing/preview', 'POST'),
            ('/api/premium/concierge/ask', 'POST'),
            ('/api/premium/pockets/1/lock', 'POST')
        ]

        for url, method in endpoints:
            if method == 'GET':
                res = self.client.get(url)
            else:
                res = self.client.post(url, json={})
            self.assertEqual(res.status_code, 403, f"Endpoint {url} should return 403 for standard user, got {res.status_code}")
            data = res.get_json()
            self.assertEqual(data.get('code'), 'PREMIUM_REQUIRED')

    # =========================================================================
    # PART 1: ORDER CREATION AND VERIFICATION FLOW
    # =========================================================================
    def test_02_order_creation_and_verification_flow(self):
        """Test order creation, payment verification, idempotency and cancellation."""
        user = self.create_test_user("buyer@pocketpay.app", is_premium=False)
        self.login_user(user)

        # 1. Test order creation on /api/premium/create-checkout-order
        res = self.client.post('/api/premium/create-checkout-order', json={'plan': 'monthly'})
        self.assertEqual(res.status_code, 201)
        data = res.get_json().get('data', {})
        self.assertIsNotNone(data.get('order_id'))
        self.assertEqual(data.get('amount'), 99.0)
        self.assertEqual(data.get('amount_paise'), 9900)
        self.assertEqual(data.get('currency'), 'INR')
        order_id = data['order_id']

        # 2. Test alias endpoint /premium/create-checkout-order with second user
        user2 = self.create_test_user("buyer2@pocketpay.app", is_premium=False)
        self.login_user(user2)
        res_alias = self.client.post('/premium/create-checkout-order', json={'plan_id': 'yearly'})
        self.assertEqual(res_alias.status_code, 201)
        alias_data = res_alias.get_json().get('data', {})
        self.assertEqual(alias_data.get('amount'), 799.0)

        # Switch back to user 1
        self.login_user(user)

        # 3. Test verification with invalid signature
        fail_res = self.client.post('/api/premium/verify-payment', json={
            'order_id': order_id,
            'payment_id': 'pay_invalid_123',
            'signature': 'bad_sig'
        })
        self.assertEqual(fail_res.status_code, 400)

        # 4. Test verification with valid sandbox signature
        sandbox_sig = f"sig_sandbox_{order_id}"
        success_res = self.client.post('/api/premium/verify-payment', json={
            'order_id': order_id,
            'payment_id': f"pay_test_{order_id}",
            'signature': sandbox_sig
        })
        self.assertEqual(success_res.status_code, 200)
        sub_info = success_res.get_json().get('data', {}).get('subscription', {})
        self.assertEqual(sub_info.get('status'), 'ACTIVE')

        # Verify user is now premium in DB
        db.session.refresh(user)
        self.assertTrue(user.is_premium)
        self.assertTrue(user.is_premium_active)

        # 5. Duplicate payment verification attempt
        dup_res = self.client.post('/api/premium/verify-payment', json={
            'order_id': order_id,
            'payment_id': f"pay_test_{order_id}",
            'signature': sandbox_sig
        })
        self.assertEqual(dup_res.status_code, 200)
        self.assertTrue(dup_res.get_json().get('data', {}).get('already_active'))

        # 6. Cancel subscription
        cancel_res = self.client.post('/api/premium/cancel', json={})
        self.assertEqual(cancel_res.status_code, 200)
        sub_cancelled = cancel_res.get_json().get('data', {}).get('subscription', {})
        self.assertEqual(sub_cancelled.get('status'), 'CANCELLED')
        # Retains active status until end of billing cycle
        self.assertTrue(user.is_premium_active)

    # =========================================================================
    # PART 2.1: POCKET RULES ENGINE
    # =========================================================================
    def test_03_pocket_rules_crud_and_idempotent_execution(self):
        """Test Rule CRUD, trigger matching, and guarantee no duplicate execution for same tx."""
        user = self.create_test_user("rules@pocketpay.app", is_premium=True, wallet_balance=10000.0)
        self.login_user(user)

        emergency_pocket = Pocket(user_id=user.id, name="Emergency Pocket", current_balance=500.0)
        db.session.add(emergency_pocket)
        db.session.commit()

        # 1. Create rule: IF income received -> allocate 30% to Emergency Pocket
        create_res = self.client.post('/api/premium/rules', json={
            'name': '30% Income to Emergency',
            'trigger_type': 'INCOME_RECEIVED',
            'action_type': 'ALLOCATE_PERCENT',
            'action_value': 30.0,
            'target_pocket_id': emergency_pocket.id
        })
        self.assertEqual(create_res.status_code, 201)
        rule_data = create_res.get_json().get('data', {}).get('rule', {})
        rule_id = rule_data['id']
        self.assertEqual(rule_data['action_value'], 30.0)

        # 2. Update rule
        update_res = self.client.put(f'/api/premium/rules/{rule_id}', json={'action_value': 25.0})
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(update_res.get_json().get('data', {}).get('rule', {})['action_value'], 25.0)

        # 3. Simulate incoming income transaction (e.g. salary of ₹4,000)
        tx = Transaction(
            transaction_id=Transaction.generate_transaction_id(),
            user_id=user.id,
            type='income',
            amount=4000.0,
            status='completed',
            completed_at=datetime.utcnow()
        )
        db.session.add(tx)
        user.wallet_balance += 4000.0
        db.session.commit()

        # 4. Trigger rules evaluation
        executed = PremiumService.evaluate_rules_on_credit(user, tx)
        self.assertEqual(len(executed), 1)
        # 25% of 4,000 = ₹1,000
        self.assertEqual(executed[0]['executed_amount'], 1000.0)

        # Verify pocket balance increased by ₹1,000
        db.session.refresh(emergency_pocket)
        self.assertEqual(emergency_pocket.current_balance, 1500.0)

        # 5. Test idempotency: Calling again with SAME transaction ID must NOT execute again
        executed_repeat = PremiumService.evaluate_rules_on_credit(user, tx)
        self.assertEqual(len(executed_repeat), 0)
        db.session.refresh(emergency_pocket)
        self.assertEqual(emergency_pocket.current_balance, 1500.0)

        # 6. Verify rule history
        hist_res = self.client.get(f'/api/premium/rules/history?rule_id={rule_id}')
        self.assertEqual(hist_res.status_code, 200)
        history = hist_res.get_json().get('data', {}).get('history', [])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['status'], 'SUCCESS')

    # =========================================================================
    # PART 2.2: POCKET LOCK
    # =========================================================================
    def test_04_pocket_lock_prevents_spending(self):
        """Verify locked pocket money is visible in balance but cannot be spent or withdrawn."""
        user = self.create_test_user("lock@pocketpay.app", is_premium=True, wallet_balance=5000.0)
        self.login_user(user)

        vacation_pocket = Pocket(
            user_id=user.id,
            name="Vacation Pocket",
            current_balance=8000.0,
            budget_amount=10000.0
        )
        db.session.add(vacation_pocket)
        db.session.commit()

        # 1. Lock pocket until goal of ₹10,000 reached
        lock_res = self.client.post(f'/api/premium/pockets/{vacation_pocket.id}/lock', json={
            'reason': 'Trip to Japan',
            'goal_amount': 10000.0,
            'locked_until_date': (datetime.utcnow() + timedelta(days=30)).isoformat()
        })
        self.assertEqual(lock_res.status_code, 200)
        p_dict = lock_res.get_json().get('data', {}).get('pocket', {})
        self.assertTrue(p_dict['is_currently_locked'])

        # 2. Verify LedgerService withdraw is blocked
        with self.assertRaises(FinancialInvariantError):
            LedgerService.withdraw_from_pocket(user, vacation_pocket, 1000.0)

        # 3. Verify Payment endpoint blocks spending from locked pocket
        pay_res = self.client.post('/api/transactions/pay-pocket', json={
            'pocket_id': vacation_pocket.id,
            'amount': 500.0,
            'pin': '1234'
        })
        self.assertEqual(pay_res.status_code, 400)
        self.assertEqual(pay_res.get_json().get('code'), 'POCKET_LOCKED')

        # 4. Unlock pocket
        unlock_res = self.client.post(f'/api/premium/pockets/{vacation_pocket.id}/unlock', json={})
        self.assertEqual(unlock_res.status_code, 200)
        self.assertFalse(unlock_res.get_json().get('data', {}).get('pocket', {})['is_currently_locked'])

        # 5. Withdrawal now succeeds
        res_with = LedgerService.withdraw_from_pocket(user, vacation_pocket, 1000.0)
        self.assertTrue(res_with['success'])
        db.session.refresh(vacation_pocket)
        self.assertEqual(vacation_pocket.current_balance, 7000.0)

    # =========================================================================
    # PART 2.5: PAYMENT APPROVAL MODE
    # =========================================================================
    def test_05_payment_approval_mode_backend_enforcement(self):
        """Verify payments exceeding threshold require confirmation at authorization layer."""
        user = self.create_test_user("approval@pocketpay.app", is_premium=True, wallet_balance=20000.0)
        self.login_user(user)

        # 1. Configure Approval Mode: Threshold = ₹5,000
        cfg_res = self.client.post('/api/premium/approval-mode/settings', json={
            'require_payment_approval': True,
            'payment_approval_threshold': 5000.0
        })
        self.assertEqual(cfg_res.status_code, 200)
        self.assertTrue(cfg_res.get_json().get('data', {}).get('require_payment_approval'))

        # 2. Attempt payment of ₹8,500 without confirmation -> MUST be blocked
        pay_res = self.client.post('/api/transactions/pay-balance', json={
            'amount': 8500.0,
            'recipient': 'vendor@merchant.com',
            'pin': '1234'
        })
        self.assertEqual(pay_res.status_code, 400)
        err_data = pay_res.get_json()
        self.assertEqual(err_data.get('code'), 'PAYMENT_APPROVAL_REQUIRED')
        self.assertEqual(err_data.get('amount'), 8500.0)
        self.assertEqual(err_data.get('threshold'), 5000.0)

        # Balance remains untouched
        db.session.refresh(user)
        self.assertEqual(user.wallet_balance, 20000.0)

        # 3. Supply approval_confirmed: True -> MUST succeed
        approved_pay_res = self.client.post('/api/transactions/pay-balance', json={
            'amount': 8500.0,
            'recipient': 'vendor@merchant.com',
            'pin': '1234',
            'approval_confirmed': True
        })
        self.assertEqual(approved_pay_res.status_code, 201)
        db.session.refresh(user)
        self.assertEqual(user.wallet_balance, 11500.0)

    # =========================================================================
    # PART 2.3, 2.4, 2.6, 2.7, 2.8: FORECAST, DETECTOR, SIMULATOR, ROUTING, CONCIERGE
    # =========================================================================
    def test_06_future_forecast_and_subscription_detector(self):
        """Forecast calculation and subscription detector."""
        user = self.create_test_user("forecast@pocketpay.app", is_premium=True, wallet_balance=35000.0)
        self.login_user(user)

        now = datetime.utcnow()
        t1 = Transaction(transaction_id=Transaction.generate_transaction_id(), user_id=user.id, type='expense', merchant='Netflix', amount=649.0, status='completed', created_at=now - timedelta(days=28))
        t2 = Transaction(transaction_id=Transaction.generate_transaction_id(), user_id=user.id, type='expense', merchant='Netflix', amount=649.0, status='completed', created_at=now)
        t3 = Transaction(transaction_id=Transaction.generate_transaction_id(), user_id=user.id, type='expense', merchant='Spotify', amount=119.0, status='completed', created_at=now - timedelta(days=25))
        t4 = Transaction(transaction_id=Transaction.generate_transaction_id(), user_id=user.id, type='expense', merchant='Spotify', amount=119.0, status='completed', created_at=now)
        db.session.add_all([t1, t2, t3, t4])
        db.session.commit()

        # Subscription detector
        det_res = self.client.get('/api/premium/subscriptions/detected')
        self.assertEqual(det_res.status_code, 200)
        subs = det_res.get_json().get('data', {}).get('subscriptions', [])
        self.assertGreaterEqual(len(subs), 2)
        services = [s['service'] for s in subs]
        self.assertIn('Netflix', services)
        self.assertIn('Spotify', services)

        # Forecast
        fc_res = self.client.get('/api/premium/forecast?days=30')
        self.assertEqual(fc_res.status_code, 200)
        fc = fc_res.get_json().get('data', {})
        self.assertEqual(fc['actual_balance'], 35000.0)
        self.assertGreaterEqual(fc['upcoming_commitments'], 768.0)
        self.assertFalse(fc['is_guaranteed'])

    def test_07_simulator_and_payment_routing(self):
        """Simulator without modifying balance, and multi-pocket routing."""
        user = self.create_test_user("sim@pocketpay.app", is_premium=True, wallet_balance=10000.0)
        self.login_user(user)

        p1 = Pocket(user_id=user.id, name="Travel Pocket", current_balance=4000.0)
        p2 = Pocket(user_id=user.id, name="General Pocket", current_balance=5000.0)
        p3 = Pocket(user_id=user.id, name="Locked Pocket", current_balance=3000.0, is_locked=True)
        db.session.add_all([p1, p2, p3])
        db.session.commit()

        # 1. Simulator
        sim_res = self.client.post('/api/premium/simulator/calculate', json={
            'income': 40000.0,
            'fixed_expenses': {'rent': 12000.0, 'food': 6000.0, 'travel': 4000.0}
        })
        self.assertEqual(sim_res.status_code, 200)
        sim_data = sim_res.get_json().get('data', {})
        self.assertTrue(sim_data['is_hypothetical'])
        self.assertEqual(sim_data['net_surplus'], 18000.0)
        db.session.refresh(user)
        self.assertEqual(user.wallet_balance, 10000.0)

        # 2. Routing preview
        route_res = self.client.post('/api/premium/routing/preview', json={
            'amount': 7000.0,
            'preferred_pocket_ids': [p1.id, p2.id]
        })
        self.assertEqual(route_res.status_code, 200)
        r_data = route_res.get_json().get('data', {})
        self.assertTrue(r_data['can_fulfill'])
        self.assertEqual(len(r_data['routes']), 2)
        self.assertEqual(r_data['routes'][0]['pocket_id'], p1.id)
        self.assertEqual(r_data['routes'][0]['amount_to_debit'], 4000.0)
        self.assertEqual(r_data['routes'][1]['pocket_id'], p2.id)
        self.assertEqual(r_data['routes'][1]['amount_to_debit'], 3000.0)
        locked_excluded = r_data.get('locked_pockets_excluded', [])
        self.assertTrue(any(lp['id'] == p3.id for lp in locked_excluded))

    def test_08_money_concierge_analysis(self):
        """Premium Concierge data-backed question answering."""
        user = self.create_test_user("concierge@pocketpay.app", is_premium=True, wallet_balance=25000.0)
        self.login_user(user)

        q_res = self.client.post('/api/premium/concierge/ask', json={'question': 'Can I afford ₹8,000 this month?'})
        self.assertEqual(q_res.status_code, 200)
        q_data = q_res.get_json().get('data', {})
        self.assertEqual(q_data.get('type'), 'affordability')
        self.assertTrue(q_data.get('can_afford'))
        self.assertIn('afford ₹8,000', q_data.get('answer', ''))


if __name__ == '__main__':
    unittest.main()
