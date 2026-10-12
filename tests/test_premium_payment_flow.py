import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app, db
from app.models.user import User
from app.models.subscription import Subscription
from app.models.transaction import Transaction


class TestPremiumPaymentFlow(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Create user with insufficient balance (₹50)
        self.poor_user = User(
            email="poor@pocketpay.app",
            full_name="Poor User",
            phone="9800000001",
            virtual_wallet_id="PPW_POOR_001",
            virtual_upi_id="poor@pocketpay",
            wallet_balance=50.0,
            is_premium=False,
            security_setup_completed=True
        )
        self.poor_user.set_password("SecurePass@123")
        self.poor_user.set_transaction_pin("1234")
        db.session.add(self.poor_user)

        # Create user with sufficient balance (₹5000)
        self.rich_user = User(
            email="rich@pocketpay.app",
            full_name="Rich User",
            phone="9800000002",
            virtual_wallet_id="PPW_RICH_002",
            virtual_upi_id="rich@pocketpay",
            wallet_balance=5000.0,
            is_premium=False,
            security_setup_completed=True
        )
        self.rich_user.set_password("SecurePass@123")
        self.rich_user.set_transaction_pin("1234")
        db.session.add(self.rich_user)

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self, email, password="SecurePass@123"):
        return self.client.post('/auth/login', json={
            'email': email,
            'password': password
        })

    # =========================================================================
    # 1. RAZORPAY PAYMENT FLOW TESTS
    # =========================================================================
    def test_razorpay_order_creation_and_failure_handling(self):
        """Test that order creation doesn't activate premium, and invalid signature fails."""
        self.login("poor@pocketpay.app")

        # 1. Check initial status is not premium
        res = self.client.get('/api/premium/status')
        self.assertFalse(res.get_json()['data']['is_premium'])

        # 2. Create Razorpay order
        order_res = self.client.post('/api/premium/create-checkout-order', json={'plan_id': 'monthly'})
        self.assertEqual(order_res.status_code, 201)
        order_data = order_res.get_json()['data']
        order_id = order_data['order_id']
        self.assertIsNotNone(order_id)

        # Re-check status - creating order must NOT activate Premium
        res_after_order = self.client.get('/api/premium/status')
        self.assertFalse(res_after_order.get_json()['data']['is_premium'])

        # 3. Invalid signature must fail and NOT activate Premium
        fail_res = self.client.post('/api/premium/verify-payment', json={
            'order_id': order_id,
            'payment_id': 'pay_failed_fake',
            'signature': 'invalid_signature_attempt'
        })
        self.assertEqual(fail_res.status_code, 400)

        # Verify in DB user remains non-premium
        u = db.session.get(User, self.poor_user.id)
        self.assertFalse(u.is_premium)
        self.assertFalse(u.is_premium_active)

    def test_razorpay_successful_verification_activates_premium(self):
        """Test valid signature verification activates Premium and stores transaction."""
        self.login("rich@pocketpay.app")

        # Create order
        order_res = self.client.post('/api/premium/create-checkout-order', json={'plan_id': 'yearly'})
        self.assertEqual(order_res.status_code, 201)
        order_id = order_res.get_json()['data']['order_id']

        # Verify with valid sandbox signature (under TESTING=True)
        sandbox_sig = f"sig_sandbox_{order_id}"
        verify_res = self.client.post('/api/premium/verify-payment', json={
            'order_id': order_id,
            'payment_id': f"pay_rzp_{order_id}",
            'signature': sandbox_sig
        })
        self.assertEqual(verify_res.status_code, 200)

        # User is now premium
        u = db.session.get(User, self.rich_user.id)
        self.assertTrue(u.is_premium)
        self.assertTrue(u.is_premium_active)

        # Transaction recorded in database
        tx = Transaction.query.filter_by(reference_id=order_id).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.status, 'completed')
        self.assertEqual(tx.amount, 799.0)

    # =========================================================================
    # 2. POCKETPAY PAYMENT FLOW TESTS
    # =========================================================================
    def test_pocketpay_insufficient_balance_rejected(self):
        """PocketPay payment initiation must reject when wallet balance is insufficient."""
        self.login("poor@pocketpay.app")

        # Wallet has ₹50, monthly plan requires ₹99
        res = self.client.post('/api/premium/pocketpay/initiate', json={
            'plan_id': 'monthly',
            'identifier': 'PPW_POOR_001'
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Insufficient', data['message'])

        # User remains non-premium
        u = db.session.get(User, self.poor_user.id)
        self.assertFalse(u.is_premium)

    def test_pocketpay_invalid_account_identifier_rejected(self):
        """PocketPay payment initiation must reject invalid/non-existent account ID."""
        self.login("rich@pocketpay.app")

        res = self.client.post('/api/premium/pocketpay/initiate', json={
            'plan_id': 'monthly',
            'identifier': 'PPW_DOES_NOT_EXIST_999'
        })
        self.assertEqual(res.status_code, 404)
        self.assertFalse(res.get_json()['success'])

    @patch('app.utils.email_service.send_otp_email')
    def test_pocketpay_full_flow_otp_and_deduction(self, mock_email):
        """Test full PocketPay payment flow: initiate OTP -> verify & deduct -> activate."""
        mock_email.return_value = (True, "Sent")
        self.login("rich@pocketpay.app")

        # Initial wallet balance ₹5000
        initial_balance = self.rich_user.wallet_balance
        self.assertEqual(initial_balance, 5000.0)

        # 1. Step 1: Initiate payment with PocketPay ID
        init_res = self.client.post('/api/premium/pocketpay/initiate', json={
            'plan_id': 'monthly',
            'identifier': self.rich_user.virtual_wallet_id
        })
        self.assertEqual(init_res.status_code, 200)
        init_data = init_res.get_json()['data']
        self.assertTrue(init_res.get_json()['success'])
        self.assertIn('masked_email', init_data)
        self.assertEqual(init_data['amount'], 99.0)

        # User is NOT premium yet!
        u_mid = db.session.get(User, self.rich_user.id)
        self.assertFalse(u_mid.is_premium)
        self.assertEqual(u_mid.wallet_balance, 5000.0)

        # 2. Test Step 2 with incorrect OTP -> must fail and NOT deduct
        fail_otp_res = self.client.post('/api/premium/pocketpay/confirm', json={
            'plan_id': 'monthly',
            'identifier': self.rich_user.virtual_wallet_id,
            'otp': '000000'
        })
        self.assertEqual(fail_otp_res.status_code, 400)
        self.assertFalse(fail_otp_res.get_json()['success'])

        # Balance remains untouched
        db.session.refresh(self.rich_user)
        self.assertEqual(self.rich_user.wallet_balance, 5000.0)
        self.assertFalse(self.rich_user.is_premium)

        # 3. Test Step 2 with valid OTP -> succeeds, deducts, and activates
        valid_otp = self.rich_user.email_otp
        self.assertIsNotNone(valid_otp)

        confirm_res = self.client.post('/api/premium/pocketpay/confirm', json={
            'plan_id': 'monthly',
            'identifier': self.rich_user.virtual_wallet_id,
            'otp': valid_otp
        })
        self.assertEqual(confirm_res.status_code, 200)
        confirm_data = confirm_res.get_json()['data']
        self.assertTrue(confirm_res.get_json()['success'])
        self.assertEqual(confirm_data['new_balance'], 4901.0)  # 5000 - 99

        # Verify DB state
        db.session.refresh(self.rich_user)
        self.assertEqual(self.rich_user.wallet_balance, 4901.0)
        self.assertTrue(self.rich_user.is_premium)
        self.assertTrue(self.rich_user.is_premium_active)

        # Verify Subscription in DB
        sub = Subscription.query.filter_by(user_id=self.rich_user.id, status='ACTIVE').first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.provider, 'pocketpay')
        self.assertEqual(sub.amount, 99.0)

        # Verify Transaction in DB
        tx = Transaction.query.filter_by(user_id=self.rich_user.id, payment_method='pocketpay_wallet').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.status, 'completed')
        self.assertEqual(tx.amount, 99.0)
        self.assertEqual(tx.source_type, 'main_balance')
        self.assertEqual(tx.destination_type, 'subscription')

    def test_refresh_page_does_not_activate_premium_without_payment(self):
        """Refreshing / checking status without payment keeps account on standard tier."""
        self.login("poor@pocketpay.app")

        for _ in range(3):
            res = self.client.get('/api/premium/status')
            data = res.get_json()['data']
            self.assertFalse(data['is_premium'])
            self.assertEqual(data['subscription_status'], 'NONE')
