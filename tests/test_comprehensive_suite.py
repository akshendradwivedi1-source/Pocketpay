import unittest
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app import create_app, db
from app.models.user import User
from app.models.payment_request import PaymentRequest
from app.models.transaction import Transaction
from app.services.travelease_service import TravelEaseService
from app.services.premium_service import PremiumService
from app.utils.email_service import send_otp_email_sync

class ComprehensivePocketPayIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Seed test user
        self.user = User(
            full_name='Comprehensive User',
            email='testuser@example.com',
            phone='9876543211',
            virtual_wallet_id='PPW9988776655',
            virtual_upi_id='compuser@pocketpay',
            wallet_balance=15000.0,
            is_active=True
        )
        self.user.set_password('Password123!')
        self.user.set_transaction_pin('1234')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # =========================================================================
    # 1. TEST ALL 6 TRAVELEASE BOOKING TYPES RESOLUTION & INTEGRATION
    # =========================================================================
    def test_all_six_travelease_booking_types(self):
        booking_types = ['flight', 'train', 'bus', 'cab', 'hotel', 'package']
        
        for idx, b_type in enumerate(booking_types, start=101):
            booking_id = f"TRV_COMP_{b_type.upper()}_{idx}"
            amount = 1200.0 + idx

            pr = PaymentRequest(
                request_id=f"PPR_{booking_id}",
                merchant='TravelEase',
                booking_id=booking_id,
                booking_type=b_type,
                reference=f"REF_{booking_id}",
                version='1',
                amount=amount,
                currency='INR',
                description=f'TravelEase {b_type.capitalize()} Booking #{booking_id}',
                status='pending',
                expires_at=datetime.utcnow() + timedelta(minutes=30)
            )
            db.session.add(pr)
            db.session.commit()

            # Authoritative verification via TravelEaseService
            with patch.object(TravelEaseService, 'verify_booking') as mock_verify:
                mock_verify.return_value = {
                    'valid': True,
                    'booking_id': booking_id,
                    'amount': amount,
                    'status': 'PENDING',
                    'booking_type': b_type,
                    'source': 'authoritative_test'
                }

                # A. Resolve via JSON QR payload (standard TravelEase QR)
                qr_payload = json.dumps({
                    "type": "travelease_payment",
                    "version": "1",
                    "merchant": "TravelEase",
                    "booking_id": booking_id,
                    "booking_type": b_type,
                    "amount": amount,
                    "currency": "INR",
                    "reference": f"REF_{booking_id}",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
                res = self.client.post('/qr/api/resolve', json={'content': qr_payload})
                self.assertEqual(res.status_code, 200, f"Failed resolving QR for {b_type}")
                data = res.get_json()
                self.assertTrue(data.get('success'))
                self.assertEqual(data['payment_request']['booking_type'], b_type)
                self.assertEqual(data['payment_request']['amount'], amount)
                self.assertEqual(data['payment_request']['booking_id'], booking_id)

                # B. Resolve via direct booking URL payload
                url_payload = f"http://127.0.0.1:5000/booking/payment/{booking_id}"
                res_url = self.client.post('/qr/api/resolve', json={'content': url_payload})
                self.assertEqual(res_url.status_code, 200)
                data_url = res_url.get_json()
                self.assertTrue(data_url.get('success'))
                self.assertEqual(data_url['payment_request']['booking_id'], booking_id)

    # =========================================================================
    # 2. RAZORPAY SUBSCRIPTION INTEGRATION & CRYPTOGRAPHIC VERIFICATION
    # =========================================================================
    @patch('requests.post')
    def test_razorpay_order_creation_and_verification(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'order_rzp_test_mock_12345',
            'entity': 'order',
            'amount': 9900,
            'currency': 'INR',
            'receipt': 'rcpt_sub_123',
            'status': 'created'
        }
        mock_post.return_value = mock_response

        # Step A: Order creation
        order_res = PremiumService.create_order(
            user=self.user,
            plan_id='monthly'
        )
        self.assertEqual(order_res['order_id'], 'order_rzp_test_mock_12345')
        self.assertFalse(order_res['is_sandbox'])
        self.assertEqual(order_res['key_id'], 'rzp_test_THKr80oWuqIomZ')
        self.assertEqual(order_res['amount'], 99.0)

        # Step B: Cryptographic signature verification
        secret = 'oh2x8FnVlFBq6ygO7EJ2fOmn'
        payment_id = 'pay_test_987654321'
        message = f"order_rzp_test_mock_12345|{payment_id}"
        valid_signature = hmac.new(
            secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Verify valid payment
        verify_res = PremiumService.verify_payment(
            user=self.user,
            order_id='order_rzp_test_mock_12345',
            payment_id=payment_id,
            signature=valid_signature
        )
        self.assertTrue(verify_res['success'])
        self.assertTrue(self.user.is_premium)
        self.assertEqual(self.user.plan_id, 'monthly')

        # Check Transaction ledger entry
        tx = Transaction.query.filter_by(
            user_id=self.user.id,
            category='Subscriptions'
        ).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.status, 'completed')
        self.assertEqual(tx.amount, 99.0)

        # Step C: Replay attack prevention / Idempotency
        replay_res = PremiumService.verify_payment(
            user=self.user,
            order_id='order_rzp_test_mock_12345',
            payment_id=payment_id,
            signature=valid_signature
        )
        self.assertTrue(replay_res['success'])
        self.assertTrue(replay_res.get('already_active'))

        # Step D: Reject invalid/tampered signature
        bad_sig_res = PremiumService.verify_payment(
            user=self.user,
            order_id='order_rzp_test_mock_12345',
            payment_id='pay_tampered_id',
            signature='invalid_bad_signature_hash'
        )
        self.assertFalse(bad_sig_res['success'])
        self.assertIn('Invalid payment signature', bad_sig_res.get('error', ''))

    # =========================================================================
    # 3. POCKETPAY ID LOOKUP & SYNCHRONOUS SMTP EMAIL DISPATCH
    # =========================================================================
    def test_pocketpay_id_lookup_variations(self):
        from app.blueprints.partner_payments import find_pocketpay_user
        
        # Exact PPW uppercase
        self.assertEqual(find_pocketpay_user('PPW9988776655'), self.user)
        # Lowercase ppw
        self.assertEqual(find_pocketpay_user('ppw9988776655'), self.user)
        # With spaces
        self.assertEqual(find_pocketpay_user('  PPW9988776655  '), self.user)
        # UPI ID
        self.assertEqual(find_pocketpay_user('compuser@pocketpay'), self.user)
        # Email
        self.assertEqual(find_pocketpay_user('testuser@example.com'), self.user)
        # Non-existent user
        self.assertIsNone(find_pocketpay_user('PPW0000000000'))

    @patch('app.utils.email_service._send_via_smtp')
    def test_sync_smtp_email_delivery_success(self, mock_send):
        mock_send.return_value = (True, "Delivered via SMTP (smtp.gmail.com:587)")
        self.app.config['TESTING'] = False
        self.app.config['MAIL_USERNAME'] = 'akshendra.dwivedi1@gmail.com'
        try:
            success, msg = send_otp_email_sync(
                recipient_email='testuser@example.com',
                otp='654321',
                purpose='TravelEase Verification',
                user_name='Comprehensive User'
            )
            self.assertTrue(success)
            self.assertIn("Delivered via SMTP", msg)
            mock_send.assert_called_once()
        finally:
            self.app.config['TESTING'] = True

    @patch('app.utils.email_service._send_via_smtp')
    def test_sync_smtp_email_delivery_failure(self, mock_send):
        mock_send.return_value = (False, "SMTP Server connection timed out")
        self.app.config['TESTING'] = False
        self.app.config['MAIL_USERNAME'] = 'akshendra.dwivedi1@gmail.com'
        try:
            success, msg = send_otp_email_sync(
                recipient_email='testuser@example.com',
                otp='654321',
                purpose='TravelEase Verification',
                user_name='Comprehensive User'
            )
            self.assertFalse(success)
            self.assertIn("timed out", msg)
            mock_send.assert_called_once()
        finally:
            self.app.config['TESTING'] = True

if __name__ == '__main__':
    unittest.main()
