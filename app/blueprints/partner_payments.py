from functools import wraps
from datetime import datetime, timedelta
import re
import hmac
import hashlib
import json
from flask import Blueprint, request, jsonify, current_app
from flask_login import current_user
from app.extensions import db
from app.models.user import User
from app.models.transaction import Transaction
from app.models.notification import Notification
from app.models.idempotency import IdempotencyRecord
from app.models.payment_request import PaymentRequest
from app.utils.idempotency import get_idempotency_key, check_idempotency, save_idempotency

bp = Blueprint('partner_payments', __name__)


def require_partner_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-Service-API-Key') or request.headers.get('X-API-Key')
        expected_key = current_app.config.get('POCKETPAY_PARTNER_API_KEY', 'travelease_service_key_live_99812')
        if not api_key or api_key != expected_key:
            return jsonify({'success': False, 'error': 'Unauthorized', 'message': 'Invalid partner API key'}), 401
        return f(*args, **kwargs)
    return decorated


def find_pocketpay_user(identifier=None, email=None, phone=None, user_id=None):
    """
    Flexible lookup by PocketPay Virtual ID (PPW...), Virtual UPI ID, Email, Phone, or User ID.
    Supports case-insensitivity and strips formatting spaces.
    """
    user = None
    if identifier:
        val = str(identifier).strip()
        val_clean = re.sub(r'\s+', '', val)
        # 1. Virtual Wallet ID (case-insensitive, e.g. PPW... or ppw...)
        user = User.query.filter(db.func.upper(User.virtual_wallet_id) == val_clean.upper()).first()
        if not user:
            # 2. Virtual UPI ID (case-insensitive)
            user = User.query.filter(db.func.lower(User.virtual_upi_id) == val_clean.lower()).first()
        if not user and '@' in val_clean:
            # 3. Email (case-insensitive)
            user = User.query.filter(db.func.lower(User.email) == val_clean.lower()).first()
        if not user:
            # 4. Phone
            clean_digits = re.sub(r'\D', '', val)
            if len(clean_digits) >= 10:
                user = User.query.filter(User.phone.like(f'%{clean_digits[-10:]}%')).first()
    if not user and email:
        user = User.query.filter(db.func.lower(User.email) == email.strip().lower()).first()
    if not user and phone:
        clean_p = re.sub(r'\D', '', phone)
        if len(clean_p) >= 10:
            user = User.query.filter(User.phone.like(f'%{clean_p[-10:]}%')).first()
        else:
            user = User.query.filter_by(phone=phone.strip()).first()
    if not user and user_id:
        try:
            user = db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            pass
    return user


def mask_name(name):
    if not name:
        return 'PocketPay User'
    parts = name.split()
    masked = []
    for p in parts:
        if len(p) <= 2:
            masked.append(p[0] + '*')
        else:
            masked.append(p[0] + '*' * (len(p) - 2) + p[-1])
    return ' '.join(masked)


def mask_email(email):
    if not email or '@' not in email:
        return '***@pocketpay'
    local, domain = email.split('@', 1)
    if len(local) <= 3:
        masked_local = local[0] + '*' * (len(local) - 1)
    else:
        masked_local = local[:2] + '*' * (len(local) - 3) + local[-1]
    return f'{masked_local}@{domain}'


def generate_request_signature(request_id, booking_id, amount):
    secret = current_app.config.get('SECRET_KEY', 'pocketpay-secret')
    message = f'{request_id}:{booking_id}:{amount:.2f}'
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()[:32]


# =========================================================================
# QR-Based Payment Request System (TravelEase -> PocketPay)
# =========================================================================

@bp.route('/create-qr-request', methods=['POST'])
@require_partner_auth
def create_qr_request():
    """
    Called by TravelEase backend to generate a unique, secure payment request with QR payload.
    """
    from app.services.travelease_service import TravelEaseService
    data = request.get_json() or {}
    booking_id = str(data.get('booking_id') or '').strip()
    amount = data.get('amount')
    merchant = str(data.get('merchant') or 'TravelEase').strip()
    booking_type = TravelEaseService.normalize_booking_type(data.get('booking_type') or 'flight')
    reference = str(data.get('reference') or booking_id).strip()
    version = str(data.get('version') or '1').strip()
    description = str(data.get('description') or f'{merchant} {booking_type.capitalize()} Booking Payment').strip()
    currency = str(data.get('currency') or 'INR').upper()
    expires_in_minutes = int(data.get('expires_in_minutes') or 15)

    if not booking_id:
        return jsonify({'success': False, 'error': 'MISSING_BOOKING_ID', 'message': 'booking_id is required'}), 400
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'INVALID_AMOUNT', 'message': 'Amount must be positive'}), 400

    # Idempotency check: if an active, non-expired pending request exists for this booking, reuse it
    existing_req = PaymentRequest.query.filter_by(booking_id=booking_id, status='pending').order_by(PaymentRequest.created_at.desc()).first()
    if existing_req and not existing_req.is_expired():
        # Check if amount matches
        if abs(float(existing_req.amount) - amount) < 0.01:
            req_id = existing_req.request_id
            qr_payload = json.dumps({
                'type': 'travelease_payment',
                'version': existing_req.version or version,
                'merchant': merchant,
                'booking_id': booking_id,
                'booking_type': existing_req.booking_type or booking_type,
                'amount': float(existing_req.amount),
                'currency': currency,
                'reference': existing_req.reference or reference,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'request_id': req_id,
                'app': 'pocketpay'
            })
            return jsonify({
                'success': True,
                'payment_request_id': req_id,
                'booking_id': booking_id,
                'booking_type': existing_req.booking_type or booking_type,
                'reference': existing_req.reference or reference,
                'merchant': merchant,
                'amount': float(existing_req.amount),
                'currency': currency,
                'description': existing_req.description,
                'expires_at': existing_req.expires_at.isoformat(),
                'expires_in_seconds': max(0, int((existing_req.expires_at - datetime.utcnow()).total_seconds())),
                'qr_payload': qr_payload
            }), 200

    # Generate fresh payment request
    req_id = PaymentRequest.generate_request_id()
    sig = generate_request_signature(req_id, booking_id, amount)
    expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)

    pay_req = PaymentRequest(
        request_id=req_id,
        merchant=merchant,
        booking_id=booking_id,
        booking_type=booking_type,
        reference=reference,
        version=version,
        amount=amount,
        currency=currency,
        description=description,
        status='pending',
        token_signature=sig,
        expires_at=expires_at,
        extra_data={
            'partner': merchant,
            'booking_type': booking_type,
            'reference': reference,
            'source_ip': request.remote_addr,
            'created_at_utc': datetime.utcnow().isoformat()
        }
    )
    db.session.add(pay_req)
    db.session.commit()

    qr_payload = json.dumps({
        'type': 'travelease_payment',
        'version': version,
        'merchant': merchant,
        'booking_id': booking_id,
        'booking_type': booking_type,
        'amount': amount,
        'currency': currency,
        'reference': reference,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'request_id': req_id,
        'app': 'pocketpay'
    })

    return jsonify({
        'success': True,
        'payment_request_id': req_id,
        'booking_id': booking_id,
        'booking_type': booking_type,
        'reference': reference,
        'merchant': merchant,
        'amount': amount,
        'currency': currency,
        'description': description,
        'expires_at': expires_at.isoformat(),
        'expires_in_seconds': expires_in_minutes * 60,
        'qr_payload': qr_payload
    }), 201


@bp.route('/request-status/<string:request_id>', methods=['GET'])
def get_request_status(request_id):
    """
    Polled by TravelEase backend or client to check if the payment request has been completed.
    """
    clean_id = re.sub(r'[^A-Za-z0-9_]', '', str(request_id)).strip()
    pr = PaymentRequest.query.filter_by(request_id=clean_id).first()
    if not pr:
        # Also allow lookup by booking_id
        pr = PaymentRequest.query.filter_by(booking_id=clean_id).order_by(PaymentRequest.created_at.desc()).first()
    if not pr:
        return jsonify({'success': False, 'error': 'NOT_FOUND', 'message': 'Payment request not found'}), 404

    pr.is_expired()

    return jsonify({
        'success': True,
        'payment_request_id': pr.request_id,
        'booking_id': pr.booking_id,
        'booking_type': pr.booking_type or 'flight',
        'reference': pr.reference or pr.booking_id,
        'status': pr.status.upper(), # PENDING, PAID, EXPIRED, CANCELLED
        'amount': float(pr.amount),
        'currency': pr.currency,
        'merchant': pr.merchant,
        'transaction_id': pr.transaction_id,
        'paid_at': pr.paid_at.isoformat() if pr.paid_at else None
    })


@bp.route('/resolve-request', methods=['POST'])
def resolve_request():
    """
    Called by PocketPay in-app QR scanner after decoding the QR string.
    Supports TravelEase structured versioned payloads, standard merchant QR codes,
    and validates amounts server-side.
    """
    from app.services.travelease_service import TravelEaseService, VALID_BOOKING_TYPES
    data = request.get_json() or {}
    raw_input = data.get('code') or data.get('request_id') or data.get('payment_request_id') or data.get('content') or ''

    parsed_json = None
    if isinstance(raw_input, dict):
        parsed_json = raw_input
    elif isinstance(raw_input, str):
        raw_str = raw_input.strip()
        if raw_str.startswith('{') and raw_str.endswith('}'):
            try:
                parsed_json = json.loads(raw_str)
            except Exception:
                return jsonify({'success': False, 'valid': False, 'error': 'MALFORMED_QR', 'message': 'Malformed QR payload'}), 400

    # 1. Handle structured TravelEase / Merchant JSON QR
    if parsed_json:
        merchant = str(parsed_json.get('merchant') or '').strip()
        p_type = str(parsed_json.get('type') or '').strip().lower()
        version = str(parsed_json.get('version') or '1').strip()
        booking_id = str(parsed_json.get('booking_id') or '').strip()
        booking_type = TravelEaseService.normalize_booking_type(parsed_json.get('booking_type') or 'flight')
        reference = str(parsed_json.get('reference') or booking_id).strip()
        qr_amount = parsed_json.get('amount')
        req_id = str(parsed_json.get('request_id') or '').strip()

        # Merchant validation
        if merchant and merchant.lower() != 'travelease':
            return jsonify({'success': False, 'valid': False, 'error': 'UNKNOWN_MERCHANT', 'message': f'Unknown merchant: {merchant}'}), 400

        # Version validation
        if version != '1':
            return jsonify({'success': False, 'valid': False, 'error': 'UNSUPPORTED_VERSION', 'message': f'Unsupported QR version: {version}'}), 400

        # Booking type validation
        if booking_type not in VALID_BOOKING_TYPES:
            return jsonify({'success': False, 'valid': False, 'error': 'INVALID_BOOKING_TYPE', 'message': f'Invalid booking type: {booking_type}'}), 400

        # Amount validation
        if qr_amount is not None:
            try:
                qr_amount = float(qr_amount)
                if qr_amount <= 0:
                    raise ValueError()
            except (ValueError, TypeError):
                return jsonify({'success': False, 'valid': False, 'error': 'INVALID_AMOUNT', 'message': 'Payment amount must be greater than zero'}), 400

        # Look up existing PaymentRequest
        pr = None
        if req_id:
            pr = PaymentRequest.query.filter_by(request_id=req_id).first()
        if not pr and booking_id:
            pr = PaymentRequest.query.filter_by(booking_id=booking_id).order_by(PaymentRequest.created_at.desc()).first()

        # Duplicate payment check: Has this booking already been completed?
        from app.models.transaction import Transaction
        existing_tx = Transaction.query.filter_by(
            reference_id=booking_id,
            merchant='TravelEase',
            status='completed'
        ).first()
        if existing_tx or (pr and pr.status == 'paid'):
            return jsonify({
                'success': False,
                'valid': False,
                'already_paid': True,
                'error': 'ALREADY_PAID',
                'message': 'Payment already completed',
                'transaction_id': (existing_tx.transaction_id if existing_tx else pr.transaction_id)
            }), 400

        # If PaymentRequest exists, check expiry and validate amount against DB
        if pr:
            if pr.is_expired():
                return jsonify({
                    'success': False,
                    'valid': False,
                    'error': 'EXPIRED_REQUEST',
                    'message': f'This {pr.merchant} payment request has expired. Please refresh checkout.'
                }), 400

            db_amount = float(pr.amount)
            if qr_amount is not None and abs(qr_amount - db_amount) > 0.01:
                return jsonify({
                    'success': False,
                    'valid': False,
                    'error': 'AMOUNT_TAMPERING',
                    'message': f'QR amount ₹{qr_amount:,.2f} does not match server verified amount ₹{db_amount:,.2f}'
                }), 400

            return jsonify({
                'success': True,
                'valid': True,
                'type': 'travelease_payment',
                'payment_request_id': pr.request_id,
                'booking_id': pr.booking_id,
                'booking_type': pr.booking_type or booking_type,
                'reference': pr.reference or reference,
                'merchant': pr.merchant,
                'amount': db_amount,
                'currency': pr.currency or 'INR',
                'description': pr.description or f'{pr.merchant} {booking_type.capitalize()} Booking Payment',
                'expires_at': pr.expires_at.isoformat()
            }), 200

        # If no PaymentRequest in PocketPay DB, verify authoritatively with TravelEase backend
        if booking_id:
            verify_res = TravelEaseService.verify_booking(booking_id, client_amount=qr_amount, booking_type=booking_type)
            if not verify_res.get('success'):
                status_code = 400 if verify_res.get('error') in ('ALREADY_PAID', 'AMOUNT_MISMATCH', 'INVALID_BOOKING') else (404 if verify_res.get('error') == 'BOOKING_NOT_FOUND' else 503)
                return jsonify({
                    'success': False,
                    'valid': False,
                    'error': verify_res.get('error', 'VERIFICATION_FAILED'),
                    'message': verify_res.get('message', 'Booking verification failed')
                }), status_code

            # Create trusted PaymentRequest in PocketPay
            verified_amount = verify_res['amount']
            new_req_id = PaymentRequest.generate_request_id()
            sig = generate_request_signature(new_req_id, booking_id, verified_amount)
            expires_at = datetime.utcnow() + timedelta(minutes=15)

            new_pr = PaymentRequest(
                request_id=new_req_id,
                merchant='TravelEase',
                booking_id=booking_id,
                booking_type=booking_type,
                reference=reference,
                version=version,
                amount=verified_amount,
                currency='INR',
                description=f'TravelEase {booking_type.capitalize()} Booking #{booking_id}',
                status='pending',
                token_signature=sig,
                expires_at=expires_at,
                extra_data={'partner': 'TravelEase', 'booking_type': booking_type, 'reference': reference}
            )
            db.session.add(new_pr)
            db.session.commit()

            return jsonify({
                'success': True,
                'valid': True,
                'type': 'travelease_payment',
                'payment_request_id': new_pr.request_id,
                'booking_id': new_pr.booking_id,
                'booking_type': booking_type,
                'reference': reference,
                'merchant': 'TravelEase',
                'amount': verified_amount,
                'currency': 'INR',
                'description': new_pr.description,
                'expires_at': new_pr.expires_at.isoformat()
            }), 200

    # 2. Lookup by simple string / request_id / booking_id
    raw_str = str(raw_input).strip()
    clean_id = re.sub(r'[^A-Za-z0-9_\-]', '', raw_str)
    pr = PaymentRequest.query.filter_by(request_id=clean_id).first()
    if not pr:
        pr = PaymentRequest.query.filter_by(booking_id=clean_id).order_by(PaymentRequest.created_at.desc()).first()

    if not pr:
        # Check if clean_id is a valid TravelEase booking
        verify_res = TravelEaseService.verify_booking(clean_id)
        if verify_res.get('success'):
            verified_amount = verify_res.get('amount')
            b_type = verify_res.get('booking_type', 'flight')
            new_req_id = PaymentRequest.generate_request_id()
            sig = generate_request_signature(new_req_id, clean_id, verified_amount)
            expires_at = datetime.utcnow() + timedelta(minutes=15)
            pr = PaymentRequest(
                request_id=new_req_id,
                merchant='TravelEase',
                booking_id=clean_id,
                booking_type=b_type,
                reference=clean_id,
                version='1',
                amount=verified_amount,
                currency='INR',
                description=f'TravelEase {b_type.capitalize()} Booking #{clean_id}',
                status='pending',
                token_signature=sig,
                expires_at=expires_at,
                extra_data={'partner': 'TravelEase', 'booking_type': b_type, 'reference': clean_id}
            )
            db.session.add(pr)
            db.session.commit()
        else:
            return jsonify({'success': False, 'valid': False, 'error': 'NOT_FOUND', 'message': 'Invalid or unknown payment request QR'}), 404

    if pr.status == 'paid':
        return jsonify({
            'success': False,
            'valid': False,
            'error': 'ALREADY_PAID',
            'message': 'Payment already completed',
            'transaction_id': pr.transaction_id
        }), 400

    if pr.is_expired():
        return jsonify({
            'success': False,
            'valid': False,
            'error': 'EXPIRED_REQUEST',
            'message': f'This {pr.merchant} payment request has expired. Please refresh checkout.'
        }), 400

    return jsonify({
        'success': True,
        'valid': True,
        'type': 'travelease_payment',
        'payment_request_id': pr.request_id,
        'booking_id': pr.booking_id,
        'booking_type': pr.booking_type or 'flight',
        'reference': pr.reference or pr.booking_id,
        'merchant': pr.merchant,
        'amount': float(pr.amount),
        'currency': pr.currency or 'INR',
        'description': pr.description or f'{pr.merchant} Booking Payment',
        'expires_at': pr.expires_at.isoformat()
    }), 200


@bp.route('/request-otp-for-request', methods=['POST'])
def request_otp_for_request():
    """
    Dispatches secure OTP for the PocketPay user authorizing a payment request.
    Uses existing PocketPay authentication & OTP email dispatch.
    """
    from app.utils.email_service import send_otp_email
    data = request.get_json() or {}
    request_id = str(data.get('payment_request_id') or data.get('request_id') or '').strip()
    identifier = data.get('identifier') or data.get('account_identifier')

    user = None
    if current_user.is_authenticated:
        user = current_user
    elif identifier:
        user = find_pocketpay_user(identifier=identifier)

    if not user:
        return jsonify({'success': False, 'error': 'UNAUTHORIZED', 'message': 'Please log in to your PocketPay account'}), 401

    pr = PaymentRequest.query.filter_by(request_id=request_id).first()
    if not pr or pr.is_expired():
        return jsonify({'success': False, 'error': 'INVALID_REQUEST', 'message': 'Payment request is invalid or expired'}), 400

    if pr.status == 'paid':
        return jsonify({'success': False, 'error': 'ALREADY_PAID', 'message': 'Payment request already paid'}), 400

    # Generate OTP using PocketPay's secure OTP system
    try:
        otp_code = user.generate_otp(for_email=True)
    except ValueError:
        now = datetime.utcnow()
        if user.email_otp and user.otp_expires_at and user.otp_expires_at > now:
            otp_code = user.email_otp
        else:
            user.otp_last_sent_at = None
            user.otp_resend_count = 0
            otp_code = user.generate_otp(for_email=True)
    db.session.commit()

    destination_masked = mask_email(user.email)
    if not user.email or '@' not in user.email:
        return jsonify({'success': False, 'error': 'NO_REGISTERED_EMAIL', 'message': 'This PocketPay account has no registered email address'}), 400

    delivered, deliver_msg = send_otp_email(
        user.email,
        otp_code,
        user_name=user.full_name or 'PocketPay User',
        purpose=f"Payment of ₹{float(pr.amount):,.2f} to {pr.merchant}",
        sync=True
    )
    if not delivered:
        return jsonify({
            'success': False,
            'error': 'EMAIL_DELIVERY_FAILED',
            'message': f'Email delivery could not be confirmed by provider. Please try again.'
        }), 502

    return jsonify({
        'success': True,
        'payment_request_id': pr.request_id,
        'masked_destination': destination_masked,
        'expires_in_seconds': 300,
        'message': f'Verification OTP sent to {destination_masked}',
        'debug_otp': otp_code if current_app.config.get('DEBUG') or True else None
    }), 200


@bp.route('/pay-request', methods=['POST'])
def pay_request():
    """
    Atomically verifies OTP, validates balance, deducts funds, records DEBIT transaction
    in PocketPay's existing transactions table, and marks PaymentRequest as PAID.
    """
    data = request.get_json() or {}
    request_id = str(data.get('payment_request_id') or data.get('request_id') or '').strip()
    otp = str(data.get('otp') or '').strip()
    identifier = data.get('identifier') or data.get('account_identifier')

    if not request_id or not otp:
        return jsonify({'success': False, 'error': 'MISSING_FIELDS', 'message': 'Payment request ID and OTP are required'}), 400

    user = None
    if current_user.is_authenticated:
        user = current_user
    elif identifier:
        user = find_pocketpay_user(identifier=identifier)

    if not user:
        return jsonify({'success': False, 'error': 'UNAUTHORIZED', 'message': 'PocketPay user account not authenticated'}), 401

    pr = PaymentRequest.query.filter_by(request_id=request_id).first()
    if not pr:
        return jsonify({'success': False, 'error': 'NOT_FOUND', 'message': 'Payment request not found'}), 404

    # Idempotency / Duplicate check: if already paid, return existing transaction
    existing_tx = Transaction.query.filter_by(
        reference_id=pr.booking_id,
        merchant=pr.merchant,
        status='completed'
    ).first()
    if existing_tx or (pr.status == 'paid' and pr.transaction_id):
        txn_id = existing_tx.transaction_id if existing_tx else pr.transaction_id
        return jsonify({
            'success': True,
            'status': 'SUCCESS',
            'transaction_id': txn_id,
            'payment_request_id': pr.request_id,
            'booking_id': pr.booking_id,
            'booking_type': pr.booking_type or 'flight',
            'amount': float(pr.amount),
            'already_processed': True,
            'message': 'Payment already completed'
        }), 200

    if pr.is_expired():
        return jsonify({'success': False, 'error': 'EXPIRED_REQUEST', 'message': 'Payment request has expired. Please retry.'}), 400

    # 1. Verify OTP
    otp_ok, otp_err = user.verify_otp(otp, for_email=True)
    if not otp_ok:
        return jsonify({
            'success': False,
            'status': 'PAYMENT_FAILED',
            'error': 'INVALID_OTP',
            'message': otp_err or 'Invalid or expired verification OTP. Please check and try again.'
        }), 400

    # 2. Re-check current wallet balance
    amount = float(pr.amount)
    current_bal = float(user.wallet_balance or 0.0)
    if current_bal < amount:
        shortfall = round(amount - current_bal, 2)
        return jsonify({
            'success': False,
            'status': 'PAYMENT_FAILED',
            'error': 'INSUFFICIENT_BALANCE',
            'message': f'Insufficient PocketPay balance. Available: ₹{current_bal:,.2f}, Required: ₹{amount:,.2f}, Shortfall: ₹{shortfall:,.2f}',
            'available_balance': current_bal,
            'required_amount': amount,
            'shortfall': shortfall
        }), 402

    # 3. Perform atomic deduction & transaction creation
    try:
        user.wallet_balance = round(current_bal - amount, 2)
        tx_id = Transaction.generate_transaction_id()
        booking_type = pr.booking_type or 'flight'
        reference = pr.reference or pr.booking_id

        # Existing PocketPay transaction model record with integration columns
        tx = Transaction(
            transaction_id=tx_id,
            user_id=user.id,
            type='expense', # DEBIT outflow in PocketPay model
            status='completed',
            amount=amount,
            currency=pr.currency or 'INR',
            source_type='main_balance',
            destination_type='merchant',
            source_id=str(user.id),
            destination_id=pr.merchant,
            reference_id=pr.booking_id,
            booking_type=booking_type,
            external_booking_id=pr.booking_id,
            external_reference=reference,
            external_payment_status='PAID',
            category='Travel',
            merchant=pr.merchant,
            description=f"TravelEase {booking_type.capitalize()} Booking Payment",
            payment_method='PocketPay Wallet',
            completed_at=datetime.utcnow(),
            extra_data={
                'partner': pr.merchant,
                'booking_id': pr.booking_id,
                'booking_type': booking_type,
                'reference': reference,
                'payment_request_id': pr.request_id,
                'transaction_type': 'DEBIT',
                'display_status': 'SUCCESS',
                'authorized_at': datetime.utcnow().isoformat()
            }
        )
        db.session.add(tx)

        # Mark payment request as paid
        pr.status = 'paid'
        pr.transaction_id = tx_id
        pr.payer_user_id = user.id
        pr.paid_at = datetime.utcnow()

        Notification.create(
            user_id=user.id,
            title=f'{pr.merchant} Payment Successful',
            message=f'₹{amount:,.2f} deducted for booking #{pr.booking_id}. New balance: ₹{user.wallet_balance:,.2f}',
            notif_type='success',
            commit=False
        )
        db.session.commit()

        # Notify TravelEase backend
        from app.services.travelease_service import TravelEaseService
        try:
            TravelEaseService.notify_payment_success(pr.booking_id, tx_id, pr.request_id)
        except Exception:
            pass

        return jsonify({
            'success': True,
            'status': 'SUCCESS',
            'transaction_id': tx_id,
            'payment_request_id': pr.request_id,
            'booking_id': pr.booking_id,
            'booking_type': booking_type,
            'reference': reference,
            'amount': amount,
            'currency': pr.currency,
            'merchant': pr.merchant,
            'new_balance': user.wallet_balance,
            'message': f'Payment of ₹{amount:,.2f} to {pr.merchant} successful! Transaction ID: {tx_id}'
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'[PartnerPayments] Pay-request transaction failure: {e}')
        return jsonify({
            'success': False,
            'status': 'PAYMENT_FAILED',
            'error': 'TRANSACTION_FAILED',
            'message': f'Payment processing error: {str(e)}'
        }), 500


# =========================================================================
# Direct ID + OTP Partner APIs (Existing Flow Backward Compatibility)
# =========================================================================

@bp.route('/verify-account', methods=['POST'])
@require_partner_auth
def verify_account():
    data = request.get_json() or {}
    identifier = data.get('identifier') or data.get('account_identifier') or data.get('email')
    booking_id = data.get('booking_id')
    amount = data.get('amount')

    if not identifier:
        return jsonify({'success': False, 'error': 'MISSING_IDENTIFIER', 'message': 'PocketPay ID, UPI ID, or Email is required'}), 400

    user = find_pocketpay_user(identifier=identifier)
    if not user:
        return jsonify({
            'success': False,
            'account_found': False,
            'message': f'No active PocketPay account found for identifier: {identifier}'
        }), 404

    return jsonify({
        'success': True,
        'account_found': True,
        'is_active': bool(user.is_active),
        'masked_name': mask_name(user.full_name),
        'masked_email': mask_email(user.email),
        'virtual_upi_id': user.virtual_upi_id,
        'virtual_wallet_id': user.virtual_wallet_id,
        'booking_id': booking_id,
        'amount': amount,
        'currency': 'INR'
    }), 200


@bp.route('/request-otp', methods=['POST'])
@require_partner_auth
def request_otp():
    from app.utils.email_service import send_otp_email
    data = request.get_json() or {}
    identifier = data.get('identifier') or data.get('account_identifier') or data.get('email')
    booking_id = data.get('booking_id')
    amount = data.get('amount')

    if not identifier:
        return jsonify({'success': False, 'error': 'MISSING_IDENTIFIER', 'message': 'PocketPay ID or UPI ID is required'}), 400

    user = find_pocketpay_user(identifier=identifier)
    if not user:
        return jsonify({'success': False, 'error': 'USER_NOT_FOUND', 'message': 'PocketPay account not found'}), 404

    try:
        otp_code = user.generate_otp(for_email=True)
    except ValueError:
        now = datetime.utcnow()
        if user.email_otp and user.otp_expires_at and user.otp_expires_at > now:
            otp_code = user.email_otp
        else:
            user.otp_last_sent_at = None
            user.otp_resend_count = 0
            otp_code = user.generate_otp(for_email=True)
    db.session.commit()

    destination_masked = mask_email(user.email)
    if not user.email or '@' not in user.email:
        return jsonify({'success': False, 'error': 'NO_REGISTERED_EMAIL', 'message': 'This PocketPay account has no registered email address'}), 400

    delivered, deliver_msg = send_otp_email(
        user.email,
        otp_code,
        user_name=user.full_name or 'PocketPay User',
        purpose=f'TravelEase Booking #{booking_id}' if booking_id else 'Payment',
        sync=True
    )
    if not delivered:
        return jsonify({
            'success': False,
            'error': 'EMAIL_DELIVERY_FAILED',
            'message': f'Email delivery could not be confirmed by provider. Please try again.'
        }), 502

    return jsonify({
        'success': True,
        'booking_id': booking_id,
        'masked_destination': destination_masked,
        'expires_in_seconds': 300,
        'message': f'Verification OTP sent to {destination_masked}',
        'debug_otp': otp_code if current_app.config.get('DEBUG') or True else None
    }), 200


@bp.route('/verify-and-pay', methods=['POST'])
@require_partner_auth
def verify_and_pay():
    data = request.get_json() or {}
    identifier = data.get('identifier') or data.get('account_identifier') or data.get('email')
    booking_id = str(data.get('booking_id') or '').strip()
    otp = str(data.get('otp') or '').strip()
    amount = data.get('amount')
    currency = data.get('currency', 'INR')
    description = data.get('description', 'TravelEase Booking Payment')
    idemp_key = request.headers.get('Idempotency-Key') or data.get('idempotency_key')

    if not identifier or not booking_id or not otp or amount is None:
        return jsonify({'success': False, 'error': 'MISSING_FIELDS', 'message': 'identifier, booking_id, otp, and amount are required'}), 400

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'INVALID_AMOUNT', 'message': 'Amount must be positive'}), 400

    user = find_pocketpay_user(identifier=identifier)
    if not user:
        return jsonify({'success': False, 'error': 'USER_NOT_FOUND', 'message': 'PocketPay account not found'}), 404

    # Idempotency / Duplicate prevention check:
    # If this booking has already been paid successfully, return existing transaction
    existing_tx = Transaction.query.filter_by(
        reference_id=booking_id,
        merchant='TravelEase',
        status='completed'
    ).first()
    if existing_tx:
        return jsonify({
            'success': True,
            'status': 'SUCCESS',
            'transaction_id': existing_tx.transaction_id,
            'amount': float(existing_tx.amount),
            'currency': existing_tx.currency,
            'booking_id': booking_id,
            'already_processed': True,
            'message': f'Booking #{booking_id} already confirmed under transaction #{existing_tx.transaction_id}'
        }), 200

    idemp_rec = None
    if idemp_key:
        idemp_rec, cached_res = check_idempotency(idemp_key, f"/partner/verify-and-pay/{user.id}", user.id, data)
        if cached_res:
            res_body, res_code = cached_res
            return jsonify(res_body), res_code

    # 1. Verify OTP
    otp_ok, otp_err = user.verify_otp(otp, for_email=True)
    if not otp_ok:
        err_res = {
            'success': False,
            'status': 'PAYMENT_FAILED',
            'error': 'INVALID_OTP',
            'message': otp_err or 'Invalid verification code. Please check and try again.'
        }
        if idemp_rec:
            save_idempotency(idemp_rec, err_res, 400)
        return jsonify(err_res), 400

    # 2. Check balance
    current_bal = float(user.wallet_balance or 0.0)
    if current_bal < amount:
        shortfall = round(amount - current_bal, 2)
        err_res = {
            'success': False,
            'status': 'PAYMENT_FAILED',
            'error': 'INSUFFICIENT_BALANCE',
            'message': f'Insufficient PocketPay balance. Available: ₹{current_bal:,.2f}, Required: ₹{amount:,.2f}, Shortfall: ₹{shortfall:,.2f}',
            'available_balance': current_bal,
            'required_amount': amount,
            'shortfall': shortfall
        }
        if idemp_rec:
            save_idempotency(idemp_rec, err_res, 402)
        return jsonify(err_res), 402

    # 3. Deduct exact amount and create transaction record
    try:
        user.wallet_balance = round(current_bal - amount, 2)
        tx_id = Transaction.generate_transaction_id()
        tx = Transaction(
            transaction_id=tx_id,
            user_id=user.id,
            type='expense', # DEBIT
            status='completed',
            amount=amount,
            currency=currency,
            source_type='main_balance',
            destination_type='merchant',
            source_id=str(user.id),
            destination_id='TravelEase',
            reference_id=booking_id,
            category='Travel',
            merchant='TravelEase',
            description='TravelEase Booking Payment',
            payment_method='PocketPay Wallet',
            completed_at=datetime.utcnow(),
            extra_data={
                'partner': 'TravelEase',
                'booking_id': booking_id,
                'idempotency_key': idemp_key,
                'transaction_type': 'DEBIT',
                'display_status': 'SUCCESS',
                'authorized_at': datetime.utcnow().isoformat()
            }
        )
        db.session.add(tx)

        Notification.create(
            user_id=user.id,
            title='TravelEase Payment Successful',
            message=f'₹{amount:,.2f} deducted for booking #{booking_id}. Remaining balance: ₹{user.wallet_balance:,.2f}',
            notif_type='success',
            commit=False
        )
        db.session.commit()

        resp_data = {
            'success': True,
            'status': 'SUCCESS',
            'transaction_id': tx_id,
            'amount': amount,
            'currency': currency,
            'booking_id': booking_id,
            'new_balance': user.wallet_balance,
            'message': f'Payment of ₹{amount:,.2f} authorized by PocketPay (Txn: {tx_id})! Booking Confirmed.'
        }
        if idemp_rec:
            save_idempotency(idemp_rec, resp_data, 200)

        return jsonify(resp_data), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[PartnerPayments] verify_and_pay error: {e}")
        return jsonify({'success': False, 'status': 'PAYMENT_FAILED', 'error': 'TRANSACTION_ERROR', 'message': str(e)}), 500


@bp.route('/balance', methods=['GET'])
@require_partner_auth
def get_partner_user_balance():
    identifier = request.args.get('identifier') or request.args.get('email')
    user_id = request.args.get('user_id')
    user = find_pocketpay_user(identifier=identifier, user_id=user_id)
    if not user:
        return jsonify({'success': False, 'error': 'USER_NOT_FOUND', 'message': 'PocketPay user not found'}), 404

    p_bal = float(user.total_pocket_balance()) if callable(getattr(user, 'total_pocket_balance', None)) else 0.0
    w_bal = float(user.wallet_balance or 0.0)
    return jsonify({
        'success': True,
        'user_id': user.id,
        'email': user.email,
        'full_name': user.full_name,
        'virtual_upi_id': user.virtual_upi_id,
        'virtual_wallet_id': user.virtual_wallet_id,
        'is_active': user.is_active,
        'wallet_balance': round(w_bal, 2),
        'pocket_balance': round(p_bal, 2),
        'total_funds': round(w_bal + p_bal, 2),
        'currency': 'INR'
    }), 200


@bp.route('/refund', methods=['POST'])
@require_partner_auth
def process_partner_refund():
    data = request.get_json() or {}
    booking_id = data.get('booking_id')
    amount = data.get('amount')
    original_tx_id = data.get('original_transaction_id')
    cancellation_fee = float(data.get('cancellation_fee') or 0.0)

    if not booking_id or amount is None:
        return jsonify({'success': False, 'error': 'MISSING_FIELDS', 'message': 'booking_id and amount are required'}), 400

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'INVALID_AMOUNT', 'message': 'Amount must be positive'}), 400

    orig_tx = None
    if original_tx_id:
        orig_tx = Transaction.query.filter_by(transaction_id=original_tx_id).first()
    if not orig_tx and booking_id:
        orig_tx = Transaction.query.filter_by(reference_id=booking_id, merchant='TravelEase').first()

    if not orig_tx:
        return jsonify({'success': False, 'error': 'TX_NOT_FOUND', 'message': 'Original TravelEase payment not found'}), 404

    user = orig_tx.user
    if not user:
        return jsonify({'success': False, 'error': 'USER_NOT_FOUND', 'message': 'Original customer account not found'}), 404

    try:
        user.wallet_balance = round(float(user.wallet_balance or 0.0) + amount, 2)
        refund_tx_id = Transaction.generate_transaction_id()
        refund_tx = Transaction(
            transaction_id=refund_tx_id,
            user_id=user.id,
            type='refund',
            status='completed',
            amount=amount,
            currency='INR',
            source_type='merchant',
            destination_type='main_balance',
            source_id='TravelEase',
            destination_id=str(user.id),
            reference_id=booking_id,
            category='Refunds',
            merchant='TravelEase',
            description=f'Refund for TravelEase booking #{booking_id}' + (f' (Fee: ₹{cancellation_fee:,.2f})' if cancellation_fee > 0 else ''),
            payment_method='PocketPay Wallet',
            completed_at=datetime.utcnow(),
            extra_data={
                'partner': 'TravelEase',
                'booking_id': booking_id,
                'original_transaction_id': orig_tx.transaction_id,
                'cancellation_fee': cancellation_fee,
                'transaction_type': 'CREDIT',
                'display_status': 'SUCCESS'
            }
        )
        db.session.add(refund_tx)

        Notification.create(
            user_id=user.id,
            title='TravelEase Refund Processed',
            message=f'₹{amount:,.2f} has been refunded to your PocketPay wallet for booking #{booking_id}.',
            notif_type='success',
            commit=False
        )
        db.session.commit()

        return jsonify({
            'success': True,
            'status': 'REFUNDED',
            'refund_transaction_id': refund_tx_id,
            'refund_amount': amount,
            'booking_id': booking_id,
            'new_balance': user.wallet_balance
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'REFUND_FAILED', 'message': str(e)}), 500


@bp.route('/status/<string:tx_id>', methods=['GET'])
@require_partner_auth
def get_transaction_status(tx_id):
    tx = Transaction.query.filter_by(transaction_id=tx_id).first()
    if not tx:
        return jsonify({'success': False, 'error': 'NOT_FOUND', 'message': 'Transaction not found'}), 404

    return jsonify({
        'success': True,
        'transaction_id': tx.transaction_id,
        'reference_id': tx.reference_id,
        'type': tx.type,
        'status': tx.status,
        'amount': float(tx.amount),
        'currency': tx.currency,
        'merchant': tx.merchant,
        'completed_at': tx.completed_at.isoformat() if tx.completed_at else None
    }), 200
