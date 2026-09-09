import unittest
import json
import openai
from unittest.mock import patch, MagicMock
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.transaction import Transaction
from app.services.assistant_service import AssistantService


class TestPocketPayFullRequirements(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['MAIL_SUPPRESS_SEND'] = True
        self.app.config['OPENAI_API_KEY'] = None
        self.app.config['OPENAI_MODEL'] = 'gpt-4o-mini'

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self, email, password):
        return self.client.post('/auth/login', json={
            'email': email,
            'password': password
        })

    # =========================================================================
    # TEST A: FIRST-LOGIN SECURITY CREDENTIAL SETUP
    # =========================================================================
    def test_a_security_credential_setup_flow(self):
        # 1. Register new user without transaction PIN
        user = User(
            full_name="New Security User",
            email="newsec@pocketpay.app",
            phone="9876543299",
            email_verified=True,
            wallet_balance=1000.0,
            security_setup_completed=False
        )
        user.set_password("SecurePass@123")
        db.session.add(user)
        db.session.commit()

        # Check model properties
        self.assertTrue(user.security_setup_required)
        self.assertFalse(user.security_setup_completed)
        self.assertIsNone(user.transaction_pin_hash)

        # 2. Login as new user
        res = self._login("newsec@pocketpay.app", "SecurePass@123")
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data['success'])
        # Disclaimer flag must be true
        self.assertTrue(data['data']['security_setup_required'])
        self.assertFalse(data['data']['security_setup_completed'])

        # 3. Setup 4-digit PIN via complete-security-setup endpoint
        setup_res = self.client.post('/auth/complete-security-setup', json={
            'pin': '4321',
            'confirm_pin': '4321'
        })
        setup_data = setup_res.get_json()
        self.assertEqual(setup_res.status_code, 200)
        self.assertTrue(setup_data['success'])
        self.assertTrue(setup_data['data']['security_setup_completed'])

        # Refresh user from DB
        db.session.refresh(user)
        self.assertTrue(user.security_setup_completed)
        self.assertFalse(user.security_setup_required)
        # Ensure PIN is hashed and never plaintext
        self.assertIsNotNone(user.transaction_pin_hash)
        self.assertNotEqual(user.transaction_pin_hash, "4321")
        self.assertTrue(user.check_transaction_pin("4321"))
        self.assertFalse(user.check_transaction_pin("9999"))

        # 4. Subsequent login -> security_setup_required must now be False
        res2 = self._login("newsec@pocketpay.app", "SecurePass@123")
        data2 = res2.get_json()
        self.assertEqual(res2.status_code, 200)
        self.assertFalse(data2['data']['security_setup_required'])
        self.assertTrue(data2['data']['security_setup_completed'])

    # =========================================================================
    # TEST B: MACHINE-READABLE QR CODE & RESOLUTION
    # =========================================================================
    def test_b_machine_readable_qr_code_and_resolution(self):
        user = User(
            full_name="Merchant Raj",
            email="raj@pocketpay.app",
            phone="9876543288",
            email_verified=True,
            wallet_balance=5000.0,
            virtual_upi_id="raj@pocketpay",
            virtual_wallet_id="PPWRAJ001"
        )
        user.set_password("SecurePass@123")
        user.set_transaction_pin("1234")
        user.security_setup_completed = True
        db.session.add(user)
        db.session.commit()

        self._login("raj@pocketpay.app", "SecurePass@123")

        # 1. Fetch wallet QR endpoint
        res = self.client.get('/auth/wallet-qr')
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data['success'])
        qr_data = data['data']
        # Must contain base64 image data
        self.assertTrue(qr_data['qr_code_base64'].startswith('data:image/png;base64,'))
        # Must contain standard upi:// format payload
        self.assertTrue(qr_data['qr_payload'].startswith('upi://pay?pa='))
        self.assertIn('raj@pocketpay', qr_data['qr_payload'])

        # 2. Resolve QR payload via /qr/resolve
        resolve_res = self.client.post('/qr/resolve', json={
            'content': qr_data['qr_payload']
        })
        res_data = resolve_res.get_json()
        self.assertEqual(resolve_res.status_code, 200)
        self.assertTrue(res_data['success'])
        self.assertEqual(res_data['data']['name'], "Merchant Raj")
        # Ensure no secrets leaked
        self.assertNotIn('password', res_data['data'])
        self.assertNotIn('transaction_pin_hash', res_data['data'])

    # =========================================================================
    # TEST C: NETBANKING BENEFICIARY TRANSFER (ATOMIC BACKEND)
    # =========================================================================
    def test_c_netbanking_beneficiary_transfer(self):
        # TEST C: Sender ₹10,000, Beneficiary ₹2,000 -> transfer ₹500 -> Sender ₹9,500, Beneficiary ₹2,500
        sender = User(
            full_name="Sender Vikram",
            email="vikram@pocketpay.app",
            phone="9876543201",
            email_verified=True,
            wallet_balance=10000.0,
            virtual_upi_id="vikram@pocketpay",
            virtual_wallet_id="PPWVIK001"
        )
        sender.set_password("SecurePass@123")
        sender.set_transaction_pin("1234")
        sender.security_setup_completed = True

        beneficiary = User(
            full_name="Beneficiary Anita",
            email="anita@pocketpay.app",
            phone="9876543202",
            email_verified=True,
            wallet_balance=2000.0,
            virtual_upi_id="anita@pocketpay",
            virtual_wallet_id="PPWANI002"
        )
        beneficiary.set_password("SecurePass@123")
        beneficiary.set_transaction_pin("5678")
        beneficiary.security_setup_completed = True

        db.session.add_all([sender, beneficiary])
        db.session.commit()

        self._login("vikram@pocketpay.app", "SecurePass@123")

        # Execute netbanking transfer of ₹500 to beneficiary's virtual wallet ID / account
        res = self.client.post('/api/payouts/netbanking-transfer', json={
            'bank_code': 'HDFC',
            'account_holder': 'Beneficiary Anita',
            'account_number': 'PPWANI002',
            'amount': 500.0,
            'pin': '1234',
            'idempotency_key': 'test_netbank_001'
        })
        data = res.get_json()
        self.assertIn(res.status_code, [200, 201])
        self.assertTrue(data['success'])

        # Refresh from database
        db.session.refresh(sender)
        db.session.refresh(beneficiary)

        # Sender should be ₹9,500 and Beneficiary should be ₹2,500
        self.assertEqual(sender.wallet_balance, 9500.0)
        self.assertEqual(beneficiary.wallet_balance, 2500.0)

        # Dual ledger transactions check
        sender_tx = Transaction.query.filter_by(user_id=sender.id, amount=500.0).first()
        self.assertIsNotNone(sender_tx)
        self.assertIn(sender_tx.type, ['withdraw', 'payout'])

        beneficiary_tx = Transaction.query.filter_by(user_id=beneficiary.id, amount=500.0).first()
        self.assertIsNotNone(beneficiary_tx)
        self.assertIn(beneficiary_tx.type, ['peer_receive', 'deposit'])

    # =========================================================================
    # TEST D: INSUFFICIENT BALANCE REJECTION
    # =========================================================================
    def test_d_insufficient_balance_rejection(self):
        sender = User(
            full_name="Low Balance User",
            email="lowbal@pocketpay.app",
            phone="9876543203",
            email_verified=True,
            wallet_balance=500.0
        )
        sender.set_password("SecurePass@123")
        sender.set_transaction_pin("1234")
        sender.security_setup_completed = True

        beneficiary = User(
            full_name="Beneficiary Two",
            email="ben2@pocketpay.app",
            phone="9876543204",
            email_verified=True,
            wallet_balance=1000.0,
            virtual_wallet_id="PPWBEN002"
        )
        beneficiary.set_password("SecurePass@123")
        beneficiary.set_transaction_pin("1234")
        beneficiary.security_setup_completed = True

        db.session.add_all([sender, beneficiary])
        db.session.commit()

        self._login("lowbal@pocketpay.app", "SecurePass@123")

        # Attempt to transfer ₹2,000 when sender only has ₹500
        res = self.client.post('/api/payouts/netbanking-transfer', json={
            'bank_code': 'SBIN',
            'account_holder': 'Beneficiary Two',
            'account_number': 'PPWBEN002',
            'amount': 2000.0,
            'pin': '1234',
            'idempotency_key': 'test_insufficient_001'
        })
        self.assertEqual(res.status_code, 400)

        # Balances remain untouched
        db.session.refresh(sender)
        db.session.refresh(beneficiary)
        self.assertEqual(sender.wallet_balance, 500.0)
        self.assertEqual(beneficiary.wallet_balance, 1000.0)

    # =========================================================================
    # TEST E: IDEMPOTENCY PREVENTS DOUBLE DEBIT
    # =========================================================================
    def test_e_idempotency_prevents_double_debit(self):
        sender = User(
            full_name="Idem Sender",
            email="idem@pocketpay.app",
            phone="9876543205",
            email_verified=True,
            wallet_balance=5000.0
        )
        sender.set_password("SecurePass@123")
        sender.set_transaction_pin("1234")
        sender.security_setup_completed = True

        ben = User(
            full_name="Idem Ben",
            email="idemben@pocketpay.app",
            phone="9876543206",
            email_verified=True,
            wallet_balance=1000.0,
            virtual_wallet_id="PPWIDEM001"
        )
        ben.set_password("SecurePass@123")
        ben.set_transaction_pin("1234")
        ben.security_setup_completed = True

        db.session.add_all([sender, ben])
        db.session.commit()

        self._login("idem@pocketpay.app", "SecurePass@123")

        # First request
        res1 = self.client.post('/api/payouts/netbanking-transfer', json={
            'bank_code': 'ICIC',
            'account_holder': 'Idem Ben',
            'account_number': 'PPWIDEM001',
            'amount': 500.0,
            'pin': '1234',
            'idempotency_key': 'idem_key_xyz'
        })
        self.assertIn(res1.status_code, [200, 201])

        # Second request with SAME idempotency key
        res2 = self.client.post('/api/payouts/netbanking-transfer', json={
            'bank_code': 'ICIC',
            'account_holder': 'Idem Ben',
            'account_number': 'PPWIDEM001',
            'amount': 500.0,
            'pin': '1234',
            'idempotency_key': 'idem_key_xyz'
        })
        self.assertIn(res2.status_code, [200, 201])

        # Sender should be ₹4,500 (debited once only), Beneficiary ₹1,500
        db.session.refresh(sender)
        db.session.refresh(ben)
        self.assertEqual(sender.wallet_balance, 4500.0)
        self.assertEqual(ben.wallet_balance, 1500.0)

    # =========================================================================
    # TEST F: BANK DISCONNECT BALANCE RECONCILIATION
    # =========================================================================
    def test_f_bank_disconnect_balance_reconciliation(self):
        # User starts with ₹500 independent PocketPay balance
        user = User(
            full_name="Reconcile User",
            email="reconcile@pocketpay.app",
            phone="9876543207",
            email_verified=True,
            wallet_balance=500.0
        )
        user.set_password("SecurePass@123")
        user.set_transaction_pin("1234")
        user.security_setup_completed = True
        db.session.add(user)
        db.session.commit()

        self._login("reconcile@pocketpay.app", "SecurePass@123")

        # Link bank account with ₹25,000
        link_res = self.client.post('/auth/link-bank-account', json={
            'bank_name': 'State Bank of India',
            'account_number': '123456789012',
            'ifsc_code': 'SBIN0001234',
            'account_holder': 'Reconcile User',
            'initial_balance': 25000.0
        })
        self.assertIn(link_res.status_code, [200, 201])

        db.session.refresh(user)
        # Total available balance should now be ₹25,500
        self.assertEqual(user.wallet_balance, 25500.0)
        self.assertEqual(user.total_available_balance, 25500.0)
        self.assertEqual(user.connected_bank_balance, 25000.0)
        self.assertEqual(user.own_wallet_balance, 500.0)

        self.assertTrue(len(user.linked_banks or []) > 0)
        bank_id = user.linked_banks[0]['id']

        # Disconnect bank account
        unlink_res = self.client.post('/auth/unlink-bank-account', json={
            'bank_id': bank_id
        })
        self.assertEqual(unlink_res.status_code, 200)

        db.session.refresh(user)
        # After disconnecting ₹25,000 bank, total balance must be ₹500
        self.assertEqual(user.wallet_balance, 500.0)
        self.assertEqual(user.total_available_balance, 500.0)
        self.assertEqual(user.connected_bank_balance, 0.0)
        self.assertEqual(user.own_wallet_balance, 500.0)

    # =========================================================================
    # TEST G: BANK RECONNECTION DUPLICATE CREDIT PREVENTION
    # =========================================================================
    def test_g_bank_reconnection(self):
        user = User(
            full_name="Reconnect User",
            email="reconnect@pocketpay.app",
            phone="9876543208",
            email_verified=True,
            wallet_balance=500.0
        )
        user.set_password("SecurePass@123")
        user.set_transaction_pin("1234")
        user.security_setup_completed = True
        db.session.add(user)
        db.session.commit()

        self._login("reconnect@pocketpay.app", "SecurePass@123")

        # Connect bank first time (balance ₹25,000)
        self.client.post('/auth/link-bank-account', json={
            'bank_name': 'HDFC Bank',
            'account_number': '998877665544',
            'ifsc_code': 'HDFC0001234',
            'account_holder': 'Reconnect User',
            'initial_balance': 25000.0
        })

        db.session.refresh(user)
        self.assertEqual(user.wallet_balance, 25500.0)

        # Attempt to link SAME bank account again while connected -> rejected
        dup_res = self.client.post('/auth/link-bank-account', json={
            'bank_name': 'HDFC Bank',
            'account_number': '998877665544',
            'ifsc_code': 'HDFC0001234',
            'account_holder': 'Reconnect User',
            'initial_balance': 25000.0
        })
        self.assertEqual(dup_res.status_code, 400)

        # Balance remains ₹25,500, NOT ₹50,500
        db.session.refresh(user)
        self.assertEqual(user.wallet_balance, 25500.0)

    # =========================================================================
    # TEST H: ASSISTANT QUERY, GUARDRAILS & API KEY SECURITY
    # =========================================================================
    def test_h_assistant_query_and_api_key_security(self):
        user = User(
            full_name="AI User",
            email="aiuser@pocketpay.app",
            phone="9876543209",
            email_verified=True,
            wallet_balance=7500.0
        )
        user.set_password("SecurePass@123")
        user.set_transaction_pin("1234")
        user.security_setup_completed = True
        db.session.add(user)
        db.session.commit()

        self._login("aiuser@pocketpay.app", "SecurePass@123")

        # 1. Test query with transfer intent - guardrails should trigger transfer prompt, NOT execute transfer
        res_guardrail = self.client.post('/api/assistant/ask', json={
            'query': 'pay 500 to Bob'
        })
        self.assertEqual(res_guardrail.status_code, 200)
        data_g = res_guardrail.get_json()
        self.assertTrue(data_g['success'])
        self.assertEqual(data_g['data']['type'], 'transaction_prompt')
        self.assertIn('Send Money', json.dumps(data_g['data']['actions']))
        # Ensure user balance unchanged
        db.session.refresh(user)
        self.assertEqual(user.wallet_balance, 7500.0)

        # 2. Test fallback response when OpenAI key is not present
        res_fb = self.client.post('/api/assistant/ask', json={
            'query': 'What is my current balance?'
        })
        self.assertEqual(res_fb.status_code, 200)
        data_fb = res_fb.get_json()
        self.assertTrue(data_fb['success'])
        self.assertIn('title', data_fb['data'])
        self.assertIn('message', data_fb['data'])

        # 3. Test real OpenAI integration with mock and verify secret key is never leaked
        with patch('app.services.assistant_service.openai.OpenAI') as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_completion = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = json.dumps({
                "title": "💳 AI Financial Summary",
                "message": "You currently have <b>₹7,500.00</b> in your PocketPay wallet.",
                "actions": [{"label": "View Balance", "icon": "wallet", "action": "balance"}],
                "suggested_prompts": ["Show my pockets"]
            })
            mock_completion.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_completion

            secret_key = 'sk-test-super-secret-key-12345'
            self.app.config['OPENAI_API_KEY'] = secret_key
            try:
                res_ai = self.client.post('/api/assistant/ask', json={'query': 'Tell me about my balance'})
                self.assertEqual(res_ai.status_code, 200)
                data_ai = res_ai.get_json()
                self.assertTrue(data_ai['success'])
                self.assertEqual(data_ai['data']['title'], "💳 AI Financial Summary")
                self.assertIn('actions', data_ai['data'])
                self.assertIn('suggested_prompts', data_ai['data'])

                # Critical: API key must NEVER be leaked in the response
                res_str = json.dumps(data_ai)
                self.assertNotIn(secret_key, res_str)
                self.assertNotIn('OPENAI_API_KEY', res_str)
            finally:
                self.app.config['OPENAI_API_KEY'] = None

        # 4. Test alias endpoint /api/assistant
        res_alias = self.client.post('/api/assistant', json={
            'query': 'How do pockets work?'
        })
        self.assertEqual(res_alias.status_code, 200)
        self.assertTrue(res_alias.get_json()['success'])

    # =========================================================================
    # TEST I: MULTI-USER AUTH & AUTHORIZATION ISOLATION
    # =========================================================================
    def test_i_multi_user_authorization_scoping(self):
        user_a = User(
            full_name="User Alpha",
            email="alpha@pocketpay.app",
            phone="9876543211",
            email_verified=True,
            wallet_balance=1000.0
        )
        user_a.set_password("SecurePass@123")
        user_a.set_transaction_pin("1234")

        user_b = User(
            full_name="User Beta",
            email="beta@pocketpay.app",
            phone="9876543212",
            email_verified=True,
            wallet_balance=5000.0
        )
        user_b.set_password("SecurePass@123")
        user_b.set_transaction_pin("5678")

        db.session.add_all([user_a, user_b])
        db.session.commit()

        # Login as User A
        self._login("alpha@pocketpay.app", "SecurePass@123")

        # User A's /auth/me returns only User A's data
        me_res = self.client.get('/auth/me')
        me_data = me_res.get_json()
        self.assertEqual(me_data['data']['user']['email'], "alpha@pocketpay.app")
        self.assertEqual(me_data['data']['user']['wallet_balance'], 1000.0)
        self.assertNotEqual(me_data['data']['user']['wallet_balance'], 5000.0)


if __name__ == '__main__':
    unittest.main()
