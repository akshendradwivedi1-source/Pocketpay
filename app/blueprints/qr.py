from flask import Blueprint, request, render_template, redirect, url_for, jsonify
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.utils.helpers import get_public_base_url
import re

bp = Blueprint('qr', __name__, url_prefix='/qr')


@bp.route('/pay')
@bp.route('/user/<string:user_ref>')
@bp.route('/wallet/<string:wallet_id>')
def qr_pay_destination(user_ref=None, wallet_id=None):
    """
    Universal mobile & desktop destination for User / Wallet / UPI QR code scans.
    Scannable with standard camera, Google Lens, or in-app scanner.
    """
    target_ident = user_ref or wallet_id or request.args.get('user') or request.args.get('upi_id') or ''
    user_name = request.args.get('name') or ''
    
    target_user = None
    if target_ident:
        clean_ident = re.sub(r'[\x00-\x1f\s]', '', str(target_ident)).strip()
        target_user = User.query.filter(
            (User.virtual_wallet_id == clean_ident) |
            (User.virtual_upi_id == clean_ident) |
            (User.email == clean_ident) |
            (User.phone == clean_ident)
        ).first()
            
    if target_user:
        recipient_name = target_user.full_name or 'PocketPay User'
        resolved_upi_id = target_user.virtual_upi_id or f"{target_user.email.split('@')[0]}@pocketpay"
        resolved_wallet_id = target_user.virtual_wallet_id
    elif target_ident or user_name:
        recipient_name = user_name or target_ident.split('@')[0].capitalize()
        resolved_upi_id = target_ident
        resolved_wallet_id = target_ident
    else:
        return render_template('qr/error.html',
            error_title="Recipient Not Found",
            error_message="The payment QR code you scanned does not belong to an active PocketPay user."
        ), 404

    upi_uri = f"upi://pay?pa={resolved_upi_id}&pn={recipient_name}&cu=INR"

    return render_template('qr/pay.html',
        recipient_name=recipient_name,
        upi_id=resolved_upi_id,
        wallet_id=resolved_wallet_id,
        upi_uri=upi_uri
    )


@bp.route('/pocket/<string:pocket_ref>')
def qr_pocket_destination(pocket_ref):
    """
    Universal mobile & desktop destination for Pocket QR code scans.
    """
    clean_ref = re.sub(r'[\x00-\x1f\s]', '', str(pocket_ref)).strip()
    
    pocket = None
    if clean_ref.isdigit():
        pocket = Pocket.query.filter_by(id=int(clean_ref), archived=False).first()
        
    if not pocket:
        return render_template('qr/error.html',
            error_title="Pocket Not Found",
            error_message="The savings pocket you scanned does not exist or has been archived."
        ), 404

    owner = pocket.user
    owner_name = owner.full_name if owner else 'PocketPay Member'
    
    target_amount = pocket.budget_amount or pocket.monthly_limit or 0
    progress_pct = 0
    if target_amount and target_amount > 0:
        progress_pct = min(100, (float(pocket.current_balance or 0) / float(target_amount)) * 100)

    return render_template('qr/pocket.html',
        pocket=pocket,
        owner_name=owner_name,
        target_amount=target_amount,
        progress_pct=progress_pct
    )


@bp.route('/tx/<string:tx_id>')
def qr_transaction_destination(tx_id):
    """
    Universal mobile & desktop destination for digital Transaction Receipt QR code scans.
    """
    clean_tx_id = re.sub(r'[\x00-\x1f\s]', '', str(tx_id)).strip()
    
    tx = Transaction.query.filter_by(transaction_id=clean_tx_id).first()
    if not tx:
        # Fallback to UUID
        tx = Transaction.query.filter_by(uuid=clean_tx_id).first()
        
    if not tx:
        return render_template('qr/error.html',
            error_title="Receipt Not Found",
            error_message="The digital transaction receipt you scanned could not be verified."
        ), 404

    from app.utils.helpers import generate_qr_code, build_qr_tx_url
    formatted_date = tx.created_at.strftime('%d %b %Y, %I:%M %p UTC') if tx.created_at else 'Recent'
    
    sender_name = tx.user.full_name if tx.user else 'PocketPay User'
    recipient_name = tx.merchant or ''
    if tx.extra_data and isinstance(tx.extra_data, dict):
        recipient_name = tx.extra_data.get('peer_name') or recipient_name
    
    sender_source = tx.from_pocket.name if tx.from_pocket else 'Wallet Balance'
    recipient_destination = tx.to_pocket.name if tx.to_pocket else 'PocketPay Wallet'
    
    qr_data_uri = generate_qr_code(build_qr_tx_url(tx), 250)

    return render_template('qr/receipt.html',
        tx=tx,
        formatted_date=formatted_date,
        sender_name=sender_name,
        recipient_name=recipient_name or 'PocketPay Member',
        sender_source=sender_source,
        recipient_destination=recipient_destination,
        qr_data_uri=qr_data_uri
    )


# =========================================================================
# JSON API Endpoints for In-App Scanner & Verification
# =========================================================================

@bp.route('/api/user/<string:user_ref>', methods=['GET'])
def api_qr_user(user_ref):
    """Fetch sanitized user details for Send Money prefill after QR scan."""
    clean_ref = re.sub(r'[\x00-\x1f\s]', '', str(user_ref)).strip()
    target_user = User.query.filter(
        (User.virtual_wallet_id == clean_ref) |
        (User.virtual_upi_id == clean_ref) |
        (User.email == clean_ref) |
        (User.phone == clean_ref)
    ).first()
    
    if not target_user:
        return jsonify({'success': False, 'error': 'PocketPay user not found or inactive'}), 404
        
    user_payload = {
        'id': target_user.id,
        'name': target_user.full_name,
        'full_name': target_user.full_name,
        'virtual_upi_id': target_user.virtual_upi_id or f"{target_user.email.split('@')[0]}@pocketpay",
        'virtual_wallet_id': target_user.virtual_wallet_id,
        'is_active': target_user.is_active
    }
    return jsonify({
        'success': True,
        'type': 'user',
        'data': user_payload,
        'user': user_payload
    })


@bp.route('/api/pocket/<string:pocket_ref>', methods=['GET'])
def api_qr_pocket(pocket_ref):
    """Fetch sanitized pocket details for in-app Pocket QR scan."""
    clean_ref = re.sub(r'[\x00-\x1f\s]', '', str(pocket_ref)).strip()
    pocket = None
    if clean_ref.isdigit():
        pocket = Pocket.query.filter_by(id=int(clean_ref), archived=False).first()
    if not pocket:
        pocket = Pocket.query.filter_by(name=clean_ref, archived=False).first()
        
    if not pocket:
        return jsonify({'success': False, 'error': 'Pocket not found or archived'}), 404
        
    owner_name = pocket.user.full_name if pocket.user else 'PocketPay Member'
    owner_upi = pocket.user.virtual_upi_id if pocket.user else ''
    
    return jsonify({
        'success': True,
        'type': 'pocket',
        'pocket': {
            'id': pocket.id,
            'name': pocket.name,
            'description': pocket.description or '',
            'icon': pocket.icon or 'wallet',
            'color': pocket.color or '#6366f1',
            'budget_amount': pocket.budget_amount or pocket.monthly_limit or 0.0,
            'owner_name': owner_name,
            'owner_upi': owner_upi
        }
    })


@bp.route('/api/transaction/<string:tx_ref>', methods=['GET'])
def api_qr_transaction(tx_ref):
    """Fetch sanitized verified transaction receipt for in-app Receipt QR scan."""
    from app.blueprints.transactions import format_transaction_receipt
    clean_ref = re.sub(r'[\x00-\x1f\s]', '', str(tx_ref)).strip()
    tx = Transaction.query.filter_by(transaction_id=clean_ref).first() or Transaction.query.filter_by(uuid=clean_ref).first()
    if not tx:
        return jsonify({'success': False, 'error': 'Transaction receipt not found'}), 404
        
    receipt = format_transaction_receipt(tx)
    return jsonify({
        'success': True,
        'type': 'transaction',
        'receipt': receipt
    })


@bp.route('/resolve', methods=['POST'])
@bp.route('/api/resolve', methods=['POST'])
def api_qr_resolve():
    """Universal resolver for all scanned PocketPay QR strings and payloads."""
    import json
    from app.services.payout_service import parse_payment_qr
    data = request.get_json() or {}
    raw_content = str(data.get('content') or data.get('qr_string') or data.get('code') or data.get('payload') or '').strip()
    
    if not raw_content:
        return jsonify({'success': False, 'error': 'Empty QR content'}), 400

    # 1. Structured JSON PocketPay QR
    if raw_content.startswith('{') and raw_content.endswith('}'):
        try:
            payload = json.loads(raw_content)
            if payload.get('app') == 'pocketpay' or payload.get('type'):
                p_type = str(payload.get('type')).lower()
                p_id = str(payload.get('id') or payload.get('ref') or '').strip()
                if p_type == 'user':
                    return api_qr_user(p_id)
                elif p_type == 'pocket':
                    return api_qr_pocket(p_id)
                elif p_type in ('transaction', 'tx'):
                    return api_qr_transaction(p_id)
        except Exception:
            pass

    # 2. Universal payment parser
    parsed = parse_payment_qr(raw_content)
    if parsed and parsed.get('valid'):
        p_type = parsed.get('type')
        if p_type == 'pocketpay_wallet':
            w_id = parsed.get('wallet_id') or raw_content
            return api_qr_user(w_id)
        elif p_type == 'pocketpay_pocket':
            pkt_id = str(parsed.get('pocket_id'))
            return api_qr_pocket(pkt_id)
        elif p_type == 'pocketpay_tx':
            tx_id = parsed.get('transaction_id')
            return api_qr_transaction(tx_id)
        elif p_type in ('upi', 'upi_qr', 'upi_id'):
            vpa = parsed.get('vpa') or ''
            # If the VPA belongs to an active PocketPay user, resolve cleanly to the user
            if vpa:
                target_user = User.query.filter(
                    (User.virtual_upi_id == vpa) |
                    (User.virtual_wallet_id == vpa) |
                    (User.email == vpa)
                ).first()
                if target_user:
                    return api_qr_user(target_user.virtual_wallet_id or target_user.virtual_upi_id)
            return jsonify({
                'success': True,
                'type': 'upi',
                'upi_data': parsed
            })

    return jsonify({'success': False, 'error': 'Unrecognized or invalid QR code format'}), 400

