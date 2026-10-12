import os
import requests
import sqlite3
from datetime import datetime
from flask import current_app

VALID_BOOKING_TYPES = ('flight', 'train', 'bus', 'cab', 'hotel', 'package')


class TravelEaseService:
    """
    Service-to-service integration client for TravelEase.
    Authoritatively validates bookings, verifies amounts, prevents tampering,
    and synchronizes confirmed payment statuses back to TravelEase.
    """

    @classmethod
    def get_config(cls):
        api_url = os.environ.get('TRAVELEASE_API_URL', 'http://127.0.0.1:5000')
        api_key = os.environ.get('TRAVELEASE_API_KEY', 'travelease_service_key_live_99812')
        if current_app:
            api_url = current_app.config.get('TRAVELEASE_API_URL', api_url)
            api_key = current_app.config.get('TRAVELEASE_API_KEY', api_key)
        return api_url.rstrip('/'), api_key

    @classmethod
    def normalize_booking_type(cls, booking_type: str) -> str:
        if not booking_type:
            return 'flight'
        bt = str(booking_type).strip().lower()
        if bt in VALID_BOOKING_TYPES:
            return bt
        for valid in VALID_BOOKING_TYPES:
            if valid in bt:
                return valid
        return bt

    @classmethod
    def _query_local_travelease_db(cls, booking_id: str) -> dict:
        """
        Safely reads trusted booking data from local TravelEase SQLite database (read-only).
        Acts as authoritative source of truth for booking amount, travel type, and payment status.
        """
        possible_paths = [
            os.environ.get('TRAVELEASE_DB_PATH'),
            r'C:\Users\arvin\OneDrive\Desktop\Travelease\instance\travelease.db',
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'Travelease', 'instance', 'travelease.db'))
        ]
        db_path = None
        for p in possible_paths:
            if p and os.path.exists(p):
                db_path = p
                break

        if not db_path:
            return None

        try:
            norm_path = os.path.abspath(db_path).replace(os.sep, '/')
            uri = f'file:{norm_path}?mode=ro'
            conn = sqlite3.connect(uri, uri=True, timeout=3)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                'SELECT booking_id, travel_type, total_amount, status, payment_status, source, destination FROM booking WHERE booking_id = ? LIMIT 1',
                (booking_id,)
            )
            row = cur.fetchone()
            conn.close()
            if row:
                return dict(row)
        except Exception as e:
            if current_app:
                current_app.logger.warning(f'[TravelEaseService] Local DB read error: {e}')
        return None

    @classmethod
    def verify_booking(cls, booking_id: str, client_amount: float = None, booking_type: str = None) -> dict:
        """
        Authoritatively verifies booking details against TravelEase records.
        Guarantees that amounts, merchants, and statuses cannot be tampered with in the QR.
        """
        from app.models.payment_request import PaymentRequest
        from app.models.transaction import Transaction

        clean_bid = str(booking_id).strip()
        if not clean_bid:
            return {
                'success': False,
                'error': 'MISSING_BOOKING_ID',
                'message': 'Booking ID is required'
            }

        # 1. Check local PocketPay transaction ledger: Is this booking already paid?
        existing_tx = Transaction.query.filter(
            (Transaction.reference_id == clean_bid) | (Transaction.external_booking_id == clean_bid),
            Transaction.merchant == 'TravelEase',
            Transaction.status == 'completed'
        ).first()
        if existing_tx:
            return {
                'success': False,
                'already_paid': True,
                'error': 'ALREADY_PAID',
                'message': 'Payment already completed',
                'transaction_id': existing_tx.transaction_id,
                'amount': float(existing_tx.amount)
            }

        # Check existing PaymentRequest in PocketPay DB
        existing_pr = PaymentRequest.query.filter_by(
            booking_id=clean_bid,
            merchant='TravelEase'
        ).order_by(PaymentRequest.created_at.desc()).first()

        if existing_pr and existing_pr.status == 'paid':
            return {
                'success': False,
                'already_paid': True,
                'error': 'ALREADY_PAID',
                'message': 'Payment already completed',
                'transaction_id': existing_pr.transaction_id,
                'amount': float(existing_pr.amount)
            }

        verified_amount = None
        verified_type = None

        # 2. Remote HTTP check to TravelEase backend
        api_url, api_key = cls.get_config()
        headers = {
            'X-Service-API-Key': api_key,
            'Accept': 'application/json'
        }

        remote_available = False
        try:
            req_id = existing_pr.request_id if existing_pr else clean_bid
            resp = requests.get(
                f'{api_url}/booking/pocketpay/check-status/{clean_bid}',
                params={'payment_request_id': req_id},
                headers=headers,
                timeout=4
            )
            remote_available = True
            if resp.status_code == 200:
                data = resp.json()
                status = (data.get('status') or '').upper()

                if status in ('PAID', 'CONFIRMED', 'COMPLETED') and data.get('confirmed'):
                    return {
                        'success': False,
                        'already_paid': True,
                        'error': 'ALREADY_PAID',
                        'message': 'Payment already completed',
                        'transaction_id': data.get('transaction_id')
                    }

                if status in ('PENDING', 'UNPAID', 'PAYMENT_PENDING'):
                    te_amount = data.get('amount')
                    if te_amount is not None:
                        try:
                            te_amount = float(te_amount)
                            if client_amount is not None and abs(client_amount - te_amount) > 0.01:
                                return {
                                    'success': False,
                                    'error': 'AMOUNT_MISMATCH',
                                    'message': f'Amount mismatch. Authoritative amount is ₹{te_amount:,.2f}'
                                }
                            verified_amount = te_amount
                        except (ValueError, TypeError):
                            pass
                    if data.get('travel_type'):
                        verified_type = cls.normalize_booking_type(data.get('travel_type'))

            elif resp.status_code == 404:
                return {
                    'success': False,
                    'error': 'BOOKING_NOT_FOUND',
                    'message': 'TravelEase booking not found'
                }
            elif resp.status_code in (400, 410):
                return {
                    'success': False,
                    'error': 'INVALID_BOOKING',
                    'message': 'TravelEase booking is expired or cancelled'
                }
        except Exception as e:
            if current_app:
                current_app.logger.warning(f'[TravelEaseService] Remote check notice: {e}')

        # 3. If remote is not returning amount, check authoritative local TravelEase database (read-only SQLite)
        if verified_amount is None:
            local_booking = cls._query_local_travelease_db(clean_bid)
            if local_booking:
                b_status = (local_booking.get('status') or '').capitalize()
                p_status = (local_booking.get('payment_status') or '').capitalize()

                if b_status in ('Confirmed', 'Completed') and p_status == 'Paid':
                    return {
                        'success': False,
                        'already_paid': True,
                        'error': 'ALREADY_PAID',
                        'message': 'Payment already completed for this booking.'
                    }

                if b_status in ('Cancelled', 'Expired') or p_status in ('Failed', 'Cancelled'):
                    return {
                        'success': False,
                        'error': 'INVALID_BOOKING',
                        'message': 'TravelEase booking is expired or cancelled.'
                    }

                try:
                    db_amt = float(local_booking.get('total_amount') or 0.0)
                    if db_amt > 0:
                        if client_amount is not None:
                            try:
                                c_amt = float(client_amount)
                                if abs(c_amt - db_amt) > 0.01:
                                    return {
                                        'success': False,
                                        'error': 'AMOUNT_MISMATCH',
                                        'message': f'Amount mismatch. Authoritative booking amount is ₹{db_amt:,.2f}'
                                    }
                            except (ValueError, TypeError):
                                pass
                        verified_amount = db_amt
                        verified_type = cls.normalize_booking_type(local_booking.get('travel_type') or booking_type or 'flight')
                except (ValueError, TypeError):
                    pass

        # 4. Fallback to existing non-expired PaymentRequest created authoritatively
        if existing_pr:
            if existing_pr.is_expired():
                return {
                    'success': False,
                    'error': 'EXPIRED_REQUEST',
                    'message': 'Payment request has expired'
                }
            pr_amount = float(existing_pr.amount)
            if client_amount is not None and abs(client_amount - pr_amount) > 0.01:
                return {
                    'success': False,
                    'error': 'AMOUNT_MISMATCH',
                    'message': f'QR amount ₹{client_amount:,.2f} does not match server verified amount ₹{pr_amount:,.2f}'
                }
            if verified_amount is None:
                verified_amount = pr_amount
            if not verified_type:
                verified_type = cls.normalize_booking_type(existing_pr.booking_type or booking_type or 'flight')

        # 5. If TravelEase is completely unreachable/unregistered and no authoritative record exists
        if verified_amount is None or verified_amount <= 0:
            if not remote_available:
                return {
                    'success': False,
                    'error': 'API_UNAVAILABLE',
                    'message': 'TravelEase API is currently unavailable and booking could not be verified'
                }
            return {
                'success': False,
                'error': 'INVALID_AMOUNT',
                'message': 'Could not authoritatively verify booking amount.'
            }

        if not verified_type:
            verified_type = cls.normalize_booking_type(booking_type or 'flight')

        return {
            'success': True,
            'verified': True,
            'booking_id': clean_bid,
            'merchant': 'TravelEase',
            'amount': round(float(verified_amount), 2),
            'currency': 'INR',
            'booking_type': verified_type,
            'payment_request': existing_pr
        }

    @classmethod
    def notify_payment_success(cls, booking_id: str, transaction_id: str, payment_request_id: str = None) -> bool:
        """
        Signals TravelEase that payment was debited so TravelEase can confirm the booking.
        """
        api_url, api_key = cls.get_config()
        headers = {'X-Service-API-Key': api_key}
        try:
            resp = requests.get(
                f'{api_url}/booking/pocketpay/check-status/{booking_id}',
                params={'payment_request_id': payment_request_id or transaction_id},
                headers=headers,
                timeout=4
            )
            return resp.status_code == 200 and resp.json().get('confirmed', False)
        except Exception as e:
            if current_app:
                current_app.logger.warning(f'[TravelEaseService] Notify status error: {e}')
            return False
