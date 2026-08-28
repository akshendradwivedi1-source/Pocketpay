import unittest
import json
import pyotp
from unittest.mock import patch
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.notification import Notification
from app.models.money_request import MoneyRequest
from app.models.goal import SavingsGoal
from app.telegram.handlers import TelegramHandler
from app.telegram.session import SessionManager
from app.services.assistant_service import AssistantService


class TestPocketPayFintechSuite(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['MAIL_SUPPRESS_SEND'] = True
        self.app.config['POCKETPAY_ADMIN_EMAIL'] = 'admin@pocketpay.app'
        self.app.config['ADMIN_PASSWORD'] = 'Admin@PocketPay2026'
        
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        db.create_all()
        from app.seeds import ensure_admin_user_exists
        ensure_admin_user_exists()
        
        # Create Test User 1
        self.user1 = User(
            full_name="Alice Trader",
            email="alice@pocketpay.app",
            phone="9876543210",
            email_verified=True,
            wallet_balance=10000.0,
            virtual_upi_id="alice@pocketpay",
            virtual_wallet_id="PPWALICE01"
        )
        self.user1.set_password("SecurePass@123")
        self.user1.set_transaction_pin("1234")
        
        # Create Test User 2
        self.user2 = User(
            full_name="Bob Builder",
            email="bob@pocketpay.app",
            phone="9876543211",
            email_verified=True,
            wallet_balance=5000.0,
            virtual_upi_id="bob@pocketpay",
            virtual_wallet_id="PPWBOB0002"
        )
        self.user2.set_password("SecurePass@123")
        self.user2.set_transaction_pin("5678")
        
        db.session.add_all([self.user1, self.user2])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login_client(self, email="alice@pocketpay.app", password="SecurePass@123"):
        return self.client.post('/auth/login', json={
            'email': email,
            'password': password
        })

    # =========================================================================
    # 1. AUTH & SECURITY TESTS
    # =========================================================================
    def test_auth_login_and_session(self):
        res = self.login_client()
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['user']['email'], 'alice@pocketpay.app')

    def test_totp_2fa_lifecycle(self):
        self.login_client()
        
        # Setup TOTP
        res = self.client.post('/auth/totp/setup')
        self.assertEqual(res.status_code, 200)
        secret = res.get_json()['data']['secret']
        self.assertTrue(bool(secret))
        
        # Verify and Enable TOTP with current code
        totp = pyotp.TOTP(secret)
        code = totp.now()
        
        res = self.client.post('/auth/totp/verify-setup', json={'code': code, 'secret': secret})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']['backup_codes']), 8)

    # =========================================================================
    # 2. POCKETS & TRANSFERS
    # =========================================================================
    def test_pocket_lifecycle_and_transfer(self):
        self.login_client()
        
        # 1. Create Pocket A
        res_a = self.client.post('/api/pockets', json={
            'name': 'Food & Groceries',
            'color': '#f97316',
            'icon': 'utensils',
            'budget_amount': 5000.0,
            'monthly_limit': 5000.0,
            'initial_balance': 2000.0
        })
        self.assertEqual(res_a.status_code, 201)
        pocket_a = res_a.get_json()['data']['pocket']
        self.assertEqual(pocket_a['current_balance'], 2000.0)
        
        # 2. Create Pocket B
        res_b = self.client.post('/api/pockets', json={
            'name': 'Savings Vault',
            'color': '#22c55e',
            'icon': 'piggy-bank',
            'budget_amount': 20000.0,
            'monthly_limit': 10000.0,
            'initial_balance': 1000.0
        })
        self.assertEqual(res_b.status_code, 201)
        pocket_b = res_b.get_json()['data']['pocket']
        
        # 3. Transfer from Pocket A to Pocket B with PIN
        res_tx = self.client.post('/api/transactions/transfer', json={
            'from_pocket_id': pocket_a['id'],
            'to_pocket_id': pocket_b['id'],
            'amount': 500.0,
            'pin': '1234',
            'description': 'Move to savings'
        })
        self.assertEqual(res_tx.status_code, 201)
        
        # Verify balances
        p_a_updated = db.session.get(Pocket, pocket_a['id'])
        p_b_updated = db.session.get(Pocket, pocket_b['id'])
        self.assertEqual(p_a_updated.current_balance, 1500.0)
        self.assertEqual(p_b_updated.current_balance, 1500.0)

    # =========================================================================
    # 3. P2P SEND & MONEY REQUESTS
    # =========================================================================
    def test_p2p_money_transfer_and_requests(self):
        self.login_client(email="alice@pocketpay.app", password="SecurePass@123")
        
        # Alice sends ₹1,000 to Bob
        res_send = self.client.post('/api/wallet/send-money', json={
            'recipient': 'bob@pocketpay.app',
            'amount': 1000.0,
            'pin': '1234',
            'description': 'Dinner split'
        })
        self.assertIn(res_send.status_code, [200, 201])
        
        u1 = db.session.get(User, self.user1.id)
        u2 = db.session.get(User, self.user2.id)
        self.assertEqual(u1.wallet_balance, 9000.0)
        self.assertEqual(u2.wallet_balance, 6000.0)
        
        # Bob requests ₹300 from Alice
        self.login_client(email="bob@pocketpay.app", password="SecurePass@123")
        res_req = self.client.post('/api/wallet/request-money', json={
            'target': 'alice@pocketpay.app',
            'amount': 300.0,
            'note': 'Movie ticket'
        })
        self.assertEqual(res_req.status_code, 201)
        req_id = res_req.get_json()['data']['request']['id']
        
        # Alice pays the request
        self.login_client(email="alice@pocketpay.app", password="SecurePass@123")
        res_pay = self.client.post(f'/api/wallet/requests/{req_id}/pay', json={
            'pin': '1234'
        })
        self.assertEqual(res_pay.status_code, 200)
        
        u1_final = db.session.get(User, self.user1.id)
        u2_final = db.session.get(User, self.user2.id)
        self.assertEqual(u1_final.wallet_balance, 8700.0)
        self.assertEqual(u2_final.wallet_balance, 6300.0)

    # =========================================================================
    # 4. BANK IMPS / NEFT SANDBOX PAYOUT
    # =========================================================================
    def test_bank_transfer_sandbox_payout(self):
        self.login_client(email="alice@pocketpay.app", password="SecurePass@123")
        
        res_payout = self.client.post('/api/payouts/transfer-to-bank', json={
            'account_number': '123456789012',
            'ifsc_code': 'HDFC0001234',
            'beneficiary_name': 'Alice Personal Account',
            'bank_name': 'HDFC Bank',
            'amount': 2500.0,
            'pin': '1234'
        })
        payout_data = res_payout.get_json()['data']['payout']
        self.assertEqual(str(payout_data['status']).lower(), 'success')
        self.assertTrue(bool(payout_data['utr']))
        
        u1 = db.session.get(User, self.user1.id)
        self.assertEqual(u1.wallet_balance, 7500.0)

    # =========================================================================
    # 5. SAVINGS GOALS (Phase 11)
    # =========================================================================
    def test_savings_goals_crud_and_deposits(self):
        self.login_client(email="alice@pocketpay.app", password="SecurePass@123")
        
        # 1. Create Goal
        res_goal = self.client.post('/api/analytics/goals', json={
            'name': 'New MacBook Pro',
            'target_amount': 150000.0,
            'category': 'Tech & Gadgets'
        })
        self.assertEqual(res_goal.status_code, 201)
        goal_id = res_goal.get_json()['data']['goal']['id']
        
        # 2. Deposit into Goal
        res_dep = self.client.post(f'/api/analytics/goals/{goal_id}/deposit', json={
            'amount': 2000.0,
            'source': 'wallet'
        })
        self.assertEqual(res_dep.status_code, 200)
        goal_data = res_dep.get_json()['data']['goal']
        self.assertEqual(goal_data['current_amount'], 2000.0)
        
        # 3. Withdraw from Goal
        res_wth = self.client.post(f'/api/analytics/goals/{goal_id}/withdraw', json={
            'amount': 500.0
        })
        self.assertEqual(res_wth.status_code, 200)
        self.assertEqual(res_wth.get_json()['data']['goal']['current_amount'], 1500.0)
        
        # 4. List Goals
        res_list = self.client.get('/api/analytics/goals')
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(res_list.get_json()['data']['total_count'], 1)

    # =========================================================================
    # 6. DEMO PREMIUM UPGRADE (Phase 14)
    # =========================================================================
    def test_demo_premium_upgrade(self):
        self.login_client(email="alice@pocketpay.app", password="SecurePass@123")
        
        # Check initial tier
        u = db.session.get(User, self.user1.id)
        self.assertFalse(u.is_premium)
        
        # Upgrade to demo premium
        res = self.client.post('/auth/upgrade-premium', json={'plan': 'annual'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['data']['is_premium'])
        
        u_updated = db.session.get(User, self.user1.id)
        self.assertTrue(u_updated.is_premium)

    # =========================================================================
    # 7. CONVERSATIONAL AI ASSISTANT (Phases 16, 17, 18)
    # =========================================================================
    def test_ai_assistant_intent_understanding(self):
        self.login_client(email="alice@pocketpay.app", password="SecurePass@123")
        
        queries = [
            ("What's my balance?", "Total Net Worth"),
            ("How much money do I have?", "Total Net Worth"),
            ("Show my pockets", "Smart Pockets"),
            ("What did I spend this month?", "Spending"),
            ("Show my recent transactions", "Recent Transactions"),
            ("Show my savings goals", "Savings Goals"),
            ("How does TOTP 2FA work?", "Multi-Layer Security"),
            ("What is Premium?", "PocketPay Pro"),
            ("How do I create a pocket?", "Creating a Smart Pocket"),
            ("Send ₹500 to Rahul", "Transfer Preparation")
        ]
        
        for q, expected_snippet in queries:
            res = self.client.post('/api/assistant/ask', json={'query': q, 'route': 'dashboard'})
            self.assertEqual(res.status_code, 200, f"Query failed: {q}")
            data = res.get_json()['data']
            combined_text = (data.get('title', '') + ' ' + data.get('message', ''))
            self.assertIn(expected_snippet, combined_text, f"Expected '{expected_snippet}' in response for query '{q}'")

    # =========================================================================
    # 8. ADMIN CONTROL & AUTHORIZATION GUARDS (Phase 15)
    # =========================================================================
    def test_admin_access_control(self):
        # 1. Normal user cannot access admin dashboard -> 403
        self.login_client(email="alice@pocketpay.app", password="SecurePass@123")
        res_user = self.client.get('/admin/dashboard')
        self.assertEqual(res_user.status_code, 403)
        
        # 2. Admin logs in with valid credentials
        res_admin = self.client.post('/admin/login', json={
            'email': 'admin@pocketpay.app',
            'password': 'Admin@PocketPay2026'
        })
        self.assertEqual(res_admin.status_code, 200)
        
        # 3. Admin dashboard loads
        res_dash = self.client.get('/admin/dashboard')
        self.assertEqual(res_dash.status_code, 200)

    # =========================================================================
    # 9. PERMANENT ACCOUNT DELETION & RE-REGISTRATION (Phase 4)
    # =========================================================================
    @patch('app.utils.email_service.send_email_async')
    def test_account_deletion_and_reregistration(self, mock_email):
        mock_email.return_value = True
        
        # 1. Register Charlie
        res_reg = self.client.post('/auth/register', json={
            'full_name': 'Charlie Test',
            'email': 'charlie@pocketpay.app',
            'phone': '9876543299',
            'password': 'Password@123',
            'password_confirm': 'Password@123'
        })
        self.assertEqual(res_reg.status_code, 201)
        
        user_c = User.query.filter_by(email='charlie@pocketpay.app').first()
        user_c.email_verified = True
        user_c.wallet_balance = 0.0
        db.session.commit()
        
        # 2. Login as Charlie
        self.login_client(email='charlie@pocketpay.app', password='Password@123')
        
        # 3. Delete account
        res_del = self.client.post('/auth/delete-account', json={'password': 'Password@123'})
        self.assertEqual(res_del.status_code, 200)
        
        # 4. Re-register with same email
        res_rereg = self.client.post('/auth/register', json={
            'full_name': 'Charlie New',
            'email': 'charlie@pocketpay.app',
            'phone': '9876543299',
            'password': 'NewPassword@123',
            'password_confirm': 'NewPassword@123'
        })
        self.assertEqual(res_rereg.status_code, 201)

    # =========================================================================
    # 10. TELEGRAM BOT NLP & COMMANDS (Phase 19)
    # =========================================================================
    @patch('app.telegram.service.TelegramService.send_message')
    def test_telegram_nlp_and_commands(self, mock_send):
        mock_send.return_value = {'ok': True, 'result': {'message_id': 1}}
        session = SessionManager.get_or_create(999999, username="testtelegram")
        session.link_user(self.user1)
        
        # Test natural language question on Telegram
        msg = {
            'chat': {'id': 123456},
            'from': {'id': 999999, 'username': 'testtelegram', 'first_name': 'Alice'},
            'text': 'How much money do I have?'
        }
        TelegramHandler.handle_message(msg)
        self.assertTrue(mock_send.called)
        
        # Verify response text passed to Telegram contains balance
        call_args = mock_send.call_args[0]
        self.assertIn("Total Net Worth", call_args[1])


if __name__ == '__main__':
    unittest.main()
