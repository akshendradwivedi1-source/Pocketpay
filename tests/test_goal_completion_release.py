"""
Unit and integration tests for Goal Completion and Fund Release to Available Balance (unittest).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['FLASK_CONFIG'] = 'testing'

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.pocket import Pocket
from app.models.goal import SavingsGoal
from app.models.transaction import Transaction


class TestGoalCompletionRelease(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config.update({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'WTF_CSRF_ENABLED': False,
            'SECRET_KEY': 'test-secret-key-goals'
        })
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create user
        self.user = User(
            full_name='Goal Winner',
            email='winner@example.com',
            wallet_balance=1000.0,
            is_active=True,
            security_setup_completed=True
        )
        self.user.set_password('Secret123!')
        self.user.set_transaction_pin('1234')
        db.session.add(self.user)
        db.session.commit()
        self.user_id = self.user.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login_user(self, user):
        return self.client.post('/auth/login', json={
            'email': user.email,
            'password': 'Secret123!'
        })

    def test_savings_goal_model_release_to_wallet(self):
        user = db.session.get(User, self.user_id)
        self.assertEqual(user.wallet_balance, 1000.0)

        goal = SavingsGoal(
            user_id=user.id,
            name='Laptop Fund',
            target_amount=500.0,
            current_amount=500.0,
            is_completed=False
        )
        db.session.add(goal)
        db.session.commit()

        # Call release_to_wallet
        released = goal.release_to_wallet(user)
        self.assertEqual(released, 500.0)
        self.assertTrue(goal.is_completed)
        self.assertEqual(goal.current_amount, 0.0)
        self.assertEqual(goal.released_amount, 500.0)
        self.assertIsNotNone(goal.released_at)
        self.assertEqual(user.wallet_balance, 1500.0)

    def test_goal_deposit_auto_release_flow(self):
        # Log in
        login_res = self.login_user(self.user)
        self.assertEqual(login_res.status_code, 200)

        # 1. Create a goal with target 500
        res = self.client.post('/api/analytics/goals', json={
            'name': 'New Phone',
            'target_amount': 500.0,
            'category': 'Electronics',
            'target_date': '2026-12-31'
        })
        self.assertEqual(res.status_code, 201)
        goal_data = res.get_json()['data']['goal']
        goal_id = goal_data['id']

        # 2. Deposit 200 (partial, not completed)
        res_dep1 = self.client.post(f'/api/analytics/goals/{goal_id}/deposit', json={
            'amount': 200.0,
            'source': 'wallet'
        })
        self.assertEqual(res_dep1.status_code, 200)
        d1 = res_dep1.get_json()
        self.assertTrue(d1['success'])
        self.assertFalse(d1['data']['goal_completed'])
        self.assertEqual(d1['data']['goal']['current_amount'], 200.0)

        # User wallet should now be 800 (1000 - 200)
        u = db.session.get(User, self.user_id)
        self.assertEqual(u.wallet_balance, 800.0)

        # 3. Deposit 300 to reach target of 500
        res_dep2 = self.client.post(f'/api/analytics/goals/{goal_id}/deposit', json={
            'amount': 300.0,
            'source': 'wallet'
        })
        self.assertEqual(res_dep2.status_code, 200)
        d2 = res_dep2.get_json()
        self.assertTrue(d2['success'])
        self.assertTrue(d2['data']['goal_completed'])
        self.assertEqual(d2['data']['released_amount'], 500.0)

        # 4. Check database: funds released back into wallet_balance!
        u = db.session.get(User, self.user_id)
        # Starting 1000:
        # - 200 first deposit = 800
        # - 300 second deposit = 500
        # + 500 goal release = 1000
        self.assertEqual(u.wallet_balance, 1000.0)

        g = db.session.get(SavingsGoal, goal_id)
        self.assertTrue(g.is_completed)
        self.assertEqual(g.current_amount, 0.0)
        self.assertEqual(g.released_amount, 500.0)
        self.assertIsNotNone(g.released_at)

        # Verify audit transaction created
        tx = Transaction.query.filter_by(user_id=u.id, type='income', category='Goal Achievement').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 500.0)

    def test_goal_explicit_release_endpoint(self):
        # Log in
        login_res = self.login_user(self.user)
        self.assertEqual(login_res.status_code, 200)

        # Create completed goal with unreleased funds in current_amount
        goal = SavingsGoal(
            user_id=self.user_id,
            name='Emergency Fund',
            target_amount=400.0,
            current_amount=400.0,
            is_completed=True
        )
        db.session.add(goal)
        db.session.commit()
        goal_id = goal.id

        # Call explicit release endpoint
        res = self.client.post(f'/api/analytics/goals/{goal_id}/release')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['released_amount'], 400.0)

        u = db.session.get(User, self.user_id)
        # 1000 initial + 400 released = 1400
        self.assertEqual(u.wallet_balance, 1400.0)
        g = db.session.get(SavingsGoal, goal_id)
        self.assertEqual(g.current_amount, 0.0)
        self.assertEqual(g.released_amount, 400.0)

    def test_pocket_goal_release_endpoint(self):
        # Log in
        login_res = self.login_user(self.user)
        self.assertEqual(login_res.status_code, 200)

        # Create locked pocket with goal met
        pocket = Pocket(
            user_id=self.user_id,
            name='Travel Pocket',
            current_balance=750.0,
            is_locked=True,
            locked_goal_amount=700.0
        )
        db.session.add(pocket)
        db.session.commit()
        pocket_id = pocket.id

        # Call release-goal endpoint
        res = self.client.post(f'/api/pockets/{pocket_id}/release-goal')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['released_amount'], 750.0)

        u = db.session.get(User, self.user_id)
        # 1000 initial + 750 released = 1750
        self.assertEqual(u.wallet_balance, 1750.0)
        p = db.session.get(Pocket, pocket_id)
        self.assertEqual(p.current_balance, 0.0)
        self.assertFalse(p.is_locked)
        self.assertFalse(p.is_currently_locked())


if __name__ == '__main__':
    unittest.main()
