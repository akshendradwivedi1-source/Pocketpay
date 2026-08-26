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
    valid, msg = validate_required_fields(data, ['account_number', 'ifsc_code', 'account_holder', 'amount'])
    if not valid:
        return error_response(msg, 400)
        
    amount = float(data.get('amount', 0))
    mode = str(data.get('mode', 'IMPS')).strip().upper()
    idempotency_key = data.get('idempotency_key')
    
    beneficiary = {
        'account_number': str(data.get('account_number', '')).strip(),
        'ifsc_code': str(data.get('ifsc_code', '')).strip().upper(),
        'account_holder': str(data.get('account_holder', '')).strip(),
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
            
    res = PayoutProvider.execute_bank_payout(
        user=current_user,
        amount=amount,
        beneficiary=beneficiary,
        mode=mode,
        idempotency_key=idempotency_key
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
        idempotency_key=idempotency_key
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


@bp.route('/webhook', methods=['POST'])
def payout_webhook():
    """Webhook endpoint for receiving asynchronous payout events from live payment provider"""
    payload = request.get_json(silent=True) or {}
    event = payload.get('event')
    payout_id = payload.get('data', {}).get('payout_id')
    
    if not payout_id:
        return json_response(message='Webhook received (No payout ID)', status_code=200)
        
    # Idempotent status reconciliation
    all_txs = Transaction.query.order_by(Transaction.id.desc()).limit(200).all()
    tx = next((t for t in all_txs if (t.extra_data or {}).get('payout_id') == payout_id or (t.extra_data or {}).get('payout', {}).get('payout_id') == payout_id), None)
    if tx:
        status = payload.get('data', {}).get('status', 'processed').lower()
        if status in ('failed', 'reversed') and tx.status != 'failed':
            tx.status = 'failed'
            # Rollback funds
            user = tx.user
            user.wallet_balance = round(user.wallet_balance + tx.amount, 2)
            db.session.commit()
            
    return json_response(message='Webhook processed successfully', status_code=200)
