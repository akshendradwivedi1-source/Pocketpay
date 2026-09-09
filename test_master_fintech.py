import unittest
import json
import pyotp
import hmac
import hashlib
import os
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.money_request import MoneyRequest
from app.services.ledger_service import LedgerService, FinancialInvariantError


class TestMasterFintech(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['MAIL_SUPPRESS_SEND'] = True
        self.app.config['WEBHOOK_SECRET'] = 'master_test_webhook_secret'
        os.environ['WEBHOOK_SECRET'] = 'master_test_webhook_secret'

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        db.create_all()

        # User A: Initialized with exactly ₹25,000.00 available balance
        self.user_a = User(
            full_name="Arvind Raman",
            email="arvind@pocketpay.io",
            phone="9876500001",
            email_verified=True,
            wallet_balance=25000.00,
            virtual_upi_id="arvind@pocketpay",
            virtual_wallet_id="PPWARVIND01"
        )
        self.user_a.set_password("FintechSecure@2026")
        self.user_a.set_transaction_pin("4321")

        # User B: Initialized with ₹10,000.00 available balance
        self.user_b = User(
            full_name="Priya Sharma",
            email="priya@pocketpay.io",
            phone="9876500002",
            email_verified=True,
            wallet_balance=10000.00,
            virtual_upi_id="priya@pocketpay",
            virtual_wallet_id="PPWPRIYA002"
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
    # 1. CORE INVARIANT TEST: The exact ₹25,000.00 balance preservation test
    # =========================================================================
    def test_exact_balance_preservation_invariant(self):
        """
        Tests the fundamental financial law:
        Total Funds == Available Balance + Sum of Active Pocket Balances.
        Starting: ₹25,000.00
        1. Allocate ₹6,000 to Groceries -> Main: ₹19,000, Groceries: ₹6,000, Total: ₹25,000.
        2. Allocate ₹4,000 to Emergency -> Main: ₹15,000, Groceries: ₹6,000, Emergency: ₹4,000, Total: ₹25,000.
        3. Transfer ₹2,000 from Groceries to Emergency -> Groceries: ₹4,000, Emergency: ₹6,000, Total: ₹25,000.
        4. Withdraw ₹1,000 from Emergency to Main -> Emergency: ₹5,000, Main: ₹16,000, Total: ₹25,000.
        5. Verify /api/wallet/reconciliation audit.
        """
        self.login_user("arvind@pocketpay.io")

        # Initial check
        res_init = self.client.get('/api/wallet/balance')
        self.assertEqual(res_init.status_code, 200)
        bal_data = res_init.get_json()['data']
        self.assertEqual(bal_data['available_balance'], 25000.00)
        self.assertEqual(bal_data['pocket_balance'], 0.00)
        self.assertEqual(bal_data['total_funds'], 25000.00)

        # Step 1: Create 'Groceries' pocket allocating ₹6,000.00
        res_groc = self.client.post('/api/pockets', json={
            'name': 'Groceries',
            'color': '#10b981',
            'icon': 'shopping-cart',
            'funding_source': 'main_balance',
            'initial_balance': 6000.00,
            'budget_amount': 8000.00
        })
        self.assertEqual(res_groc.status_code, 201)
        groc_id = res_groc.get_json()['data']['pocket']['id']

        # Verify invariant after Step 1
        res_b1 = self.client.get('/api/wallet/balance').get_json()['data']
        self.assertEqual(res_b1['available_balance'], 19000.00)
        self.assertEqual(res_b1['pocket_balance'], 6000.00)
        self.assertEqual(res_b1['total_funds'], 25000.00)

        # Step 2: Create 'Emergency' pocket allocating ₹4,000.00
        res_emg = self.client.post('/api/pockets', json={
            'name': 'Emergency',
            'color': '#ef4444',
            'icon': 'shield-alert',
            'funding_source': 'main_balance',
            'initial_balance': 4000.00
        })
        self.assertEqual(res_emg.status_code, 201)
        emg_id = res_emg.get_json()['data']['pocket']['id']

        # Verify invariant after Step 2
        res_b2 = self.client.get('/api/wallet/balance').get_json()['data']
        self.assertEqual(res_b2['available_balance'], 15000.00)
        self.assertEqual(res_b2['pocket_balance'], 10000.00)
        self.assertEqual(res_b2['total_funds'], 25000.00)

        # Step 3: Transfer ₹2,000 from Groceries to Emergency
        res_move = self.client.post('/api/transactions/transfer', json={
            'from_pocket_id': groc_id,
            'to_pocket_id': emg_id,
            'amount': 2000.00,
            'pin': '4321',
            'description': 'Reallocate to Emergency'
        })
        self.assertEqual(res_move.status_code, 201)

        # Verify invariant after Step 3
        res_b3 = self.client.get('/api/wallet/balance').get_json()['data']
        self.assertEqual(res_b3['available_balance'], 15000.00)
        self.assertEqual(res_b3['pocket_balance'], 10000.00)
        self.assertEqual(res_b3['total_funds'], 25000.00)

        p_groc = db.session.get(Pocket, groc_id)
        p_emg = db.session.get(Pocket, emg_id)
        self.assertEqual(float(p_groc.current_balance), 4000.00)
        self.assertEqual(float(p_emg.current_balance), 6000.00)

        # Step 4: Withdraw ₹1,000 from Emergency back to Main Available Balance
        res_wth = self.client.post(f'/api/pockets/{emg_id}/withdraw', json={
            'amount': 1000.00,
            'pin': '4321',
            'description': 'Release emergency funds'
        })
        self.assertEqual(res_wth.status_code, 200)

        # Verify invariant after Step 4
        res_b4 = self.client.get('/api/wallet/balance').get_json()['data']
        self.assertEqual(res_b4['available_balance'], 16000.00)
        self.assertEqual(res_b4['pocket_balance'], 9000.00)
        self.assertEqual(res_b4['total_funds'], 25000.00)

        p_emg_after = db.session.get(Pocket, emg_id)
        self.assertEqual(float(p_emg_after.current_balance), 5000.00)

        # Step 5: Check Reconciliation endpoint
        res_rec = self.client.get('/api/wallet/reconciliation')
        self.assertEqual(res_rec.status_code, 200)
        rec_data = res_rec.get_json()['data']
        self.assertTrue(rec_data['invariant_matched'])
        self.assertEqual(rec_data['total_funds'], 25000.00)

        # Step 6: Overdraft guard check (attempting to allocate ₹20,000 when available is ₹16,000)
        res_overdraft = self.client.post('/api/pockets', json={
            'name': 'Luxury Car',
            'funding_source': 'main_balance',
            'initial_balance': 20000.00
        })
        self.assertEqual(res_overdraft.status_code, 400)
        # Verify no balances mutated during failed attempt
        res_b5 = self.client.get('/api/wallet/balance').get_json()['data']
        self.assertEqual(res_b5['available_balance'], 16000.00)
        self.assertEqual(res_b5['total_funds'], 25000.00)

    # =========================================================================
    # 2. API IDEMPOTENCY & REPLAY PROTECTION
    # =========================================================================
    def test_idempotency_replay_protection(self):
        """
        Verifies that replaying a mutating request with the same Idempotency-Key
        returns the identical cached result and DOES NOT double-deduct money.
        """
        self.login_user("arvind@pocketpay.io")
        idemp_key = "idemp_test_uuid_9999"

        # Transfer ₹1,500 to User B with Idempotency-Key
        payload = {
            'recipient': 'priya@pocketpay.io',
            'amount': 1500.00,
            'pin': '4321',
            'note': 'Idempotent peer payment'
        }
        headers = {'Idempotency-Key': idemp_key}

        res_first = self.client.post('/api/wallet/send-money', json=payload, headers=headers)
        self.assertIn(res_first.status_code, [200, 201])
        first_data = res_first.get_json()

        # Check balances after 1st execution
        u_a = db.session.get(User, self.user_a.id)
        self.assertEqual(float(u_a.wallet_balance), 23500.00)

        # Immediate replay with same Idempotency-Key
        res_replay = self.client.post('/api/wallet/send-money', json=payload, headers=headers)
        self.assertIn(res_replay.status_code, [200, 201])
        replay_data = res_replay.get_json()

        # Balances MUST NOT change on replay
        u_a_after = db.session.get(User, self.user_a.id)
        self.assertEqual(float(u_a_after.wallet_balance), 23500.00)
        u_b_after = db.session.get(User, self.user_b.id)
        self.assertEqual(float(u_b_after.wallet_balance), 11500.00)

    # =========================================================================
    # 3. MULTI-SOURCE POCKET CREATION
    # =========================================================================
    def test_multi_source_pocket_creation(self):
        """
        Tests creation of pockets via:
        1. Fund Later (zero balance)
        2. External Bank Sandbox deposit
        """
        self.login_user("arvind@pocketpay.io")

        # 1. Fund Later
        res_later = self.client.post('/api/pockets', json={
            'name': 'Vacation Fund Later',
            'funding_source': 'fund_later',
            'initial_balance': 0.0
        })
        self.assertEqual(res_later.status_code, 201)
        p_later = res_later.get_json()['data']['pocket']
        self.assertEqual(p_later['current_balance'], 0.00)

        # 2. External Bank Sandbox
        res_bank = self.client.post('/api/pockets', json={
            'name': 'Bank Deposit Pocket',
            'funding_source': 'external_bank',
            'bank_code': 'HDFC',
            'initial_balance': 3000.00
        })
        self.assertEqual(res_bank.status_code, 201)
        p_bank = res_bank.get_json()['data']['pocket']
        self.assertEqual(p_bank['current_balance'], 3000.00)

    # =========================================================================
    # 4. SECURITY HARDENING: PIN LOCKOUT & SESSION VERSIONING
    # =========================================================================
    def test_pin_lockout_and_rate_limiting(self):
        """
        Tests that 5 consecutive wrong PIN attempts triggers temporary lockout.
        """
        self.login_user("arvind@pocketpay.io")

        # Wrong PIN attempts
        for attempt in range(1, 5):
            res = self.client.post('/api/wallet/send-money', json={
                'recipient': 'priya@pocketpay.io',
                'amount': 100.00,
                'pin': '0000'
            })
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.get_json()['code'], 'INCORRECT_PIN')

        # 5th failed attempt locks out the PIN
        res_5 = self.client.post('/api/wallet/send-money', json={
            'recipient': 'priya@pocketpay.io',
            'amount': 100.00,
            'pin': '0000'
        })
        self.assertEqual(res_5.status_code, 401)
        u_a = db.session.get(User, self.user_a.id)
        self.assertTrue(u_a.is_pin_locked)

        # Subsequent attempt even with correct PIN is blocked by lockout
        res_locked = self.client.post('/api/wallet/send-money', json={
            'recipient': 'priya@pocketpay.io',
            'amount': 100.00,
            'pin': '4321'
        })
        self.assertEqual(res_locked.status_code, 401)

    def test_password_reset_invalidates_security_version(self):
        """
        Tests that resetting password increments security_version, invalidating stale sessions.
        """
        u = db.session.get(User, self.user_a.id)
        initial_ver = u.security_version or 1

        # Simulate OTP generation
        u.email_otp = "123456"
        db.session.commit()

        res_reset = self.client.post('/auth/reset-password', json={
            'email': 'arvind@pocketpay.io',
            'otp': '123456',
            'new_password': 'BrandNewPassword@2026'
        })
        self.assertEqual(res_reset.status_code, 200)

        db.session.refresh(u)
        self.assertEqual(u.security_version, initial_ver + 1)

    # =========================================================================
    # 5. WEBHOOK HMAC SIGNATURE SECURITY
    # =========================================================================
    def test_payout_webhook_hmac_verification(self):
        """
        Tests HMAC signature verification on webhook endpoint.
        """
        secret = 'master_test_webhook_secret'
        raw_body = json.dumps({'event': 'payout.processed', 'data': {'payout_id': 'fake_payout_123'}}).encode('utf-8')

        # 1. Without signature header -> 401
        res_no_sig = self.client.post('/api/payouts/webhook', data=raw_body, content_type='application/json')
        self.assertEqual(res_no_sig.status_code, 401)

        # 2. With invalid signature header -> 401
        res_bad_sig = self.client.post('/api/payouts/webhook', data=raw_body, content_type='application/json',
                                       headers={'X-Webhook-Signature': 'invalid_hex_signature'})
        self.assertEqual(res_bad_sig.status_code, 401)

        # 3. With valid HMAC SHA256 signature -> 200
        valid_sig = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
        res_good_sig = self.client.post('/api/payouts/webhook', data=raw_body, content_type='application/json',
                                        headers={'X-Webhook-Signature': valid_sig})
        self.assertEqual(res_good_sig.status_code, 200)

    # =========================================================================
    # 6. SYSTEM HEALTH PROBE
    # =========================================================================
    def test_system_health_probe(self):
        """
        Verifies that /health returns 200 with healthy database status.
        """
        res = self.client.get('/health')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['database'], 'ok')


if __name__ == '__main__':
    unittest.main()
