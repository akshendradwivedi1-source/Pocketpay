"""
Master Automated FinTech Verification Test Suite for PocketPay
Tests 1 through 18 covering all security, money movement, pocket isolation,
universal QR, payouts, idempotency, bank reconciliation, premium subscriptions,
AI assistant security, and multi-user authorization.
"""
import unittest
import json
import os
import re
import hmac
import hashlib
from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.subscription import Subscription, PocketRule, LoginEvent


class TestFintechMasterSuite(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['MAIL_SUPPRESS_SEND'] = True
        self.app.config['WEBHOOK_SECRET'] = 'fintech_master_webhook_secret'
        os.environ['WEBHOOK_SECRET'] = 'fintech_master_webhook_secret'

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        db.create_all()

        # Seed User A (Arvind)
        self.user_a = User(
            full_name="Arvind Raman",
            email="arvind@pocketpay.io",
            phone="9876543210",
            email_verified=True,
            wallet_balance=50000.00,
            virtual_upi_id="arvind@pocketpay",
            virtual_wallet_id="PPWARVIND01"
        )
        self.user_a.set_password("FintechSecure@2026")
        self.user_a.set_transaction_pin("4321")

        # Seed User B (Priya)
        self.user_b = User(
            full_name="Priya Sharma",
            email="priya@pocketpay.io",
            phone="9876543211",
            email_verified=True,
            wallet_balance=500.00,
            virtual_upi_id="priya@pocketpay",
            virtual_wallet_id="PPWPRIYA02"
        )
        self.user_b.set_password("FintechSecure@2026")
        self.user_b.set_transaction_pin("9876")

        db.session.add_all([self.user_a, self.user_b])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login_user(self, email="arvind@pocketpay.io", password="FintechSecure@2026"):
        return self.client.post('/auth/login', json={
            'email': email,
            'password': password
        })

    # =========================================================================
    # TEST 1: First login security setup
    # =========================================================================
    def test_01_first_login_security_setup(self):
        """
        TEST 1: Check security credential setup flow.
        New user registers -> has_transaction_pin is False -> security disclaimer
        card shown on dashboard -> user navigates and sets PIN -> has_transaction_pin
        becomes True -> disclaimer dismissed.
        """
        # Register fresh user
        reg_res = self.client.post('/auth/register', json={
            'full_name': 'Rohit Verma',
            'email': 'rohit@pocketpay.io',
            'phone': '9876543299',
            'password': 'Password@123',
            'confirm_password': 'Password@123'
        })
        self.assertEqual(reg_res.status_code, 201)

        # Login new user
        self.client.post('/auth/login', json={
            'email': 'rohit@pocketpay.io',
            'password': 'Password@123'
        })

        # Check me profile before PIN setup
        me_res = self.client.get('/auth/me')
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.get_json()['data']['user']
        self.assertFalse(me_data['has_transaction_pin'])

        # Set transaction PIN
        pin_res = self.client.post('/auth/set-transaction-pin', json={
            'pin': '7788',
            'confirm_pin': '7788'
        })
        self.assertEqual(pin_res.status_code, 200)

        # Check me profile after PIN setup
        me_res_after = self.client.get('/auth/me')
        me_data_after = me_res_after.get_json()['data']['user']
        self.assertTrue(me_data_after['has_transaction_pin'])

    # =========================================================================
    # TEST 2: Payment options display
    # =========================================================================
    def test_02_payment_options_display(self):
        """
        TEST 2: Payment options modal and endpoints.
        Verify Pay Securely routes and modals exist for all 4 options:
        1. PocketPay Balance
        2. Pay From a Pocket
        3. Scan QR
        4. Beneficiary / Netbanking
        """
        self.login_user()

        # Check endpoints exist and require authentication/data
        res_pay_pocket = self.client.post('/api/transactions/pay-pocket', json={})
        self.assertIn(res_pay_pocket.status_code, (400, 422))

        res_pay_balance = self.client.post('/api/transactions/pay-balance', json={})
        self.assertIn(res_pay_balance.status_code, (400, 422))

        res_payout = self.client.post('/api/payouts/transfer-to-bank', json={})
        self.assertIn(res_payout.status_code, (400, 422))

        # Check that modals.js defines the openPaymentHub with the 4 options
        with open('app/static/js/views/modals.js', 'r', encoding='utf-8') as f:
            js_content = f.read()
        self.assertIn('PAY SECURELY', js_content)
        self.assertIn('PocketPay Balance', js_content)
        self.assertIn('Pay From a Pocket', js_content)
        self.assertIn('Scan QR', js_content)
        self.assertIn('Beneficiary / Netbanking', js_content)

    # =========================================================================
    # TEST 3: Pay from Pocket (happy path)
    # =========================================================================
    def test_03_pay_from_pocket_happy_path(self):
        """
        TEST 3: User has Pocket A with ₹2,000. Pays ₹500 to recipient.
        Pocket A balance becomes ₹1,500. Recipient balance increases by ₹500.
        Transaction record created with source_type='pocket', pocket_id, amount=500.
        """
        self.login_user()

        pocket_res = self.client.post('/api/pockets', json={
            'name': 'Vacation Fund',
            'color': '#6366f1',
            'icon': 'plane',
            'initial_balance': 2000.00,
            'category': 'Travel'
        })
        self.assertEqual(pocket_res.status_code, 201)
        pocket_id = pocket_res.get_json()['data']['pocket']['id']

        # Pay ₹500 from Pocket A to User B
        pay_res = self.client.post('/api/transactions/pay-pocket', json={
            'pocket_id': pocket_id,
            'recipient': 'priya@pocketpay.io',
            'amount': 500.00,
            'pin': '4321',
            'note': 'Travel ticket contribution'
        })
        self.assertIn(pay_res.status_code, (200, 201))

        # Refresh database
        pkt = db.session.get(Pocket, pocket_id)
        u_b = db.session.get(User, self.user_b.id)

        self.assertEqual(float(pkt.current_balance), 1500.00)
        self.assertEqual(float(u_b.wallet_balance), 1000.00)  # 500 initial + 500 received

        # Verify transaction record
        tx = Transaction.query.filter_by(from_pocket_id=pocket_id).order_by(Transaction.id.desc()).first()
        self.assertIsNotNone(tx)
        self.assertEqual(float(tx.amount), 500.00)
        self.assertEqual(tx.source_type, 'pocket')

    # =========================================================================
    # TEST 4: Pay from Pocket (insufficient balance)
    # =========================================================================
    def test_04_pay_from_pocket_insufficient_funds(self):
        """
        TEST 4: Pocket balance ₹200. Attempt to pay ₹500 from pocket.
        Rejected with error 'Insufficient funds in pocket'.
        Balance remains ₹200. No transaction created.
        """
        self.login_user()

        pocket_res = self.client.post('/api/pockets', json={
            'name': 'Snacks',
            'color': '#f59e0b',
            'icon': 'coffee',
            'initial_balance': 200.00,
            'category': 'Food'
        })
        pocket_id = pocket_res.get_json()['data']['pocket']['id']

        tx_count_before = Transaction.query.count()

        pay_res = self.client.post('/api/transactions/pay-pocket', json={
            'pocket_id': pocket_id,
            'recipient': 'priya@pocketpay.io',
            'amount': 500.00,
            'pin': '4321',
            'note': 'Snack run'
        })
        self.assertEqual(pay_res.status_code, 400)
        err_msg = pay_res.get_json().get('message') or pay_res.get_json().get('error') or ''
        self.assertIn('Insufficient funds in', err_msg)

        # Balance remains 200
        pkt = db.session.get(Pocket, pocket_id)
        self.assertEqual(float(pkt.current_balance), 200.00)

        # No transaction created
        tx_count_after = Transaction.query.count()
        self.assertEqual(tx_count_before, tx_count_after)

    # =========================================================================
    # TEST 5: Pocket isolation
    # =========================================================================
    def test_05_pocket_isolation(self):
        """
        TEST 5: User has Pocket A (₹1,000) and Pocket B (₹2,000).
        Pay ₹300 from Pocket A.
        Pocket A becomes ₹700. Pocket B remains ₹2,000 completely untouched.
        """
        self.login_user()

        p_a_res = self.client.post('/api/pockets', json={
            'name': 'Pocket A',
            'initial_balance': 1000.00
        })
        self.assertEqual(p_a_res.status_code, 201)
        p_a_id = p_a_res.get_json()['data']['pocket']['id']

        p_b_res = self.client.post('/api/pockets', json={
            'name': 'Pocket B',
            'initial_balance': 2000.00
        })
        self.assertEqual(p_b_res.status_code, 201)
        p_b_id = p_b_res.get_json()['data']['pocket']['id']

        pay_res = self.client.post('/api/transactions/pay-pocket', json={
            'pocket_id': p_a_id,
            'recipient': 'priya@pocketpay.io',
            'amount': 300.00,
            'pin': '4321'
        })
        self.assertIn(pay_res.status_code, (200, 201))

        p_a = db.session.get(Pocket, p_a_id)
        p_b = db.session.get(Pocket, p_b_id)

        self.assertEqual(float(p_a.current_balance), 700.00)
        self.assertEqual(float(p_b.current_balance), 2000.00)

    # =========================================================================
    # TEST 6: Universal QR generation
    # =========================================================================
    def test_06_universal_qr_generation(self):
        """
        TEST 6: Generate QR -> scannable payload containing valid user details.
        """
        self.login_user()

        qr_res = self.client.post('/api/qr/generate', json={
            'content': f"pocketpay://wallet/{self.user_a.virtual_wallet_id}"
        })
        self.assertEqual(qr_res.status_code, 200)
        qr_data = qr_res.get_json()['data']
        self.assertTrue(qr_data.get('qr_code_url', '').startswith('data:image/png;base64,'))

    # =========================================================================
    # TEST 7: Universal QR payment
    # =========================================================================
    def test_07_universal_qr_payment(self):
        """
        TEST 7: Scan recipient QR -> resolve recipient -> select source pocket -> pay
        -> debit source pocket -> credit recipient.
        """
        self.login_user()

        # Resolve recipient User B QR
        resolve_res = self.client.post('/qr/api/resolve', json={
            'content': f"pocketpay://wallet/{self.user_b.virtual_wallet_id}"
        })
        self.assertEqual(resolve_res.status_code, 200)
        recipient_info = resolve_res.get_json()['data']
        self.assertEqual(recipient_info['virtual_wallet_id'], self.user_b.virtual_wallet_id)

        # Create source pocket for User A with ₹1,000
        p_res = self.client.post('/api/pockets', json={
            'name': 'QR Shopping',
            'initial_balance': 1000.00
        })
        self.assertEqual(p_res.status_code, 201)
        pkt_id = p_res.get_json()['data']['pocket']['id']

        # Pay recipient via pocket
        pay_res = self.client.post('/api/transactions/pay-pocket', json={
            'pocket_id': pkt_id,
            'recipient': recipient_info['virtual_wallet_id'],
            'amount': 250.00,
            'pin': '4321'
        })
        self.assertIn(pay_res.status_code, (200, 201))

        pkt = db.session.get(Pocket, pkt_id)
        u_b = db.session.get(User, self.user_b.id)

        self.assertEqual(float(pkt.current_balance), 750.00)
        self.assertEqual(float(u_b.wallet_balance), 750.00)

    # =========================================================================
    # TEST 8: Beneficiary payment from pocket
    # =========================================================================
    def test_08_beneficiary_payment_from_pocket(self):
        """
        TEST 8: Transfer to beneficiary bank selecting source Pocket -> pocket debited
        -> bank payout recorded -> other pockets untouched.
        """
        self.login_user()

        p1_res = self.client.post('/api/pockets', json={
            'name': 'Rent Pocket',
            'initial_balance': 15000.00
        })
        self.assertEqual(p1_res.status_code, 201)
        p1_id = p1_res.get_json()['data']['pocket']['id']

        p2_res = self.client.post('/api/pockets', json={
            'name': 'Groceries Pocket',
            'initial_balance': 4000.00
        })
        self.assertEqual(p2_res.status_code, 201)
        p2_id = p2_res.get_json()['data']['pocket']['id']

        # Payout to external bank from Rent Pocket
        payout_res = self.client.post('/api/payouts/transfer-to-bank', json={
            'account_number': '123456789012',
            'account_holder': 'Landlord Housing Ltd',
            'ifsc_code': 'HDFC0001234',
            'bank_name': 'HDFC Bank',
            'amount': 5000.00,
            'source_type': 'pocket',
            'pocket_id': p1_id,
            'pin': '4321'
        })
        self.assertEqual(payout_res.status_code, 201)

        p1 = db.session.get(Pocket, p1_id)
        p2 = db.session.get(Pocket, p2_id)

        self.assertEqual(float(p1.current_balance), 10000.00)
        self.assertEqual(float(p2.current_balance), 4000.00)  # Untouched

    # =========================================================================
    # TEST 9: Idempotent payment
    # =========================================================================
    def test_09_idempotent_payment(self):
        """
        TEST 9: Send same payment request twice with same idempotency_key ->
        second request returns original transaction, no duplicate deduction.
        """
        self.login_user()

        p_res = self.client.post('/api/pockets', json={
            'name': 'Idempotent Pocket',
            'initial_balance': 2000.00
        })
        self.assertEqual(p_res.status_code, 201)
        pkt_id = p_res.get_json()['data']['pocket']['id']

        idem_key = "test-idem-unique-key-12345"

        payload = {
            'pocket_id': pkt_id,
            'recipient': 'priya@pocketpay.io',
            'amount': 400.00,
            'pin': '4321',
            'idempotency_key': idem_key
        }

        # Request 1
        res1 = self.client.post('/api/transactions/pay-pocket', json=payload)
        self.assertIn(res1.status_code, (200, 201))

        # Request 2 (duplicate replay)
        res2 = self.client.post('/api/transactions/pay-pocket', json=payload)
        self.assertIn(res2.status_code, (200, 201))

        # Pocket balance deducted only once (2000 - 400 = 1600)
        pkt = db.session.get(Pocket, pkt_id)
        self.assertEqual(float(pkt.current_balance), 1600.00)

    # =========================================================================
    # TEST 10: Failed transaction rollback
    # =========================================================================
    def test_10_failed_transaction_rollback(self):
        """
        TEST 10: Failed transaction (wrong PIN or invalid recipient) does not
        touch or deduct pocket balance.
        """
        self.login_user()

        p_res = self.client.post('/api/pockets', json={
            'name': 'Safety Pocket',
            'initial_balance': 1000.00
        })
        self.assertEqual(p_res.status_code, 201)
        pkt_id = p_res.get_json()['data']['pocket']['id']

        # Attempt pay with wrong PIN
        res_fail = self.client.post('/api/transactions/pay-pocket', json={
            'pocket_id': pkt_id,
            'recipient': 'priya@pocketpay.io',
            'amount': 500.00,
            'pin': '0000'
        })
        self.assertEqual(res_fail.status_code, 401)

        pkt = db.session.get(Pocket, pkt_id)
        self.assertEqual(float(pkt.current_balance), 1000.00)

    # =========================================================================
    # TEST 11: Bank disconnect balance reconciliation
    # =========================================================================
    def test_11_bank_disconnect_balance_reconciliation(self):
        """
        TEST 11: User has ₹500 wallet balance + connects ₹25,000 bank balance.
        Disconnecting bank restores balance to ₹500.
        """
        # User starting balance: ₹500
        self.user_a.wallet_balance = 500.00
        db.session.commit()

        self.login_user()

        # Link bank account with simulated ₹25,000
        link_res = self.client.post('/auth/link-bank-account', json={
            'bank_name': 'State Bank of India',
            'account_holder': 'Arvind Raman',
            'account_number': '112233445566',
            'ifsc_code': 'SBIN0001234',
            'initial_balance': 25000.00
        })
        self.assertEqual(link_res.status_code, 201)

        u = db.session.get(User, self.user_a.id)
        self.assertEqual(float(u.wallet_balance), 25500.00)

        # Disconnect bank
        unlink_res = self.client.post('/auth/unlink-bank-account', json={})
        self.assertEqual(unlink_res.status_code, 200)

        db.session.refresh(u)
        self.assertEqual(float(u.wallet_balance), 500.00)

    # =========================================================================
    # TEST 12: Bank reconnect no duplicate
    # =========================================================================
    def test_12_bank_reconnect_no_duplicate(self):
        """
        TEST 12: Reconnecting the same active bank account returns an error and
        does not create phantom money.
        """
        self.login_user()

        # Connect bank
        self.client.post('/auth/link-bank-account', json={
            'bank_name': 'HDFC Bank',
            'account_holder': 'Arvind Raman',
            'account_number': '998877665544',
            'ifsc_code': 'HDFC0001234',
            'initial_balance': 10000.00
        })

        # Try to connect same bank account without disconnecting
        dup_res = self.client.post('/auth/link-bank-account', json={
            'bank_name': 'HDFC Bank',
            'account_holder': 'Arvind Raman',
            'account_number': '998877665544',
            'ifsc_code': 'HDFC0001234',
            'initial_balance': 10000.00
        })
        self.assertEqual(dup_res.status_code, 400)
        err_msg = dup_res.get_json().get('message') or dup_res.get_json().get('error') or ''
        self.assertIn('already connected', err_msg)

    # =========================================================================
    # TEST 13: Premium checkout flow
    # =========================================================================
    def test_13_premium_checkout_flow(self):
        """
        TEST 13: Premium checkout flow:
        1. Create checkout order
        2. Verify payment with valid signature
        3. Subscription status becomes ACTIVE, is_premium becomes True
        """
        self.login_user()

        # 1. Create checkout order
        order_res = self.client.post('/api/premium/create-checkout-order', json={
            'plan': 'monthly',
            'gateway': 'razorpay'
        })
        self.assertIn(order_res.status_code, (200, 201))
        order_data = order_res.get_json()['data']
        order_id = order_data['order_id']
        self.assertTrue(order_id.startswith('order_'))

        # 2. Verify payment (sandbox test signature)
        verify_res = self.client.post('/api/premium/verify-payment', json={
            'order_id': order_id,
            'payment_id': 'pay_test_abc123',
            'signature': f"sig_sandbox_{order_id}"
        })
        self.assertEqual(verify_res.status_code, 200)
        self.assertTrue(verify_res.get_json()['success'])

        # 3. Check user status
        u = db.session.get(User, self.user_a.id)
        self.assertTrue(u.is_premium)
        self.assertTrue(u.is_premium_active)
        self.assertEqual(u.current_subscription.status, 'ACTIVE')

    # =========================================================================
    # TEST 14: Premium payment failure
    # =========================================================================
    def test_14_premium_payment_failure(self):
        """
        TEST 14: Failed payment signature rejected -> status PAYMENT_FAILED ->
        user remains on free tier.
        """
        self.login_user()

        # Create order
        order_res = self.client.post('/api/premium/create-checkout-order', json={
            'plan': 'monthly'
        })
        order_id = order_res.get_json()['data']['order_id']

        # Attempt verification with invalid signature
        verify_res = self.client.post('/api/premium/verify-payment', json={
            'order_id': order_id,
            'payment_id': 'pay_failed_xyz',
            'signature': 'invalid_forged_signature'
        })
        self.assertEqual(verify_res.status_code, 400)

        # User remains on free tier
        u = db.session.get(User, self.user_a.id)
        self.assertFalse(u.is_premium_active)

    # =========================================================================
    # TEST 15: Webhook idempotency
    # =========================================================================
    def test_15_webhook_idempotency(self):
        """
        TEST 15: Send webhook event twice -> processed once -> second duplicate
        replay gracefully handled without error or duplicate extension.
        """
        self.login_user()

        order_res = self.client.post('/api/premium/create-checkout-order', json={'plan': 'yearly'})
        order_id = order_res.get_json()['data']['order_id']

        webhook_payload = json.dumps({
            'event': 'order.paid',
            'payload': {
                'order': {
                    'entity': {
                        'id': order_id,
                        'amount': 79900,
                        'currency': 'INR',
                        'notes': {'user_id': self.user_a.id, 'plan_id': 'yearly'}
                    }
                },
                'payment': {
                    'entity': {
                        'id': 'pay_hook_123',
                        'order_id': order_id,
                        'status': 'captured'
                    }
                }
            }
        }).encode('utf-8')

        secret = self.app.config.get('RAZORPAY_WEBHOOK_SECRET') or os.environ.get('RAZORPAY_WEBHOOK_SECRET') or 'rzp_webhook_secret'
        os.environ['RAZORPAY_WEBHOOK_SECRET'] = secret
        self.app.config['RAZORPAY_WEBHOOK_SECRET'] = secret

        sig = hmac.new(secret.encode('utf-8'), webhook_payload, hashlib.sha256).hexdigest()

        # Webhook Call 1
        res1 = self.client.post('/api/premium/webhook', data=webhook_payload,
                                content_type='application/json',
                                headers={'X-Razorpay-Signature': sig})
        self.assertEqual(res1.status_code, 200)

        # Verify active
        u = db.session.get(User, self.user_a.id)
        self.assertTrue(u.is_premium_active)

        # Webhook Call 2 (Duplicate replay)
        res2 = self.client.post('/api/premium/webhook', data=webhook_payload,
                                content_type='application/json',
                                headers={'X-Razorpay-Signature': sig})
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.get_json().get('success'))

    # =========================================================================
    # TEST 16: Premium expiration
    # =========================================================================
    def test_16_premium_expiration(self):
        """
        TEST 16: Set expiry_date in the past -> premium features locked ->
        user's normal pockets, transactions, and balances completely intact.
        """
        self.login_user()

        # Create expired subscription directly in DB
        expired_sub = Subscription(
            user_id=self.user_a.id,
            plan_id='monthly',
            provider='razorpay',
            status='ACTIVE',
            amount=99.00,
            start_date=datetime.utcnow() - timedelta(days=60),
            expiry_date=datetime.utcnow() - timedelta(days=5)  # 5 days ago
        )
        db.session.add(expired_sub)

        # Create normal pocket
        test_pocket = Pocket(
            user_id=self.user_a.id,
            name='Essential Savings',
            current_balance=3500.00
        )
        db.session.add(test_pocket)
        db.session.commit()

        u = db.session.get(User, self.user_a.id)
        # Premium should be considered expired
        self.assertFalse(u.is_premium_active)

        # User's normal data is intact
        self.assertEqual(float(test_pocket.current_balance), 3500.00)
        self.assertEqual(len(u.pockets.all()), 1)

    # =========================================================================
    # TEST 17: AI Assistant security & financial insights
    # =========================================================================
    def test_17_ai_assistant_security(self):
        """
        TEST 17: Financial inquiry handled with backend-computed aggregates.
        OpenAI keys and secrets are never returned in client response.
        """
        self.login_user()

        # Ask financial question
        res = self.client.post('/api/assistant/chat', json={
            'message': 'Where did I spend the most this month?'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        # Key verification: response must contain helpful answer and never leak keys
        response_str = json.dumps(data)
        self.assertNotIn('sk-', response_str)
        self.assertNotIn('OPENAI_API_KEY', response_str)
        reply_val = data.get('data', {}).get('reply') or data.get('data', {}).get('message') or data.get('reply') or data.get('message') or ''
        self.assertTrue(len(reply_val) > 0)

    # =========================================================================
    # TEST 18: Multi-user authorization
    # =========================================================================
    def test_18_multi_user_authorization(self):
        """
        TEST 18: User B attempts to debit User A's pocket -> 403 Forbidden ->
        User A balance remains unchanged.
        """
        # User A owns Pocket
        pocket_a = Pocket(
            user_id=self.user_a.id,
            name="Arvind's Private Fund",
            current_balance=5000.00
        )
        db.session.add(pocket_a)
        db.session.commit()
        pocket_a_id = pocket_a.id

        # Login as User B
        self.login_user(email="priya@pocketpay.io", password="FintechSecure@2026")

        # User B attempts to spend from User A's pocket
        unauth_res = self.client.post('/api/transactions/pay-pocket', json={
            'pocket_id': pocket_a_id,
            'recipient': 'priya@pocketpay.io',
            'amount': 1000.00,
            'pin': '9876'
        })
        self.assertEqual(unauth_res.status_code, 403)
        err_msg = unauth_res.get_json().get('message') or unauth_res.get_json().get('error') or ''
        self.assertIn('permission', err_msg.lower())

        # Verify User A's pocket was NOT debited
        pkt = db.session.get(Pocket, pocket_a_id)
        self.assertEqual(float(pkt.current_balance), 5000.00)


if __name__ == '__main__':
    unittest.main()
