from flask import Blueprint, request
from flask_login import current_user
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func
from app.extensions import db
from app.models.pocket import Pocket
from app.models.transaction import Transaction, EXPENSE_CATEGORIES
from app.models.notification import Notification
from app.models.budget import Budget
from app.services.ledger_service import LedgerService, FinancialInvariantError
from app.utils.idempotency import get_idempotency_key, check_idempotency, save_idempotency
from app.utils.helpers import (
    json_response, error_response, validate_required_fields,
    api_login_required, get_paginated_query, paginated_response, generate_qr_code,
    build_qr_tx_url
)

bp = Blueprint('transactions', __name__)


@bp.route('', methods=['GET'])
@api_login_required
def list_transactions():
    query = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.created_at.desc())
    
    tx_type = request.args.get('type')
    if tx_type:
        types = tx_type.split(',')
        query = query.filter(Transaction.type.in_(types))
    
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    
    pocket_id = request.args.get('pocket_id', type=int)
    if pocket_id:
        query = query.filter(
            or_(Transaction.from_pocket_id == pocket_id,
                Transaction.to_pocket_id == pocket_id)
        )
    
    category = request.args.get('category')
    if category:
        query = query.filter_by(category=category)
    
    search = request.args.get('search', '').strip()
    if search:
        like_pattern = f'%{search}%'
        query = query.filter(or_(
            Transaction.description.ilike(like_pattern),
            Transaction.merchant.ilike(like_pattern),
            Transaction.category.ilike(like_pattern),
            Transaction.transaction_id.ilike(like_pattern)
        ))
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Transaction.created_at >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Transaction.created_at < end_dt)
        except ValueError:
            pass
    
    min_amount = request.args.get('min_amount', type=float)
    max_amount = request.args.get('max_amount', type=float)
    if min_amount is not None:
        query = query.filter(Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Transaction.amount <= max_amount)
    
    pagination = get_paginated_query(query)
    
    summary = {
        'total_count': query.count(),
        'total_income': db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type.in_(['income', 'topup', 'refund'])
        ).scalar() or 0,
        'total_expense': db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'expense'
        ).scalar() or 0,
    }
    
    return json_response({
        **paginated_response(pagination, lambda t: t.to_dict(True)),
        'summary': summary
    })


@bp.route('/<int:tx_id>', methods=['GET'])
@api_login_required
def get_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first()
    if not tx:
        return error_response('Transaction not found', 404)
    return json_response({'transaction': tx.to_dict(True)})


def format_transaction_receipt(tx):
    sender_name = tx.user.full_name if tx.user else 'PocketPay User'
    sender_upi = tx.user.virtual_upi_id if tx.user else None
    
    recipient_name = tx.merchant or ''
    recipient_upi = None
    if tx.extra_data and isinstance(tx.extra_data, dict):
        recipient_name = tx.extra_data.get('peer_name') or recipient_name
        recipient_upi = tx.extra_data.get('peer_upi')
    
    sender_source = tx.from_pocket.name if tx.from_pocket else 'Wallet Balance'
    recipient_destination = tx.to_pocket.name if tx.to_pocket else 'PocketPay Wallet'
    
    qr_code = None
    try:
        qr_code = generate_qr_code(build_qr_tx_url(tx), 250)
    except Exception:
        qr_code = None

    return {
        'transaction_id': tx.transaction_id,
        'uuid': tx.uuid,
        'amount': tx.amount,
        'currency': tx.currency or 'INR',
        'type': tx.type,
        'status': tx.status,
        'sender': {
            'name': sender_name,
            'upi_id': sender_upi,
            'source': sender_source
        },
        'recipient': {
            'name': recipient_name or 'PocketPay Member',
            'upi_id': recipient_upi,
            'destination': recipient_destination
        },
        'category': tx.category or 'Transfer',
        'description': tx.description or '',
        'payment_method': tx.payment_method or 'pocketpay_p2p',
        'created_at': tx.created_at.isoformat() if tx.created_at else None,
        'date_formatted': tx.created_at.strftime('%d %b %Y, %I:%M %p UTC') if tx.created_at else 'Recent',
        'qr_code_url': qr_code or build_qr_tx_url(tx),
        'qr_data_uri': qr_code,
        'receipt_url': build_qr_tx_url(tx),
        'verified': True
    }


@bp.route('/<string:tx_ref>/receipt', methods=['GET'])
def get_transaction_receipt(tx_ref):
    import re
    clean_ref = re.sub(r'[\x00-\x1f\s]', '', str(tx_ref)).strip()
    if '/qr/tx/' in clean_ref:
        clean_ref = clean_ref.split('/qr/tx/')[-1].split('?')[0].split('/')[0]
    elif 'pocketpay://tx/' in clean_ref:
        clean_ref = clean_ref.split('pocketpay://tx/')[-1].split('?')[0].split('/')[0]
        
    tx = Transaction.query.filter_by(transaction_id=clean_ref).first()
    if not tx:
        tx = Transaction.query.filter_by(uuid=clean_ref).first()
    if not tx and clean_ref.isdigit():
        tx = Transaction.query.filter_by(id=int(clean_ref)).first()
        
    if not tx:
        return error_response('Transaction receipt not found or invalid reference', 404)
        
    return json_response({'receipt': format_transaction_receipt(tx)})


@bp.route('/verify-receipt', methods=['POST'])
def verify_receipt():
    import re
    data = request.get_json() or {}
    ref = data.get('ref') or data.get('content') or data.get('transaction_id') or ''
    clean_ref = re.sub(r'[\x00-\x1f\s]', '', str(ref)).strip()
    if '/qr/tx/' in clean_ref:
        clean_ref = clean_ref.split('/qr/tx/')[-1].split('?')[0].split('/')[0]
    elif 'pocketpay://tx/' in clean_ref:
        clean_ref = clean_ref.split('pocketpay://tx/')[-1].split('?')[0].split('/')[0]
        
    tx = Transaction.query.filter_by(transaction_id=clean_ref).first()
    if not tx:
        tx = Transaction.query.filter_by(uuid=clean_ref).first()
    if not tx and clean_ref.isdigit():
        tx = Transaction.query.filter_by(id=int(clean_ref)).first()
        
    if not tx:
        return error_response('Transaction receipt not found or invalid reference', 404)
        
    return json_response({'receipt': format_transaction_receipt(tx)})


@bp.route('/expense/preview', methods=['POST'])
@api_login_required
def preview_expense():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['pocket_id', 'amount'])
    if not valid:
        return error_response(msg, 400)
    
    pocket_id = data.get('pocket_id')
    amount = float(data.get('amount', 0))
    category = data.get('category', '')
    description = data.get('description', '').strip()
    merchant = data.get('merchant', '').strip()
    
    if amount <= 0:
        return error_response('Amount must be positive', 400)
    
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id, archived=False).first()
    if not pocket:
        return error_response('Selected pocket not found', 404)
    
    can_afford = pocket.current_balance >= amount
    balance_after = round(pocket.current_balance - amount, 2) if can_afford else pocket.current_balance
    
    alternate_pockets = []
    if not can_afford:
        alternate_pockets = [
            p.to_dict() for p in Pocket.query.filter_by(
                user_id=current_user.id, archived=False
            ).filter(Pocket.current_balance >= amount, Pocket.id != pocket_id)\
            .order_by(Pocket.current_balance.desc()).all()
        ]
    
    monthly_spent = pocket.monthly_spending()
    new_monthly_spent = round(monthly_spent + amount, 2)
    budget_impact = None
    
    if pocket.monthly_limit and pocket.monthly_limit > 0:
        current_pct = (monthly_spent / pocket.monthly_limit) * 100
        new_pct = min(100, (new_monthly_spent / pocket.monthly_limit) * 100)
        budget_impact = {
            'monthly_limit': pocket.monthly_limit,
            'current_spent': monthly_spent,
            'new_spent': new_monthly_spent,
            'current_usage_percent': round(current_pct, 1),
            'new_usage_percent': round(new_pct, 1),
            'remaining': max(0, round(pocket.monthly_limit - new_monthly_spent, 2)),
            'will_exceed_limit': new_monthly_spent > pocket.monthly_limit
        }
    
    if pocket.budget_amount and pocket.budget_amount > 0:
        budget_pct = (pocket.total_spent / pocket.budget_amount) * 100
        new_budget_pct = min(100, ((pocket.total_spent + amount) / pocket.budget_amount) * 100)
        budget_impact = budget_impact or {}
        budget_impact.update({
            'total_budget': pocket.budget_amount,
            'total_spent_before': pocket.total_spent,
            'total_spent_after': round(pocket.total_spent + amount, 2),
            'budget_usage_before': round(budget_pct, 1),
            'budget_usage_after': round(new_budget_pct, 1),
            'will_exceed_budget': (pocket.total_spent + amount) > pocket.budget_amount
        })
    
    return json_response({
        'can_afford': can_afford,
        'pocket': pocket.to_dict(),
        'amount': amount,
        'balance_before': pocket.current_balance,
        'balance_after': balance_after,
        'category': category or 'Custom',
        'description': description,
        'merchant': merchant,
        'alternate_pockets': alternate_pockets if not can_afford else [],
        'budget_impact': budget_impact,
        'available_options': {
            'can_proceed': can_afford,
            'can_choose_other_pocket': len(alternate_pockets) > 0,
            'can_transfer': True
        },
        'available_categories': EXPENSE_CATEGORIES
    })


@bp.route('/expense/execute', methods=['POST'])
@api_login_required
def execute_expense():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['pocket_id', 'amount', 'pin'])
    if not valid:
        return error_response(msg, 400)
    
    pocket_id = data.get('pocket_id')
    try:
        amount = round(float(data.get('amount', 0)), 2)
    except (ValueError, TypeError):
        return error_response('Invalid amount', 400)

    pin = str(data.get('pin', ''))
    category = data.get('category', 'Custom')
    description = data.get('description', '').strip() or None
    merchant = data.get('merchant', '').strip() or None
    tags = data.get('tags', [])
    extra_data = data.get('extra_data', data.get('metadata', {})) or {}
    
    if amount <= 0:
        return error_response('Amount must be positive', 400)
    
    if not current_user.transaction_pin_hash:
        return error_response(
            'Transaction PIN not set. Please set up your PIN first.',
            400,
            code='PIN_NOT_SET'
        )
    
    success, error = current_user.verify_transaction_pin(pin)
    if not success:
        return error_response(
            error or 'Incorrect PIN',
            401,
            code='INCORRECT_PIN',
            pin_attempts=current_user.pin_attempts,
            pin_locked_until=current_user.pin_locked_until.isoformat() if current_user.pin_locked_until else None
        )
        
    # 2FA TOTP verification
    if current_user.totp_enabled:
        totp_code = data.get('totp_code') or data.get('totp') or data.get('otp')
        verified, err, err_code = current_user.verify_totp(totp_code)
        if not verified:
            return error_response(err or 'Invalid Authenticator 2FA code', 401, code=err_code or 'INCORRECT_TOTP')
    
    # Idempotency
    idemp_key = get_idempotency_key(request, data)
    idemp_rec = None
    if idemp_key:
        idemp_rec, cached_resp = check_idempotency(idemp_key, '/api/transactions/expense/execute', current_user.id, data)
        if cached_resp:
            resp_body, resp_code = cached_resp
            return json_response(resp_body.get('data'), resp_body.get('message'), resp_code)

    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id, archived=False).first()
    if not pocket:
        return error_response('Selected pocket not found', 404)
    
    if float(pocket.current_balance or 0) < amount:
        other_pockets = Pocket.query.filter_by(
            user_id=current_user.id, archived=False
        ).filter(Pocket.current_balance >= amount, Pocket.id != pocket_id)\
        .order_by(Pocket.current_balance.desc()).all()
        
        return error_response(
            f'Your {pocket.name} Pocket has only ₹{float(pocket.current_balance or 0):.2f} remaining.',
            400,
            code='INSUFFICIENT_BALANCE',
            pocket_balance=float(pocket.current_balance or 0),
            required_amount=amount,
            shortage=round(amount - float(pocket.current_balance or 0), 2),
            pocket={
                'id': pocket.id,
                'name': pocket.name,
                'color': pocket.color,
                'icon': pocket.icon
            },
            alternate_pockets=[p.to_dict() for p in other_pockets],
            options_available={
                'choose_other_pocket': len(other_pockets) > 0,
                'transfer_money': True,
                'cancel_payment': True
            }
        )
    
    try:
        pocket.current_balance = round(float(pocket.current_balance or 0) - amount, 2)
        pocket.total_spent = round(float(pocket.total_spent or 0) + amount, 2)
        db.session.flush()
        
        tx = Transaction(
            transaction_id=Transaction.generate_transaction_id(),
            user_id=current_user.id,
            type='expense',
            status='pending',
            amount=amount,
            from_pocket_id=pocket.id,
            category=category,
            merchant=merchant,
            description=description,
            payment_method=data.get('payment_method', 'pocket'),
            tags=tags,
            extra_data=extra_data
        )
        db.session.add(tx)
        db.session.flush()
        
        tx.qr_code_url = generate_qr_code(build_qr_tx_url(tx), 200)
        
        tx.complete()
        
        budgets = Budget.query.filter_by(
            user_id=current_user.id, is_active=True
        ).filter(or_(
            Budget.pocket_id == pocket.id,
            Budget.pocket_id.is_(None)
        )).all()
        
        for b in budgets:
            b.check_and_send_alerts()
        
        if pocket.current_balance < (pocket.monthly_limit * 0.1 if pocket.monthly_limit else 500):
            if pocket.current_balance > 0 and pocket.current_balance < 1000:
                Notification.low_balance_alert(current_user.id, pocket)
        
        Notification.transaction_alert(current_user.id, tx)
        
        db.session.commit()
        
        resp_data = {
            'transaction': tx.to_dict(True),
            'pocket_balance': pocket.current_balance,
            'receipt_qr': tx.qr_code_url,
            'budget_alerts_triggered': len(budgets)
        }

        if idemp_rec:
            save_idempotency(idemp_rec, {'data': resp_data, 'message': f'Payment of ₹{amount:.2f} successful'}, 201)

        return json_response(resp_data, f'Payment of ₹{amount:.2f} successful', 201)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Payment failed: {str(e)}', 500)


@bp.route('/pay-pocket', methods=['POST'])
@api_login_required
def pay_from_pocket():
    """
    Parts 2 & 3: Pay directly from an authenticated user's Pocket.
    Validates ownership server-side, checks sufficient funds, checks PIN & limits,
    executes atomic database debit, generates dual ledger records, and returns receipt.
    """
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['pocket_id', 'amount'])
    if not valid:
        return error_response(msg, 400)

    pocket_id = data.get('pocket_id')
    try:
        amount = round(float(data.get('amount', 0)), 2)
    except (ValueError, TypeError):
        return error_response('Invalid payment amount', 400)

    recipient = str(data.get('recipient', '')).strip()
    note = str(data.get('note', data.get('description', ''))).strip()
    pin = str(data.get('pin', '')).strip()

    if amount <= 0:
        return error_response('Payment amount must be greater than zero', 400)

    if getattr(current_user, 'transfer_frozen', False):
        return error_response('Transfers are currently frozen on your account. Unfreeze in Security Centre.', 403, code='TRANSFERS_FROZEN')

    tx_limit = float(getattr(current_user, 'transaction_limit', 100000.0) or 100000.0)
    if amount > tx_limit:
        return error_response(f'Payment exceeds your transaction limit of ₹{tx_limit:,.2f}', 400, code='LIMIT_EXCEEDED')

    # Security PIN verification
    if current_user.transaction_pin_hash:
        if not pin:
            return error_response('Security PIN is required to authorize payment', 400, code='PIN_REQUIRED')
        success, error = current_user.verify_transaction_pin(pin)
        if not success:
            return error_response(error or 'Incorrect security PIN', 401, code='INCORRECT_PIN')

    # 2FA TOTP verification
    if current_user.totp_enabled:
        totp_code = data.get('totp_code') or data.get('totp') or data.get('otp')
        verified, err, err_code = current_user.verify_totp(totp_code)
        if not verified:
            return error_response(err or 'Invalid Authenticator 2FA code', 401, code=err_code or 'INCORRECT_TOTP')

    # Idempotency check
    idemp_key = get_idempotency_key(request, data)
    idemp_rec = None
    if idemp_key:
        idemp_rec, cached_resp = check_idempotency(idemp_key, '/api/transactions/pay-pocket', current_user.id, data)
        if cached_resp:
            resp_body, resp_code = cached_resp
            return json_response(resp_body.get('data'), resp_body.get('message'), resp_code)

    # Server-side pocket ownership validation (CRITICAL)
    pocket = Pocket.query.filter_by(id=pocket_id).first()
    if not pocket:
        return error_response('Selected pocket not found', 404, code='POCKET_NOT_FOUND')
    if pocket.user_id != current_user.id:
        return error_response('You do not have permission to spend from this pocket', 403, code='FORBIDDEN')
    if pocket.archived:
        return error_response('Selected pocket has been archived', 400, code='POCKET_ARCHIVED')

    available_balance = float(pocket.current_balance or 0.0)
    if available_balance < amount:
        return error_response(
            f'Insufficient funds in {pocket.name}. Available: ₹{available_balance:,.2f}, required: ₹{amount:,.2f}.',
            400,
            code='INSUFFICIENT_BALANCE',
            available_balance=available_balance,
            required_amount=amount,
            shortage=round(amount - available_balance, 2)
        )

    try:
        # Atomic deduction
        pocket.current_balance = round(available_balance - amount, 2)
        pocket.total_spent = round(float(pocket.total_spent or 0.0) + amount, 2)
        db.session.flush()

        # Check if recipient matches an existing PocketPay user
        from app.models.user import User
        recipient_user = None
        if recipient:
            all_other = User.query.filter(User.id != current_user.id).all()
            clean_rec = recipient.strip().lower()
            for u in all_other:
                if (u.virtual_wallet_id and u.virtual_wallet_id.lower() == clean_rec) or \
                   (u.virtual_upi_id and u.virtual_upi_id.lower() == clean_rec) or \
                   (u.phone and u.phone.replace(' ', '') == recipient.replace(' ', '')) or \
                   (u.full_name.strip().lower() == clean_rec) or \
                   (u.email.strip().lower() == clean_rec):
                    recipient_user = u
                    break

        recipient_tx = None
        if recipient_user:
            recipient_user.wallet_balance = round(float(recipient_user.wallet_balance or 0.0) + amount, 2)
            recipient_tx = Transaction(
                transaction_id=Transaction.generate_transaction_id(),
                user_id=recipient_user.id,
                type='peer_receive',
                amount=amount,
                category='Payment',
                merchant=current_user.full_name,
                description=f'Payment received from {current_user.full_name}' + (f': {note}' if note else ''),
                payment_method='pocket_payment',
                status='completed',
                completed_at=datetime.utcnow(),
                extra_data={'sender_user_id': current_user.id, 'sender_name': current_user.full_name, 'from_pocket': pocket.name}
            )
            db.session.add(recipient_tx)
            db.session.flush()
            recipient_tx.qr_code_url = generate_qr_code(build_qr_tx_url(recipient_tx), 200)
            Notification.transaction_alert(recipient_user.id, recipient_tx)

        # Create sender transaction
        tx = Transaction(
            transaction_id=Transaction.generate_transaction_id(),
            user_id=current_user.id,
            type='expense',
            source_type='pocket',
            source_id=str(pocket.id),
            amount=amount,
            from_pocket_id=pocket.id,
            category=data.get('category', 'Payment'),
            merchant=recipient or 'Merchant / Recipient',
            description=note or f'Payment to {recipient or "Recipient"} from {pocket.name}',
            payment_method='pocket_payment',
            status='completed',
            completed_at=datetime.utcnow(),
            extra_data={
                'source': 'pocket',
                'source_pocket_id': pocket.id,
                'source_pocket_name': pocket.name,
                'recipient': recipient,
                'recipient_user_id': recipient_user.id if recipient_user else None,
                'balance_before': available_balance,
                'balance_after': pocket.current_balance
            }
        )
        db.session.add(tx)
        db.session.flush()
        tx.qr_code_url = generate_qr_code(build_qr_tx_url(tx), 200)

        # Dual ledger entry
        try:
            from app.services.ledger_service import LedgerService
            LedgerService.record_entry(
                user_id=current_user.id,
                transaction_id=tx.id,
                entry_type='DEBIT',
                amount=amount,
                source_type='pocket',
                source_id=pocket.id,
                description=f'Payment of ₹{amount:,.2f} from {pocket.name}'
            )
            if recipient_user and recipient_tx:
                LedgerService.record_entry(
                    user_id=recipient_user.id,
                    transaction_id=recipient_tx.id,
                    entry_type='CREDIT',
                    amount=amount,
                    source_type='wallet',
                    source_id=recipient_user.id,
                    description=f'Payment of ₹{amount:,.2f} from {current_user.full_name}'
                )
        except Exception:
            pass

        Notification.transaction_alert(current_user.id, tx)
        db.session.commit()

        resp_data = {
            'transaction_id': tx.transaction_id,
            'amount': amount,
            'source_pocket_id': pocket.id,
            'source_pocket_name': pocket.name,
            'available_before': available_balance,
            'remaining_balance': pocket.current_balance,
            'recipient': recipient,
            'payment_method': 'pocket_payment',
            'status': 'completed',
            'timestamp': tx.completed_at.isoformat(),
            'receipt_qr': tx.qr_code_url,
            'transaction': tx.to_dict(True)
        }

        if idemp_rec:
            save_idempotency(idemp_rec, {'data': resp_data, 'message': f'Payment of ₹{amount:,.2f} from {pocket.name} confirmed.'}, 201)

        return json_response(resp_data, f'Payment of ₹{amount:,.2f} from {pocket.name} successful.', 201)

    except Exception as e:
        db.session.rollback()
        return error_response(f'Payment failed: {str(e)}', 500)


@bp.route('/pay-balance', methods=['POST'])
@api_login_required
def pay_from_balance():
    """
    Pay directly from PocketPay Available Wallet Balance.
    """
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['amount'])
    if not valid:
        return error_response(msg, 400)

    try:
        amount = round(float(data.get('amount', 0)), 2)
    except (ValueError, TypeError):
        return error_response('Invalid payment amount', 400)

    recipient = str(data.get('recipient', '')).strip()
    note = str(data.get('note', data.get('description', ''))).strip()
    pin = str(data.get('pin', '')).strip()

    if amount <= 0:
        return error_response('Payment amount must be greater than zero', 400)

    if getattr(current_user, 'transfer_frozen', False):
        return error_response('Transfers are currently frozen on your account. Unfreeze in Security Centre.', 403, code='TRANSFERS_FROZEN')

    tx_limit = float(getattr(current_user, 'transaction_limit', 100000.0) or 100000.0)
    if amount > tx_limit:
        return error_response(f'Payment exceeds your transaction limit of ₹{tx_limit:,.2f}', 400, code='LIMIT_EXCEEDED')

    if current_user.transaction_pin_hash:
        if not pin:
            return error_response('Security PIN is required to authorize payment', 400, code='PIN_REQUIRED')
        success, error = current_user.verify_transaction_pin(pin)
        if not success:
            return error_response(error or 'Incorrect security PIN', 401, code='INCORRECT_PIN')

    if current_user.totp_enabled:
        totp_code = data.get('totp_code') or data.get('totp') or data.get('otp')
        verified, err, err_code = current_user.verify_totp(totp_code)
        if not verified:
            return error_response(err or 'Invalid Authenticator 2FA code', 401, code=err_code or 'INCORRECT_TOTP')

    idemp_key = get_idempotency_key(request, data)
    idemp_rec = None
    if idemp_key:
        idemp_rec, cached_resp = check_idempotency(idemp_key, '/api/transactions/pay-balance', current_user.id, data)
        if cached_resp:
            resp_body, resp_code = cached_resp
            return json_response(resp_body.get('data'), resp_body.get('message'), resp_code)

    available_balance = float(current_user.wallet_balance or 0.0)
    if available_balance < amount:
        return error_response(
            f'Insufficient PocketPay balance. Available: ₹{available_balance:,.2f}, required: ₹{amount:,.2f}.',
            400,
            code='INSUFFICIENT_BALANCE',
            available_balance=available_balance,
            required_amount=amount,
            shortage=round(amount - available_balance, 2)
        )

    try:
        current_user.wallet_balance = round(available_balance - amount, 2)
        db.session.flush()

        from app.models.user import User
        recipient_user = None
        if recipient:
            all_other = User.query.filter(User.id != current_user.id).all()
            clean_rec = recipient.strip().lower()
            for u in all_other:
                if (u.virtual_wallet_id and u.virtual_wallet_id.lower() == clean_rec) or \
                   (u.virtual_upi_id and u.virtual_upi_id.lower() == clean_rec) or \
                   (u.phone and u.phone.replace(' ', '') == recipient.replace(' ', '')) or \
                   (u.full_name.strip().lower() == clean_rec) or \
                   (u.email.strip().lower() == clean_rec):
                    recipient_user = u
                    break

        recipient_tx = None
        if recipient_user:
            recipient_user.wallet_balance = round(float(recipient_user.wallet_balance or 0.0) + amount, 2)
            recipient_tx = Transaction(
                transaction_id=Transaction.generate_transaction_id(),
                user_id=recipient_user.id,
                type='peer_receive',
                amount=amount,
                category='Payment',
                merchant=current_user.full_name,
                description=f'Payment received from {current_user.full_name}' + (f': {note}' if note else ''),
                payment_method='wallet_balance',
                status='completed',
                completed_at=datetime.utcnow(),
                extra_data={'sender_user_id': current_user.id, 'sender_name': current_user.full_name}
            )
            db.session.add(recipient_tx)
            db.session.flush()
            recipient_tx.qr_code_url = generate_qr_code(build_qr_tx_url(recipient_tx), 200)
            Notification.transaction_alert(recipient_user.id, recipient_tx)

        tx = Transaction(
            transaction_id=Transaction.generate_transaction_id(),
            user_id=current_user.id,
            type='expense',
            source_type='wallet',
            amount=amount,
            category=data.get('category', 'Payment'),
            merchant=recipient or 'Merchant / Recipient',
            description=note or f'Payment to {recipient or "Recipient"} via PocketPay Balance',
            payment_method='wallet_balance',
            status='completed',
            completed_at=datetime.utcnow(),
            extra_data={
                'source': 'wallet',
                'recipient': recipient,
                'recipient_user_id': recipient_user.id if recipient_user else None,
                'balance_before': available_balance,
                'balance_after': current_user.wallet_balance
            }
        )
        db.session.add(tx)
        db.session.flush()
        tx.qr_code_url = generate_qr_code(build_qr_tx_url(tx), 200)

        try:
            from app.services.ledger_service import LedgerService
            LedgerService.record_entry(
                user_id=current_user.id,
                transaction_id=tx.id,
                entry_type='DEBIT',
                amount=amount,
                source_type='wallet',
                source_id=current_user.id,
                description=f'Payment of ₹{amount:,.2f} via PocketPay Balance'
            )
            if recipient_user and recipient_tx:
                LedgerService.record_entry(
                    user_id=recipient_user.id,
                    transaction_id=recipient_tx.id,
                    entry_type='CREDIT',
                    amount=amount,
                    source_type='wallet',
                    source_id=recipient_user.id,
                    description=f'Payment of ₹{amount:,.2f} from {current_user.full_name}'
                )
        except Exception:
            pass

        Notification.transaction_alert(current_user.id, tx)
        db.session.commit()

        resp_data = {
            'transaction_id': tx.transaction_id,
            'amount': amount,
            'available_before': available_balance,
            'remaining_balance': current_user.wallet_balance,
            'recipient': recipient,
            'payment_method': 'wallet_balance',
            'status': 'completed',
            'timestamp': tx.completed_at.isoformat(),
            'receipt_qr': tx.qr_code_url,
            'transaction': tx.to_dict(True)
        }

        if idemp_rec:
            save_idempotency(idemp_rec, {'data': resp_data, 'message': f'Payment of ₹{amount:,.2f} confirmed.'}, 201)

        return json_response(resp_data, f'Payment of ₹{amount:,.2f} from PocketPay Balance successful.', 201)

    except Exception as e:
        db.session.rollback()
        return error_response(f'Payment failed: {str(e)}', 500)


@bp.route('/transfer', methods=['POST'])
@api_login_required
def process_transfer():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['from_pocket_id', 'to_pocket_id', 'amount', 'pin'])
    if not valid:
        return error_response(msg, 400)
    
    from_id = data.get('from_pocket_id')
    to_id = data.get('to_pocket_id')
    try:
        amount = round(float(data.get('amount', 0)), 2)
    except (ValueError, TypeError):
        return error_response('Invalid amount', 400)

    pin = str(data.get('pin', ''))
    
    if amount <= 0:
        return error_response('Amount must be positive', 400)
    if from_id == to_id:
        return error_response('Cannot transfer to the same pocket', 400)
    
    if not current_user.transaction_pin_hash:
        return error_response('Please set up a transaction PIN first.', 400, code='PIN_NOT_SET')
    
    success, error = current_user.verify_transaction_pin(pin)
    if not success:
        return error_response(
            error or 'Incorrect PIN',
            401,
            code='INCORRECT_PIN',
            pin_attempts=current_user.pin_attempts,
            pin_locked_until=current_user.pin_locked_until.isoformat() if current_user.pin_locked_until else None
        )
        
    # 2FA TOTP verification
    if current_user.totp_enabled:
        totp_code = data.get('totp_code') or data.get('totp') or data.get('otp')
        if not totp_code:
            return error_response('Google Authenticator 2FA code is required', 400, code='TOTP_REQUIRED')
        verified, err, err_code = current_user.verify_totp(totp_code)
        if not verified:
            return error_response(err or 'Invalid Authenticator 2FA code', 401, code=err_code or 'INCORRECT_TOTP')
    
    # Idempotency
    idemp_key = get_idempotency_key(request, data)
    idemp_rec = None
    if idemp_key:
        idemp_rec, cached_resp = check_idempotency(idemp_key, '/api/transactions/transfer', current_user.id, data)
        if cached_resp:
            resp_body, resp_code = cached_resp
            return json_response(resp_body.get('data'), resp_body.get('message'), resp_code)

    from_pocket = Pocket.query.filter_by(id=from_id, user_id=current_user.id, archived=False).first()
    to_pocket = Pocket.query.filter_by(id=to_id, user_id=current_user.id, archived=False).first()
    
    if not from_pocket:
        return error_response('Source pocket not found', 404)
    if not to_pocket:
        return error_response('Destination pocket not found', 404)
    
    note = data.get('description', '').strip() or f'Transfer: {from_pocket.name} → {to_pocket.name}'

    try:
        res = LedgerService.transfer_between_pockets(
            user=current_user,
            from_pocket=from_pocket,
            to_pocket=to_pocket,
            amount=amount,
            note=note,
            idempotency_key=idemp_key
        )

        tx = res['transaction']
        receipt_qr = generate_qr_code(build_qr_tx_url(tx), 250) or tx.qr_code_url

        resp_data = {
            'transaction': tx.to_dict(True),
            'qr_code_url': receipt_qr,
            'receipt_qr': receipt_qr,
            'from_pocket_balance': from_pocket.current_balance,
            'to_pocket_balance': to_pocket.current_balance
        }

        if idemp_rec:
            save_idempotency(idemp_rec, {'data': resp_data, 'message': f'₹{amount:.2f} transferred successfully'}, 201)

        return json_response(resp_data, f'₹{amount:.2f} transferred successfully', 201)
        
    except FinancialInvariantError as fe:
        return error_response(str(fe), 400, code='INSUFFICIENT_BALANCE')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Transfer failed: {str(e)}', 500)


@bp.route('/timeline', methods=['GET'])
@api_login_required
def get_transaction_timeline():
    now = datetime.utcnow()
    months = int(request.args.get('months', 6))
    
    timeline_data = {}
    
    for m in range(months):
        month_date = now - timedelta(days=m * 30)
        month_key = month_date.strftime('%Y-%m')
        month_start = datetime(month_date.year, month_date.month, 1)
        if month_date.month == 12:
            month_end = datetime(month_date.year + 1, 1, 1)
        else:
            month_end = datetime(month_date.year, month_date.month + 1, 1)
        
        txs = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.created_at >= month_start,
            Transaction.created_at < month_end,
            Transaction.status == 'completed'
        ).order_by(Transaction.created_at.desc()).all()
        
        income = sum(t.amount for t in txs if t.type in ('income', 'topup', 'refund'))
        expense = sum(t.amount for t in txs if t.type == 'expense')
        
        by_category = {}
        for t in txs:
            if t.type == 'expense':
                cat = t.category or 'Other'
                if cat not in by_category:
                    by_category[cat] = 0
                by_category[cat] += t.amount
        
        by_pocket = {}
        for t in txs:
            pid = t.from_pocket_id or t.to_pocket_id
            if pid:
                p = Pocket.query.filter_by(id=pid, user_id=current_user.id).first()
                if p:
                    if pid not in by_pocket:
                        by_pocket[pid] = {
                            'pocket_id': p.id,
                            'name': p.name,
                            'color': p.color,
                            'icon': p.icon,
                            'spent': 0,
                            'received': 0
                        }
                    if t.type == 'expense' and t.from_pocket_id == pid:
                        by_pocket[pid]['spent'] += t.amount
                    elif t.type in ('income', 'topup', 'refund') and t.to_pocket_id == pid:
                        by_pocket[pid]['received'] += t.amount
        
        timeline_data[month_key] = {
            'month': month_date.strftime('%B %Y'),
            'month_short': month_date.strftime('%b %y'),
            'date': month_key,
            'income': round(income, 2),
            'expense': round(expense, 2),
            'net_savings': round(income - expense, 2),
            'transaction_count': len(txs),
            'by_category': {k: round(v, 2) for k, v in by_category.items()},
            'by_pocket': {
                k: {**v, 'spent': round(v['spent'], 2), 'received': round(v['received'], 2)}
                for k, v in by_pocket.items()
            },
            'transactions': [t.to_dict(True) for t in txs[:20]]
        }
    
    return json_response({
        'timeline': timeline_data,
        'months_covered': months
    })


@bp.route('/<int:tx_id>/refund', methods=['POST'])
@api_login_required
def refund_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first()
    if not tx:
        return error_response('Transaction not found', 404)
    
    if tx.type != 'expense' or tx.status != 'completed':
        return error_response('Only completed expense transactions can be refunded', 400)
    
    pin = str((request.get_json() or {}).get('pin', ''))
    if not current_user.transaction_pin_hash:
        return error_response('PIN not set', 400)
    success, error = current_user.verify_transaction_pin(pin)
    if not success:
        return error_response(error or 'Incorrect PIN', 401)
    
    pocket = tx.from_pocket
    if pocket:
        pocket.current_balance = round(pocket.current_balance + tx.amount, 2)
        pocket.total_spent = round(max(0, pocket.total_spent - tx.amount), 2)
    
    refund_tx = Transaction(
        transaction_id=Transaction.generate_transaction_id(),
        user_id=current_user.id,
        type='refund',
        amount=tx.amount,
        to_pocket_id=tx.from_pocket_id,
        category=tx.category,
        merchant=tx.merchant,
        description=f'Refund for: {tx.description or tx.transaction_id}',
        payment_method='refund',
        extra_data={'refund_of_tx_id': tx.id}
    )
    db.session.add(refund_tx)
    refund_tx.complete()
    db.session.commit()
    
    Notification.transaction_alert(current_user.id, refund_tx)
    
    return json_response({
        'refund_transaction': refund_tx.to_dict(True),
        'original_transaction_id': tx.transaction_id
    }, f'₹{tx.amount:.2f} refunded successfully', 201)


@bp.route('/search', methods=['GET'])
@api_login_required
def search_transactions():
    query = request.args.get('q', '').strip()
    if not query:
        return json_response({'results': [], 'count': 0})
    
    like = f'%{query}%'
    results = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        or_(
            Transaction.description.ilike(like),
            Transaction.merchant.ilike(like),
            Transaction.category.ilike(like),
            Transaction.transaction_id.ilike(like),
            Transaction.upi_reference.ilike(like)
        )
    ).order_by(Transaction.created_at.desc()).limit(50).all()
    
    return json_response({
        'results': [t.to_dict(True) for t in results],
        'count': len(results),
        'query': query
    })


@bp.route('/recurring/suggestions', methods=['GET'])
@api_login_required
def get_recurring_suggestions():
    txs = Transaction.query.filter_by(
        user_id=current_user.id, type='expense', status='completed'
    ).order_by(Transaction.created_at.desc()).all()
    
    merchant_groups = {}
    for tx in txs:
        key = (tx.merchant or tx.category, tx.category or 'Other')
        if key not in merchant_groups:
            merchant_groups[key] = {'count': 0, 'total': 0, 'transactions': [], 'category': key[1]}
        merchant_groups[key]['count'] += 1
        merchant_groups[key]['total'] += tx.amount
        merchant_groups[key]['transactions'].append(tx.created_at)
    
    recurring = []
    for (merchant, _), data in merchant_groups.items():
        if data['count'] >= 2:
            avg = data['total'] / data['count']
            recurring.append({
                'merchant': merchant or 'Unknown',
                'category': data['category'],
                'transaction_count': data['count'],
                'total_spent': round(data['total'], 2),
                'average_amount': round(avg, 2),
                'suggested_budget': round(avg * 1.1, 2),
                'is_likely_recurring': data['count'] >= 3
            })
    
    recurring.sort(key=lambda x: -x['total_spent'])
    
    return json_response({
        'suggestions': recurring[:20],
        'total_detected': len(recurring)
    })


@bp.route('/<int:tx_id>', methods=['PUT'])
@api_login_required
def update_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first()
    if not tx:
        return error_response('Transaction not found', 404)
    
    data = request.get_json() or {}
    
    if 'description' in data:
        tx.description = (str(data['description']).strip() or None) if data['description'] else None
    if 'merchant' in data:
        tx.merchant = (str(data['merchant']).strip() or None) if data['merchant'] else None
    if 'category' in data and data['category']:
        tx.category = str(data['category']).strip()
    if 'tags' in data and isinstance(data['tags'], list):
        tx.tags = data['tags']
        
    if 'amount' in data and data['amount'] is not None:
        try:
            new_amount = float(data['amount'])
            if new_amount <= 0:
                return error_response('Amount must be positive', 400)
            if new_amount != tx.amount:
                diff = round(new_amount - tx.amount, 2)
                if tx.type == 'expense' and tx.from_pocket_id:
                    pocket = Pocket.query.filter_by(id=tx.from_pocket_id, user_id=current_user.id).first()
                    if pocket:
                        if diff > 0 and pocket.current_balance < diff:
                            return error_response(f'Insufficient balance in {pocket.name} to increase amount by ₹{diff:.2f}', 400)
                        pocket.current_balance = round(pocket.current_balance - diff, 2)
                        pocket.total_spent = max(0, round(pocket.total_spent + diff, 2))
                elif tx.type == 'income' and tx.to_pocket_id:
                    pocket = Pocket.query.filter_by(id=tx.to_pocket_id, user_id=current_user.id).first()
                    if pocket:
                        if diff < 0 and pocket.current_balance < abs(diff):
                            return error_response(f'Cannot decrease income by ₹{abs(diff):.2f}, pocket balance is only ₹{pocket.current_balance:.2f}', 400)
                        pocket.current_balance = round(pocket.current_balance + diff, 2)
                        pocket.total_received = max(0, round(pocket.total_received + diff, 2))
                tx.amount = new_amount
        except (ValueError, TypeError):
            return error_response('Invalid amount format', 400)

    tx.updated_at = datetime.utcnow()
    db.session.commit()
    
    return json_response({'transaction': tx.to_dict(True)}, 'Transaction updated successfully')


@bp.route('/<int:tx_id>', methods=['DELETE'])
@api_login_required
def delete_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first()
    if not tx:
        return error_response('Transaction not found', 404)
    
    # Reverse balances atomically
    if tx.status == 'completed':
        if tx.type == 'expense':
            if tx.from_pocket_id:
                pocket = Pocket.query.filter_by(id=tx.from_pocket_id, user_id=current_user.id).first()
                if pocket:
                    pocket.current_balance = round(pocket.current_balance + tx.amount, 2)
                    pocket.total_spent = max(0, round(pocket.total_spent - tx.amount, 2))
            if tx.payment_method == 'wallet':
                current_user.wallet_balance = round(current_user.wallet_balance + tx.amount, 2)
        elif tx.type == 'income':
            if tx.to_pocket_id:
                pocket = Pocket.query.filter_by(id=tx.to_pocket_id, user_id=current_user.id).first()
                if pocket:
                    pocket.current_balance = max(0, round(pocket.current_balance - tx.amount, 2))
                    pocket.total_received = max(0, round(pocket.total_received - tx.amount, 2))
        elif tx.type == 'transfer':
            if tx.from_pocket_id:
                from_p = Pocket.query.filter_by(id=tx.from_pocket_id, user_id=current_user.id).first()
                if from_p:
                    from_p.current_balance = round(from_p.current_balance + tx.amount, 2)
            if tx.to_pocket_id:
                to_p = Pocket.query.filter_by(id=tx.to_pocket_id, user_id=current_user.id).first()
                if to_p:
                    to_p.current_balance = max(0, round(to_p.current_balance - tx.amount, 2))
        elif tx.type == 'topup':
            current_user.wallet_balance = max(0, round(current_user.wallet_balance - tx.amount, 2))

    tx_id_str = tx.transaction_id
    db.session.delete(tx)
    db.session.commit()
    
    return json_response({'deleted': True, 'transaction_id': tx_id_str}, 'Transaction deleted successfully')
