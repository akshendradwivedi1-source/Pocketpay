"""
PocketPay - TravelEase QR Compatibility & Integration Test Suite
Validates all 15 test requirements specified by the user:
TEST 1: Existing PocketPay QR -> must continue working.
TEST 2: Valid TravelEase flight QR -> recognized.
TEST 3: Valid TravelEase train QR -> recognized.
TEST 4: Valid TravelEase bus QR -> recognized.
TEST 5: Valid TravelEase cab QR -> recognized.
TEST 6: Valid TravelEase hotel QR -> recognized.
TEST 7: Valid TravelEase package QR -> recognized.
TEST 8: Malformed QR -> reject.
TEST 9: Unknown merchant -> reject.
TEST 10: Modified amount -> reject or verify against trusted booking data.
TEST 11: Already-paid booking -> do not charge again.
TEST 12: Double-click confirmation -> only one transaction.
TEST 13: Insufficient PocketPay balance -> payment rejected safely.
TEST 14: Expired/invalid booking -> payment rejected.
TEST 15: TravelEase API unavailable -> show proper error and do not create a false successful payment.
"""

import unittest
import json
from datetime import datetime, timedelta
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.payment_request import PaymentRequest
from app.utils.helpers import build_qr_user_url, build_qr_pocket_url, build_qr_tx_url


class TestTravelEaseQrIntegration(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Create Test User with 5000.0 balance
        self.user = User(
            email='traveller@pocketpay.app',
            full_name='Aarav Sharma',
            wallet_balance=5000.0,
            virtual_wallet_id='PPW999888777666',
            virtual_upi_id='aarav@pocketpay',
            is_active=True
        )
        self.user.set_password('TestPass123!')
        self.user.set_transaction_pin('1234')
        db.session.add(self.user)

        # Create Alice for P2P test
        self.alice = User(
            email='alice@pocketpay.app',
            full_name='Alice Wonderland',
            wallet_balance=1000.0,
            virtual_wallet_id='PPWALICE999',
            virtual_upi_id='alice@pocketpay',
            is_active=True
        )
        self.alice.set_password('AlicePass123!')
        db.session.add(self.alice)
        db.session.commit()

        # Login as test user
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user.id)
            sess['_fresh'] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # =========================================================================
    # TEST 1: Existing PocketPay QR must continue working
    # =========================================================================
    def test_01_existing_pocketpay_qr_continue_working(self):
        # 1. User Profile QR
        user_qr_url = build_qr_user_url(self.alice)
        r_user = self.client.post('/qr/api/resolve', json={'content': user_qr_url})
        self.assertEqual(r_user.status_code, 200)
        self.assertEqual(r_user.get_json()['type'], 'user')
        self.assertEqual(r_user.get_json()['user']['virtual_wallet_id'], 'PPWALICE999')

        # 2. Pocket QR
        pocket = Pocket(user_id=self.user.id, name='Vacation', current_balance=500.0, budget_amount=1000.0)
        db.session.add(pocket)
        db.session.commit()
        pocket_url = build_qr_pocket_url(pocket)
        r_pocket = self.client.post('/qr/api/resolve', json={'content': pocket_url})
        self.assertEqual(r_pocket.status_code, 200)
        self.assertEqual(r_pocket.get_json()['type'], 'pocket')

        # 3. Transaction Receipt QR
        tx = Transaction(
            transaction_id='PPTX_EXISTING_001',
            user_id=self.user.id,
            type='expense',
            amount=250.0,
            status='completed',
            merchant='Cafe Coffee',
            payment_method='wallet'
        )
        db.session.add(tx)
        db.session.commit()
        tx_url = build_qr_tx_url(tx)
        r_tx = self.client.post('/qr/api/resolve', json={'content': tx_url})
        self.assertEqual(r_tx.status_code, 200)
        self.assertEqual(r_tx.get_json()['type'], 'transaction')

        # 4. Standard UPI URI
        upi_uri = "upi://pay?pa=shopkeeper@upi&pn=GroceryStore&am=150.00&cu=INR"
        r_upi = self.client.post('/qr/api/resolve', json={'content': upi_uri})
        self.assertEqual(r_upi.status_code, 200)
        self.assertEqual(r_upi.get_json()['type'], 'upi')

    # =========================================================================
    # TEST 2 - TEST 7: All 6 TravelEase Booking Types Recognized
    # =========================================================================
    def _create_and_resolve_travelease_qr(self, booking_type, booking_id, amount=1200.0):
        # Pre-seed verified PaymentRequest in PocketPay as created by TravelEase
        pr = PaymentRequest(
            request_id=f"PPR_{booking_id}",
            merchant='TravelEase',
            booking_id=booking_id,
            booking_type=booking_type,
            reference=f"REF_{booking_id}",
            version='1',
            amount=amount,
            currency='INR',
            description=f'TravelEase {booking_type.capitalize()} Booking #{booking_id}',
            status='pending',
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        db.session.add(pr)
        db.session.commit()

        qr_payload = json.dumps({
            "type": "travelease_payment",
            "version": "1",
            "merchant": "TravelEase",
            "booking_id": booking_id,
            "booking_type": booking_type,
            "amount": amount,
            "currency": "INR",
            "reference": f"REF_{booking_id}",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

        # Test both /qr/api/resolve and /api/v1/payments/resolve-request
        res1 = self.client.post('/qr/api/resolve', json={'content': qr_payload})
        self.assertEqual(res1.status_code, 200)
        d1 = res1.get_json()
        self.assertTrue(d1.get('success'))
        pr_data = d1.get('payment_request')
        self.assertEqual(pr_data['merchant'], 'TravelEase')
        self.assertEqual(pr_data['booking_id'], booking_id)
        self.assertEqual(pr_data['booking_type'], booking_type)
        self.assertEqual(pr_data['amount'], amount)

        res2 = self.client.post('/api/v1/payments/resolve-request', json={'code': qr_payload})
        self.assertEqual(res2.status_code, 200)
        d2 = res2.get_json()
        self.assertTrue(d2.get('valid'))
        self.assertEqual(d2['booking_type'], booking_type)
        self.assertEqual(d2['amount'], amount)
        return pr_data

    def test_02_valid_travelease_flight_qr(self):
        pr = self._create_and_resolve_travelease_qr('flight', 'TRV_FLIGHT_101', 3500.0)
        self.assertEqual(pr['booking_type'], 'flight')

    def test_03_valid_travelease_train_qr(self):
        pr = self._create_and_resolve_travelease_qr('train', 'TRV_TRAIN_202', 850.0)
        self.assertEqual(pr['booking_type'], 'train')

    def test_04_valid_travelease_bus_qr(self):
        pr = self._create_and_resolve_travelease_qr('bus', 'TRV_BUS_303', 600.0)
        self.assertEqual(pr['booking_type'], 'bus')

    def test_05_valid_travelease_cab_qr(self):
        pr = self._create_and_resolve_travelease_qr('cab', 'TRV_CAB_404', 450.0)
        self.assertEqual(pr['booking_type'], 'cab')

    def test_06_valid_travelease_hotel_qr(self):
        pr = self._create_and_resolve_travelease_qr('hotel', 'TRV_HOTEL_505', 2200.0)
        self.assertEqual(pr['booking_type'], 'hotel')

    def test_07_valid_travelease_package_qr(self):
        pr = self._create_and_resolve_travelease_qr('package', 'TRV_PKG_606', 4999.0)
        self.assertEqual(pr['booking_type'], 'package')

    # =========================================================================
    # TEST 8: Malformed QR -> reject
    # =========================================================================
    def test_08_malformed_qr_rejected(self):
        # 1. Broken JSON syntax
        r1 = self.client.post('/qr/api/resolve', json={'content': '{invalid json here!'})
        self.assertEqual(r1.status_code, 400)
        self.assertFalse(r1.get_json()['success'])

        # 2. Unsupported QR version
        bad_ver = json.dumps({
            "type": "travelease_payment",
            "version": "99.0",
            "merchant": "TravelEase",
            "booking_id": "TRV_TEST",
            "booking_type": "flight",
            "amount": 100.0
        })
        r2 = self.client.post('/qr/api/resolve', json={'content': bad_ver})
        self.assertEqual(r2.status_code, 400)
        self.assertIn('version', r2.get_json()['error'].lower())

    # =========================================================================
    # TEST 9: Unknown merchant -> reject
    # =========================================================================
    def test_09_unknown_merchant_rejected(self):
        bad_merchant = json.dumps({
            "type": "travelease_payment",
            "version": "1",
            "merchant": "FakeMerchantScam",
            "booking_id": "SCAM123",
            "booking_type": "flight",
            "amount": 500.0
        })
        r = self.client.post('/qr/api/resolve', json={'content': bad_merchant})
        self.assertEqual(r.status_code, 400)
        self.assertIn('merchant', r.get_json()['error'].lower())

    # =========================================================================
    # TEST 10: Modified/tampered amount -> reject or verify against trusted DB
    # =========================================================================
    def test_10_modified_amount_rejected_or_verified(self):
        # Seed authentic request for 1500.00
        pr = PaymentRequest(
            request_id="PPR_TAMPER_001",
            merchant='TravelEase',
            booking_id='TRV_TAMPER_001',
            booking_type='flight',
            amount=1500.0,
            currency='INR',
            status='pending',
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        db.session.add(pr)
        db.session.commit()

        # Attacker tries to alter amount to 1.00 in the QR
        tampered_qr = json.dumps({
            "type": "travelease_payment",
            "version": "1",
            "merchant": "TravelEase",
            "booking_id": "TRV_TAMPER_001",
            "booking_type": "flight",
            "amount": 1.0,  # TAMPERED
            "currency": "INR",
            "reference": "REF_TAMPER"
        })

        # PocketPay resolver rejects tampered amount
        r_resolve = self.client.post('/qr/api/resolve', json={'content': tampered_qr})
        self.assertEqual(r_resolve.status_code, 400)
        self.assertIn('mismatch', r_resolve.get_json()['error'].lower())

        # Zero or negative amount is also rejected
        zero_qr = json.dumps({
            "type": "travelease_payment",
            "version": "1",
            "merchant": "TravelEase",
            "booking_id": "TRV_TAMPER_001",
            "amount": -50.0
        })
        r_zero = self.client.post('/qr/api/resolve', json={'content': zero_qr})
        self.assertEqual(r_zero.status_code, 400)

    # =========================================================================
    # TEST 11: Already-paid booking -> do not charge again
    # =========================================================================
    def test_11_already_paid_booking_do_not_charge_again(self):
        # Create already paid request
        pr = PaymentRequest(
            request_id="PPR_PAID_001",
            merchant='TravelEase',
            booking_id='TRV_PAID_001',
            booking_type='hotel',
            amount=1200.0,
            currency='INR',
            status='paid',
            transaction_id='PPTX_ALREADY_PAID',
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        db.session.add(pr)

        # Existing completed transaction
        tx = Transaction(
            transaction_id='PPTX_ALREADY_PAID',
            user_id=self.user.id,
            type='expense',
            amount=1200.0,
            status='completed',
            merchant='TravelEase',
            reference_id='TRV_PAID_001',
            booking_type='hotel'
        )
        db.session.add(tx)
        db.session.commit()

        qr_payload = json.dumps({
            "type": "travelease_payment",
            "version": "1",
            "merchant": "TravelEase",
            "booking_id": "TRV_PAID_001",
            "booking_type": "hotel",
            "amount": 1200.0,
            "currency": "INR"
        })

        # QR resolver rejects with "Payment already completed"
        r_res = self.client.post('/qr/api/resolve', json={'content': qr_payload})
        self.assertEqual(r_res.status_code, 400)
        self.assertIn('already', r_res.get_json()['error'].lower())

        # Direct payment attempt rejected with already completed
        r_pay = self.client.post('/api/v1/payments/pay-request', json={
            'payment_request_id': 'PPR_PAID_001',
            'otp': '123456',
            'identifier': self.user.virtual_wallet_id
        })
        self.assertEqual(r_pay.status_code, 200)
        self.assertTrue(r_pay.get_json().get('already_processed'))
        self.assertIn('already', r_pay.get_json()['message'].lower())

        # Verify wallet was NOT debited
        db.session.refresh(self.user)
        self.assertEqual(float(self.user.wallet_balance), 5000.0)

    # =========================================================================
    # TEST 12: Double-click confirmation -> only one transaction
    # =========================================================================
    def test_12_double_click_confirmation_only_one_transaction(self):
        pr = PaymentRequest(
            request_id="PPR_DOUBLE_001",
            merchant='TravelEase',
            booking_id='TRV_DOUBLE_001',
            booking_type='flight',
            amount=1000.0,
            currency='INR',
            status='pending',
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        db.session.add(pr)
        db.session.commit()

        # Generate OTP
        otp_code = self.user.generate_otp(for_email=True)
        db.session.commit()

        # First click
        r1 = self.client.post('/api/v1/payments/pay-request', json={
            'payment_request_id': 'PPR_DOUBLE_001',
            'otp': otp_code,
            'identifier': self.user.virtual_wallet_id
        })
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.get_json()['status'], 'SUCCESS')
        txn_id = r1.get_json()['transaction_id']

        # Rapid second click (replay / double-click)
        r2 = self.client.post('/api/v1/payments/pay-request', json={
            'payment_request_id': 'PPR_DOUBLE_001',
            'otp': otp_code,
            'identifier': self.user.virtual_wallet_id
        })
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.get_json().get('already_processed'))
        self.assertEqual(r2.get_json()['transaction_id'], txn_id)

        # Confirm exactly ONE transaction in DB
        tx_count = Transaction.query.filter_by(reference_id='TRV_DOUBLE_001', merchant='TravelEase').count()
        self.assertEqual(tx_count, 1)

        # Balance debited exactly once (5000 - 1000 = 4000)
        db.session.refresh(self.user)
        self.assertEqual(float(self.user.wallet_balance), 4000.0)

    # =========================================================================
    # TEST 13: Insufficient PocketPay balance -> payment rejected safely
    # =========================================================================
    def test_13_insufficient_pocketpay_balance_rejected_safely(self):
        # Booking costs 8000.0, user only has 5000.0
        pr = PaymentRequest(
            request_id="PPR_OVERDRAFT_001",
            merchant='TravelEase',
            booking_id='TRV_EXPENSIVE_001',
            booking_type='package',
            amount=8000.0,
            currency='INR',
            status='pending',
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        db.session.add(pr)
        db.session.commit()

        otp_code = self.user.generate_otp(for_email=True)
        db.session.commit()

        r_pay = self.client.post('/api/v1/payments/pay-request', json={
            'payment_request_id': 'PPR_OVERDRAFT_001',
            'otp': otp_code,
            'identifier': self.user.virtual_wallet_id
        })
        self.assertEqual(r_pay.status_code, 402)
        d = r_pay.get_json()
        self.assertEqual(d['error'], 'INSUFFICIENT_BALANCE')
        self.assertEqual(d['available_balance'], 5000.0)
        self.assertEqual(d['required_amount'], 8000.0)
        self.assertEqual(d['shortfall'], 3000.0)

        # Balance remains untouched
        db.session.refresh(self.user)
        self.assertEqual(float(self.user.wallet_balance), 5000.0)

    # =========================================================================
    # TEST 14: Expired / invalid booking -> payment rejected
    # =========================================================================
    def test_14_expired_invalid_booking_rejected(self):
        # 1. Expired PaymentRequest
        pr = PaymentRequest(
            request_id="PPR_EXPIRED_001",
            merchant='TravelEase',
            booking_id='TRV_EXPIRED_001',
            booking_type='train',
            amount=500.0,
            currency='INR',
            status='pending',
            expires_at=datetime.utcnow() - timedelta(minutes=5)  # Already expired
        )
        db.session.add(pr)
        db.session.commit()

        qr_payload = json.dumps({
            "type": "travelease_payment",
            "version": "1",
            "merchant": "TravelEase",
            "booking_id": "TRV_EXPIRED_001",
            "booking_type": "train",
            "amount": 500.0,
            "currency": "INR",
            "request_id": "PPR_EXPIRED_001"
        })

        r_res = self.client.post('/qr/api/resolve', json={'content': qr_payload})
        self.assertEqual(r_res.status_code, 400)
        self.assertIn('expired', r_res.get_json()['error'].lower())

    # =========================================================================
    # TEST 15: TravelEase API unavailable -> proper error, no fake success
    # =========================================================================
    def test_15_travelease_api_unavailable_handled_properly(self):
        # Payload for an unregistered booking when TravelEase backend is completely offline
        offline_qr = json.dumps({
            "type": "travelease_payment",
            "version": "1",
            "merchant": "TravelEase",
            "booking_id": "TRV_UNREGISTERED_999",
            "booking_type": "flight",
            "amount": 1200.0,
            "currency": "INR"
        })

        # Mock requests.get to simulate connection error to TravelEase backend
        import requests
        with patch('requests.get', side_effect=requests.ConnectionError("Connection refused")):
            r = self.client.post('/qr/api/resolve', json={'content': offline_qr})
            # Must reject safely (503 or 400 error, never a fake 200 success)
            self.assertIn(r.status_code, (400, 503))
            self.assertFalse(r.get_json()['success'])
            self.assertIn('unavailable', r.get_json()['error'].lower() + r.get_json().get('message', '').lower())


if __name__ == '__main__':
    unittest.main()
