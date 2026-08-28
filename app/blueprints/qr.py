from flask import Blueprint, request, render_template, redirect, url_for, jsonify
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.utils.helpers import get_public_base_url
import re

bp = Blueprint('qr', __name__, url_prefix='/qr')


@bp.route('/pay')
@bp.route('/wallet/<string:wallet_id>')
def qr_pay_destination(wallet_id=None):
    """
    Universal mobile & desktop destination for User / Wallet / UPI QR code scans.
    Scannable with standard camera, Google Lens, or in-app scanner.
    """
    upi_id = request.args.get('user') or request.args.get('upi_id') or ''
    user_name = request.args.get('name') or ''
    
    target_user = None
    if wallet_id:
        clean_wallet_id = re.sub(r'[\x00-\x1f\s]', '', str(wallet_id)).strip()
        target_user = User.query.filter_by(virtual_wallet_id=clean_wallet_id).first()
    elif upi_id:
        clean_upi_id = re.sub(r'[\x00-\x1f\s]', '', str(upi_id)).strip()
        target_user = User.query.filter_by(virtual_upi_id=clean_upi_id).first()
        if not target_user and '@' in clean_upi_id:
            target_user = User.query.filter_by(email=clean_upi_id).first()
            
    if target_user:
        recipient_name = target_user.full_name or 'PocketPay User'
        resolved_upi_id = target_user.virtual_upi_id or f"{target_user.email.split('@')[0]}@pocketpay"
        resolved_wallet_id = target_user.virtual_wallet_id
    elif upi_id or user_name:
        recipient_name = user_name or upi_id.split('@')[0].capitalize()
        resolved_upi_id = upi_id
        resolved_wallet_id = wallet_id
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

    formatted_date = tx.created_at.strftime('%d %b %Y, %I:%M %p UTC') if tx.created_at else 'Recent'

    return render_template('qr/receipt.html',
        tx=tx,
        formatted_date=formatted_date
    )
