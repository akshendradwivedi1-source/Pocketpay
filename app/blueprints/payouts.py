from flask import Blueprint, request
from flask_login import current_user
from app.utils.helpers import json_response, error_response, validate_required_fields, api_login_required
from app.services.payout_service import (
    PayoutProvider, PayoutStatus, SUPPORTED_NETBANKING_BANKS, parse_payment_qr
)
from app.models.transaction import Transaction
from app.extensions import db

bp = Blueprint('payouts', __name__)


@bp.route('/banks-list', methods=['GET'])
@api_login_required
def get_supported_banks():
    """Returns list of supported Net Banking and Payout partner banks"""
    return json_response({
        'banks': SUPPORTED_NETBANKING_BANKS,
        'count': len(SUPPORTED_NETBANKING_BANKS)
    })


@bp.route('/beneficiaries', methods=['GET'])
@api_login_required
def get_saved_beneficiaries():
    """Returns user's saved linked bank accounts as beneficiaries"""
    linked = current_user.linked_banks or []
    return json_response({
        'beneficiaries': linked,
        'count': len(linked)
    })


@bp.route('/validate-beneficiary', methods=['POST'])
@api_login_required
def validate_beneficiary():
    """
    Pre-validates beneficiary account number, IFSC code, and recipient existence.
    Returns sanitized beneficiary preview for transfer confirmation.
    """
    import re
    from app.models.user import User
    from app.services.payout_service import validate_account_number, validate_ifsc

    data = request.get_json() or {}
    acc_num = str(data.get('account_number', '')).strip()
    ifsc = str(data.get('ifsc_code', '')).strip().upper()
    holder = str(data.get('account_holder') or data.get('beneficiary_name') or '').strip()
    bank_name = str(data.get('bank_name', '')).strip() or "Bank Account"
    
    if not acc_num or len(acc_num) < 9:
        return error_response('Beneficiary account number must be 9 to 18 digits', 400)
    if not validate_account_number(acc_num):
        return error_response('Invalid bank account number format (9 to 18 digits required)', 400)
    if ifsc and not validate_ifsc(ifsc):
        return error_response('Invalid IFSC code format (e.g. SBIN0001234, HDFC0000123)', 400)
        
    clean_acc = re.sub(r'[\s\-]', '', acc_num)
    masked = '•••• ' + clean_acc[-4:]
    
    # Check if recipient is a registered PocketPay user
    recipient_user = None
    all_users = User.query.filter(User.id != current_user.id).all()
    for u in all_users:
        for b in (u.linked_banks or []):
            b_acc = re.sub(r'[\s\-]', '', str(b.get('account_number') or ''))
            b_mask = str(b.get('account_mask') or '')
            if (b_acc and b_acc == clean_acc) or (b_mask and b_mask.endswith(clean_acc[-4:])):
                recipient_user = u
                break
        if recipient_user:
            break
        if (u.virtual_wallet_id and u.virtual_wallet_id.upper() == clean_acc.upper()) or \
           (u.phone and re.sub(r'[\s\-]', '', u.phone) == clean_acc) or \
           (holder and u.full_name.strip().lower() == holder.strip().lower()):
            recipient_user = u
            break

    res_name = recipient_user.full_name if recipient_user else (holder or "Verified Beneficiary")

    return json_response({
        'valid': True,
        'account_number': clean_acc,
        'account_mask': masked,
        'ifsc_code': ifsc or 'SBIN0001234',
        'beneficiary_name': res_name,
        'bank_name': bank_name,
        'is_registered_member': recipient_user is not None,
        'recipient_user_id': recipient_user.id if recipient_user else None
    }, 'Beneficiary validated successfully')


@bp.route('/parse-qr', methods=['POST'])
@api_login_required
def parse_qr_endpoint():
    """Parses QR string and extracts payee information without executing a debit"""
    data = request.get_json() or {}
    qr_string = data.get('qr_string', '').strip()
    if not qr_string:
        return error_response('QR code content is required', 400)
        
    parsed = parse_payment_qr(qr_string)
    if not parsed.get('valid'):
        return error_response(parsed.get('error', 'Invalid QR code'), 400)
        
    return json_response({'qr_data': parsed})


@bp.route('/pay-qr', methods=['POST'])
@api_login_required
def execute_qr_payment():
    """Executes payment to a scanned QR or UPI address"""
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['qr_string', 'amount'])
    if not valid:
        return error_response(msg, 400)
        
    amount = float(data.get('amount', 0))
    qr_string = str(data.get('qr_string', '')).strip()
    source_type = str(data.get('source_type', 'wallet')).strip()
    pocket_id = data.get('pocket_id')
    notes = str(data.get('notes', '')).strip()
    idempotency_key = data.get('idempotency_key')
    
    # Check PIN if user has configured one
    if current_user.transaction_pin_hash:
        pin = str(data.get('pin', '')).strip()
        if not pin:
            return error_response('Transaction PIN is required', 400, code='PIN_REQUIRED')
        success, error = current_user.verify_transaction_pin(pin)
        if not success:
            return error_response(error or 'Incorrect PIN', 401, code='INCORRECT_PIN')
            
    # Check 2FA TOTP if enabled
    if current_user.totp_enabled:
        totp_code = data.get('totp_code') or data.get('totp') or data.get('otp')
        verified, err, err_code = current_user.verify_totp(totp_code)
        if not verified:
            return error_response(err or 'Invalid Authenticator 2FA code', 401, code=err_code or 'INCORRECT_TOTP')
            
    res = PayoutProvider.execute_qr_payment(
        user=current_user,
        amount=amount,
        qr_string=qr_string,
        source_type=source_type,
        pocket_id=pocket_id,
        notes=notes,
        idempotency_key=idempotency_key
    )
    
    if not res.get('success'):
        return error_response(res.get('error', 'Payment failed'), 400, code=res.get('code'))
        
    return json_response(res, res.get('message', 'Payment successful'), 201)


@bp.route('/transfer-to-bank', methods=['POST'])
@api_login_required
def transfer_to_bank():
    """Transfers funds to a bank account using legitimate payout provider in Sandbox/Live mode"""
    data = request.get_json() or {}
    account_holder = str(data.get('account_holder') or data.get('beneficiary_name') or '').strip()
    if not account_holder:
        return error_response('Account holder name is required', 400)

    valid, msg = validate_required_fields(data, ['account_number', 'ifsc_code', 'amount'])
    if not valid:
        return error_response(msg, 400)
        
    amount = float(data.get('amount', 0))
    mode = str(data.get('mode', 'IMPS')).strip().upper()
    idempotency_key = data.get('idempotency_key')
    
    beneficiary = {
        'account_number': str(data.get('account_number', '')).strip(),
        'ifsc_code': str(data.get('ifsc_code', '')).strip().upper(),
        'account_holder': account_holder,
        'bank_name': str(data.get('bank_name', '')).strip() or "Bank Account"
    }
    
    # Check PIN if user has configured one
    if current_user.transaction_pin_hash:
        pin = str(data.get('pin', '')).strip()
        if not pin:
            return error_response('Transaction PIN is required for bank transfers', 400, code='PIN_REQUIRED')
        success, error = current_user.verify_transaction_pin(pin)
        if not success:
            return error_response(error or 'Incorrect PIN', 401, code='INCORRECT_PIN')
            
    # Check 2FA TOTP if enabled
    if current_user.totp_enabled:
        totp_code = data.get('totp_code') or data.get('totp') or data.get('otp')
        verified, err, err_code = current_user.verify_totp(totp_code)
        if not verified:
            return error_response(err or 'Invalid Authenticator 2FA code', 401, code=err_code or 'INCORRECT_TOTP')
            
    source_type = str(data.get('source_type', 'wallet')).strip()
    pocket_id = data.get('pocket_id')

    res = PayoutProvider.execute_bank_payout(
        user=current_user,
        amount=amount,
        beneficiary=beneficiary,
        mode=mode,
        idempotency_key=idempotency_key,
        source_type=source_type,
        pocket_id=pocket_id
    )
    
    if not res.get('success'):
        return error_response(res.get('error', 'Transfer failed'), 400, code=res.get('code'))
        
    status_code = 200 if res.get('idempotent_replay') else 201
    return json_response(res, res.get('message', 'Bank transfer initiated successfully'), status_code)


@bp.route('/netbanking-transfer', methods=['POST'])
@api_login_required
def netbanking_transfer():
    """Transfers funds to a partner bank account via simulated net banking gateway"""
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['bank_code', 'account_number', 'account_holder', 'amount'])
    if not valid:
        return error_response(msg, 400)
        
    bank_code = str(data.get('bank_code', '')).strip().upper()
    bank_info = next((b for b in SUPPORTED_NETBANKING_BANKS if b['code'] == bank_code), None)
    bank_name = bank_info['name'] if bank_info else str(data.get('bank_name', 'Bank Account'))
    ifsc = data.get('ifsc_code') or f"{bank_code}0001234"
    
    amount = float(data.get('amount', 0))
    idempotency_key = data.get('idempotency_key')
    source_type = str(data.get('source_type', 'wallet')).strip()
    pocket_id = data.get('pocket_id')
    
    beneficiary = {
        'account_number': str(data.get('account_number', '')).strip(),
        'ifsc_code': ifsc.upper(),
        'account_holder': str(data.get('account_holder', '')).strip(),
        'bank_name': bank_name
    }
    
    # Check PIN
    if current_user.transaction_pin_hash:
        pin = str(data.get('pin', '')).strip()
        if not pin:
            return error_response('Transaction PIN is required', 400, code='PIN_REQUIRED')
        success, error = current_user.verify_transaction_pin(pin)
        if not success:
            return error_response(error or 'Incorrect PIN', 401, code='INCORRECT_PIN')
            
    # Check 2FA TOTP if enabled
    if current_user.totp_enabled:
        totp_code = data.get('totp_code') or data.get('totp') or data.get('otp')
        verified, err, err_code = current_user.verify_totp(totp_code)
        if not verified:
            return error_response(err or 'Invalid Authenticator 2FA code', 401, code=err_code or 'INCORRECT_TOTP')
            
    res = PayoutProvider.execute_bank_payout(
        user=current_user,
        amount=amount,
        beneficiary=beneficiary,
        mode='NETBANKING',
        idempotency_key=idempotency_key,
        source_type=source_type,
        pocket_id=pocket_id
    )
    
    if not res.get('success'):
        return error_response(res.get('error', 'Net banking transfer failed'), 400, code=res.get('code'))
        
    return json_response(res, f"₹{amount:,.2f} transferred via Net Banking ({bank_name}) successfully", 201)


@bp.route('/<payout_id>', methods=['GET'])
@api_login_required
def get_payout_status(payout_id):
    """Retrieves payout details, UTR, and receipt by payout_id"""
    user_txs = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.id.desc()).limit(100).all()
    tx = next((t for t in user_txs if (t.extra_data or {}).get('payout_id') == payout_id or (t.extra_data or {}).get('payout', {}).get('payout_id') == payout_id), None)
    
    if not tx:
        return error_response('Payout record not found', 404)
        
    payout = (tx.extra_data or {}).get('payout', {})
    return json_response({
        'payout': payout,
        'transaction': tx.to_dict(True)
    })


import os
import hmac
import hashlib

@bp.route('/webhook', methods=['POST'])
def payout_webhook():
    """
    Webhook endpoint for receiving asynchronous payout events from live/sandbox banking provider.
    Verifies HMAC signature, ensures idempotent event processing, and safely rolls back state on failure.
    """
    raw_body = request.get_data()
    webhook_secret = os.environ.get('WEBHOOK_SECRET') or os.environ.get('PAYOUT_WEBHOOK_SECRET')
    sig_header = request.headers.get('X-Webhook-Signature') or request.headers.get('X-Signature')

    if webhook_secret:
        if not sig_header:
            return error_response('Missing webhook signature header', 401, code='MISSING_SIGNATURE')
        expected_sig = hmac.new(webhook_secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig_header):
            return error_response('Invalid webhook signature', 401, code='INVALID_SIGNATURE')

    payload = request.get_json(silent=True) or {}
    event = payload.get('event')
    data = payload.get('data') or {}
    payout_id = data.get('payout_id')
    
    if not payout_id:
        return json_response({'status': 'ignored'}, 'Webhook received (No payout ID)', 200)
        
    # Idempotent status reconciliation
    all_txs = Transaction.query.order_by(Transaction.id.desc()).limit(200).all()
    tx = next((t for t in all_txs if (t.extra_data or {}).get('payout_id') == payout_id or (t.extra_data or {}).get('payout', {}).get('payout_id') == payout_id), None)
    if tx:
        status = str(data.get('status', 'processed')).lower()
        if status in ('failed', 'reversed') and tx.status != 'failed':
            tx.status = 'failed'
            tx.failure_reason = data.get('failure_reason') or 'Bank gateway rejected transfer'
            # Rollback funds atomically
            user = tx.user
            user.wallet_balance = round(float(user.wallet_balance or 0.0) + float(tx.amount), 2)
            db.session.commit()
            return json_response({'status': 'reversed', 'payout_id': payout_id}, 'Payout reversed and funds refunded', 200)
        elif status == 'processed' and tx.status != 'completed':
            tx.status = 'completed'
            db.session.commit()
            return json_response({'status': 'completed', 'payout_id': payout_id}, 'Payout confirmed completed', 200)
            
    return json_response({'status': 'noop', 'payout_id': payout_id}, 'Webhook processed successfully', 200)

