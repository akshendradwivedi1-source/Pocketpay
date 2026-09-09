import re
from flask import Blueprint, request
from flask_login import current_user
from datetime import datetime, timedelta
from app.extensions import db
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction, EXPENSE_CATEGORIES
from app.models.distribution_rule import DistributionRule
from app.models.notification import Notification
from app.models.money_request import MoneyRequest
from app.services.ledger_service import LedgerService, FinancialInvariantError
from app.utils.idempotency import get_idempotency_key, check_idempotency, save_idempotency
from app.utils.helpers import (
    json_response, error_response, validate_required_fields,
    api_login_required, get_paginated_query, paginated_response, generate_qr_code,
    build_qr_tx_url
)

bp = Blueprint('wallet', __name__)


@bp.route('/balance', methods=['GET'])
@api_login_required
def get_wallet_balance():
    pockets = Pocket.query.filter_by(user_id=current_user.id, archived=False).all()
    pocket_balance = round(sum(float(p.current_balance or 0.0) for p in pockets), 2)
    wallet_balance = round(float(current_user.wallet_balance or 0.0), 2)
    total_funds = round(wallet_balance + pocket_balance, 2)
    
    # Calculate start of current month and start of next month portably across SQLite & PostgreSQL
    now = datetime.utcnow()
    start_of_month = datetime(now.year, now.month, 1)
    if now.month == 12:
        start_of_next_month = datetime(now.year + 1, 1, 1)
    else:
        start_of_next_month = datetime(now.year, now.month + 1, 1)
    
    month_income = db.session.query(db.func.sum(Transaction.amount))\
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.type.in_(['income', 'topup']),
            Transaction.created_at >= start_of_month,
            Transaction.created_at < start_of_next_month
        ).scalar() or 0.0
    
    month_expense = db.session.query(db.func.sum(Transaction.amount))\
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'expense',
            Transaction.created_at >= start_of_month,
            Transaction.created_at < start_of_next_month
        ).scalar() or 0.0
    
    return json_response({
        'available_balance': wallet_balance,
        'wallet_balance': wallet_balance,
        'pocket_balance': pocket_balance,
        'total_funds': total_funds,
        'total_balance': total_funds,
        'total_pockets': len(pockets),
        'monthly_income': float(month_income),
        'monthly_expense': float(month_expense),
        'net_monthly_savings': float(month_income - month_expense),
        'virtual_wallet_id': current_user.virtual_wallet_id or '',
        'virtual_upi_id': current_user.virtual_upi_id or '',
    })


@bp.route('/topup', methods=['POST'])
@api_login_required
def wallet_topup():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['amount'])
    if not valid:
        return error_response(msg, 400)
    
    amount = float(data.get('amount', 0))
    if amount <= 0:
        return error_response('Amount must be positive', 400)
    
    payment_method = data.get('payment_method', 'upi')
    upi_ref = data.get('upi_reference') or f'UPI{datetime.utcnow().strftime("%Y%m%d%H%M%S")}'
    
    current_user.wallet_balance += amount
    db.session.commit()
    
    tx = Transaction(
        transaction_id=Transaction.generate_transaction_id(),
        user_id=current_user.id,
        type='topup',
        amount=amount,
        category='Wallet Top-up',
        description=f'Wallet topped up via {payment_method}',
        payment_method=payment_method,
        upi_reference=upi_ref
    )
    db.session.add(tx)
    tx.complete()
    
    tx.qr_code_url = generate_qr_code(build_qr_tx_url(tx), 200)
    db.session.commit()
    
    Notification.transaction_alert(current_user.id, tx)
    
    return json_response({
        'transaction': tx.to_dict(),
        'new_balance': current_user.wallet_balance,
        'qr_code_url': tx.qr_code_url
    }, f'₹{amount:.2f} added to wallet successfully', 201)


@bp.route('/income/distribute/preview', methods=['POST'])
@api_login_required
def preview_income_distribution():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['total_amount', 'strategy'])
    if not valid:
        return error_response(msg, 400)
    
    total_amount = float(data.get('total_amount', 0))
    if total_amount <= 0:
        return error_response('Amount must be positive', 400)
    
    strategy = data.get('strategy')
    allocations = []
    summary = {
        'total_amount': total_amount,
        'total_allocated': 0,
        'remaining': total_amount,
        'strategy': strategy,
    }
    
    if strategy == 'single':
        pocket_id = data.get('pocket_id')
        if not pocket_id:
            return error_response('pocket_id required for single pocket strategy', 400)
        pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id, archived=False).first()
        if not pocket:
            return error_response('Pocket not found', 404)
        allocations = [{
            'pocket_id': pocket.id,
            'pocket_name': pocket.name,
            'pocket_color': pocket.color,
            'pocket_icon': pocket.icon,
            'amount': total_amount,
            'percentage': 100
        }]
        summary['total_allocated'] = total_amount
        summary['remaining'] = 0
        
    elif strategy == 'percentage':
        splits = data.get('splits', [])
        if not splits:
            return error_response('splits array required for percentage strategy', 400)
        
        total_pct = 0
        remaining_amount = total_amount
        
        for i, split in enumerate(splits):
            pocket_id = split.get('pocket_id')
            pct = float(split.get('percentage', 0))
            pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id, archived=False).first()
            if not pocket:
                return error_response(f'Pocket {pocket_id} not found', 404)
            amount = round(total_amount * pct / 100, 2)
            if i == len(splits) - 1:
                amount = round(remaining_amount, 2)
            remaining_amount = round(remaining_amount - amount, 2)
            total_pct += pct
            allocations.append({
                'pocket_id': pocket.id,
                'pocket_name': pocket.name,
                'pocket_color': pocket.color,
                'pocket_icon': pocket.icon,
                'amount': amount,
                'percentage': pct
            })
        
        summary['total_allocated'] = round(total_amount - remaining_amount, 2)
        summary['remaining'] = remaining_amount
        summary['total_percentage'] = total_pct
        
    elif strategy == 'fixed':
        splits = data.get('splits', [])
        if not splits:
            return error_response('splits array required for fixed strategy', 400)
        
        total_fixed = 0
        remaining_amount = total_amount
        
        for i, split in enumerate(splits):
            pocket_id = split.get('pocket_id')
            amount = float(split.get('amount', 0))
            pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id, archived=False).first()
            if not pocket:
                return error_response(f'Pocket {pocket_id} not found', 404)
            if i == len(splits) - 1:
                amount = round(remaining_amount, 2)
            remaining_amount = round(remaining_amount - amount, 2)
            total_fixed += amount
            allocations.append({
                'pocket_id': pocket.id,
                'pocket_name': pocket.name,
                'pocket_color': pocket.color,
                'pocket_icon': pocket.icon,
                'amount': amount
            })
        
        summary['total_allocated'] = round(total_amount - remaining_amount, 2)
        summary['remaining'] = remaining_amount
        
    elif strategy == 'rule':
        rule_id = data.get('rule_id')
        if not rule_id:
            return error_response('rule_id required for saved rule strategy', 400)
        rule = DistributionRule.query.filter_by(id=rule_id, user_id=current_user.id, is_active=True).first()
        if not rule:
            return error_response('Distribution rule not found', 404)
        
        result, err = rule.calculate_allocations(total_amount)
        if err:
            return error_response(err, 400)
        
        allocations = []
        remaining_amount = total_amount
        
        for i, alloc in enumerate(result):
            pocket = Pocket.query.filter_by(id=alloc['pocket_id'], user_id=current_user.id, archived=False).first()
            if not pocket:
                continue
            allocations.append({
                    'pocket_id': pocket.id,
                    'pocket_name': pocket.name,
                    'pocket_color': pocket.color,
                    'pocket_icon': pocket.icon,
                    'amount': alloc['amount'],
                    'percentage': alloc.get('percentage')
                })
            remaining_amount = round(remaining_amount - alloc['amount'], 2)
        
        summary['total_allocated'] = round(total_amount - remaining_amount, 2)
        summary['remaining'] = remaining_amount
        summary['rule_name'] = rule.name
        
    else:
        return error_response(
            'Invalid strategy. Use: single, percentage, fixed, or rule',
            400,
            code='INVALID_STRATEGY',
            available_strategies=['single', 'percentage', 'fixed', 'rule']
        )
    
    return json_response({
        'allocations': allocations,
        'summary': summary
    })


@bp.route('/income/execute', methods=['POST'])
@api_login_required
def execute_income_distribution():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['total_amount', 'strategy'])
    if not valid:
        return error_response(msg, 400)
    
    total_amount = float(data.get('total_amount', 0))
    if total_amount <= 0:
        return error_response('Amount must be positive', 400)
    
    strategy = data.get('strategy')
    raw_desc = data.get('description')
    description = str(raw_desc).strip() if raw_desc is not None and str(raw_desc).strip() else 'Income received'
    raw_src = data.get('source')
    source = str(raw_src).strip() if raw_src is not None and str(raw_src).strip() else 'Other'
    fund_source = str(data.get('fund_source') or 'external').lower()
    
    if fund_source == 'wallet':
        if current_user.wallet_balance < total_amount:
            return error_response(
                f'Insufficient wallet balance. Need ₹{total_amount:.2f} but wallet has ₹{current_user.wallet_balance:.2f}',
                400,
                code='INSUFFICIENT_WALLET_BALANCE'
            )
        current_user.wallet_balance -= total_amount
        db.session.commit()
    
    allocations = []
    
    if strategy == 'single':
        pocket_id = data.get('pocket_id')
        if not pocket_id:
            return error_response('pocket_id required for single pocket strategy', 400)
        pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id, archived=False).first()
        if not pocket:
            return error_response('Pocket not found', 404)
        allocations = [{'pocket_id': pocket.id, 'amount': total_amount}]
        
    elif strategy == 'percentage':
        splits = data.get('splits', [])
        if not splits:
            return error_response('splits array required for percentage strategy', 400)
        remaining = total_amount
        for i, split in enumerate(splits):
            pct = float(split.get('percentage', 0))
            amount = round(total_amount * pct / 100, 2)
            if i == len(splits) - 1:
                amount = round(remaining, 2)
            remaining = round(remaining - amount, 2)
            allocations.append({'pocket_id': split.get('pocket_id'), 'amount': amount})
            
    elif strategy == 'fixed':
        splits = data.get('splits', [])
        if not splits:
            return error_response('splits array required for fixed strategy', 400)
        remaining = total_amount
        for i, split in enumerate(splits):
            amount = float(split.get('amount', 0))
            if i == len(splits) - 1:
                amount = round(remaining, 2)
            remaining = round(remaining - amount, 2)
            allocations.append({'pocket_id': split.get('pocket_id'), 'amount': amount})
            
    elif strategy == 'rule':
        rule_id = data.get('rule_id')
        if not rule_id:
            return error_response('rule_id required for saved rule strategy', 400)
        rule = DistributionRule.query.filter_by(id=rule_id, user_id=current_user.id, is_active=True).first()
        if not rule:
            return error_response('Distribution rule not found', 404)
        result, err = rule.calculate_allocations(total_amount)
        if err:
            return error_response(err, 400)
        allocations = [{'pocket_id': a['pocket_id'], 'amount': a['amount']} for a in result]
        rule.mark_used()
        
    else:
        return error_response('Invalid strategy', 400)
    
    try:
        transactions = []
        total_distributed = 0
        
        for alloc in allocations:
            if alloc['amount'] <= 0:
                continue
            pocket = Pocket.query.filter_by(id=alloc['pocket_id'], user_id=current_user.id, archived=False).first()
            if not pocket:
                continue
            pocket.current_balance += alloc['amount']
            pocket.total_received += alloc['amount']
            total_distributed += alloc['amount']
            db.session.flush()
            
            tx = Transaction(
                transaction_id=Transaction.generate_transaction_id(),
                user_id=current_user.id,
                type='income',
                amount=alloc['amount'],
                to_pocket_id=pocket.id,
                category=source,
                description=description,
                payment_method='wallet'
            )
            db.session.add(tx)
            tx.complete()
            transactions.append(tx)
            
            budget = pocket.budget_usage_percent()
            if budget >= 75:
                pass
        
        db.session.commit()
        
        for tx in transactions:
            Notification.transaction_alert(current_user.id, tx)
        
        Notification.create(
            current_user.id,
            'Income Distributed',
            f'₹{total_distributed:.2f} distributed across {len(allocations)} pockets',
            'success',
            'high'
        )
        
        return json_response({
            'transactions': [t.to_dict(True) for t in transactions],
            'total_distributed': total_distributed,
            'pockets_updated': len(transactions)
        }, f'₹{total_distributed:.2f} distributed successfully', 201)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Distribution failed: {str(e)}', 500)


@bp.route('/rules', methods=['GET'])
@api_login_required
def list_distribution_rules():
    query = DistributionRule.query.filter_by(user_id=current_user.id).order_by(
        DistributionRule.is_default.desc(),
        DistributionRule.usage_count.desc()
    )
    
    only_active = request.args.get('active_only', 'false').lower() == 'true'
    if only_active:
        query = query.filter_by(is_active=True)
    
    rules = [r.to_dict() for r in query.all()]
    
    default_rule = next((r for r in rules if r.get('is_default')), None)
    
    return json_response({
        'rules': rules,
        'total': len(rules),
        'default_rule': default_rule
    })


@bp.route('/rules', methods=['POST'])
@api_login_required
def create_distribution_rule():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['name', 'rule_type', 'allocations'])
    if not valid:
        return error_response(msg, 400)
    
    name = data.get('name', '').strip()
    rule_type = data.get('rule_type', 'percentage')
    allocations = data.get('allocations', [])
    
    if rule_type not in ('percentage', 'fixed'):
        return error_response('rule_type must be percentage or fixed', 400)
    
    if not isinstance(allocations, list) or len(allocations) < 1:
        return error_response('At least one allocation required', 400)
    
    raw_desc = data.get('description')
    clean_desc = str(raw_desc).strip() if raw_desc is not None and str(raw_desc).strip() else None
    
    temp_rule = DistributionRule(
        user_id=current_user.id,
        name=name,
        rule_type=rule_type,
        description=clean_desc,
        allocations=allocations
    )
    
    valid_alloc, err = temp_rule.validate_allocations(1000)
    if not valid_alloc:
        return error_response(f'Invalid allocations: {err}', 400)
    
    if data.get('is_default'):
        DistributionRule.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
    
    rule = DistributionRule(
        user_id=current_user.id,
        name=name,
        rule_type=rule_type,
        description=clean_desc,
        allocations=allocations,
        is_default=bool(data.get('is_default', False)),
        is_active=True
    )
    
    db.session.add(rule)
    db.session.commit()
    
    Notification.create(
        current_user.id,
        'Distribution Rule Saved',
        f'Rule "{name}" has been saved and is ready to use.',
        'success',
        'normal'
    )
    
    return json_response({'rule': rule.to_dict()}, 'Rule created successfully', 201)


@bp.route('/rules/<int:rule_id>', methods=['GET'])
@api_login_required
def get_distribution_rule(rule_id):
    rule = DistributionRule.query.filter_by(id=rule_id, user_id=current_user.id).first()
    if not rule:
        return error_response('Rule not found', 404)
    return json_response({'rule': rule.to_dict()})


@bp.route('/rules/<int:rule_id>', methods=['PUT'])
@api_login_required
def update_distribution_rule(rule_id):
    rule = DistributionRule.query.filter_by(id=rule_id, user_id=current_user.id).first()
    if not rule:
        return error_response('Rule not found', 404)
    
    data = request.get_json() or {}
    
    if 'name' in data and data['name']:
        rule.name = data['name'].strip()
    if 'description' in data:
        rule.description = data['description'].strip() or None
    if 'rule_type' in data and data['rule_type'] in ('percentage', 'fixed'):
        rule.rule_type = data['rule_type']
    if 'allocations' in data:
        rule.allocations = data['allocations']
    if 'is_default' in data:
        if data['is_default']:
            DistributionRule.query.filter(
                DistributionRule.user_id == current_user.id,
                DistributionRule.id != rule_id
            ).update({'is_default': False})
        rule.is_default = bool(data['is_default'])
    if 'is_active' in data:
        rule.is_active = bool(data['is_active'])
    
    valid, err = rule.validate_allocations(1000)
    if not valid:
        return error_response(f'Invalid allocations: {err}', 400)
    
    db.session.commit()
    return json_response({'rule': rule.to_dict()}, 'Rule updated successfully')


@bp.route('/rules/<int:rule_id>', methods=['DELETE'])
@api_login_required
def delete_distribution_rule(rule_id):
    rule = DistributionRule.query.filter_by(id=rule_id, user_id=current_user.id).first()
    if not rule:
        return error_response('Rule not found', 404)
    
    rule_name = rule.name
    db.session.delete(rule)
    db.session.commit()
    
    return json_response(message=f'Rule "{rule_name}" deleted successfully')


@bp.route('/withdraw', methods=['POST'])
@api_login_required
def wallet_withdraw():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['amount'])
    if not valid:
        return error_response(msg, 400)
    
    amount = float(data.get('amount', 0))
    if amount <= 0:
        return error_response('Amount must be positive', 400)
    
    if current_user.transaction_pin_hash:
        pin = str(data.get('pin', '')).strip()
        if not pin:
            return error_response('Transaction PIN is required', 400, code='PIN_REQUIRED')
        success, error = current_user.verify_transaction_pin(pin)
        if not success:
            return error_response(error or 'Incorrect PIN', 401, code='INCORRECT_PIN')
    
    if current_user.wallet_balance < amount:
        return error_response(
            f'Insufficient wallet balance. You have ₹{current_user.wallet_balance:.2f}',
            400,
            code='INSUFFICIENT_BALANCE'
        )
    
    current_user.wallet_balance = round(current_user.wallet_balance - amount, 2)
    db.session.commit()
    
    tx = Transaction(
        transaction_id=Transaction.generate_transaction_id(),
        user_id=current_user.id,
        type='withdraw',
        amount=amount,
        category='Wallet Withdrawal',
        description=str(data.get('description') or '').strip() or 'Withdrawal to bank',
        payment_method=data.get('payment_method', 'bank')
    )
    db.session.add(tx)
    tx.complete()
    
    Notification.transaction_alert(current_user.id, tx)
    
    return json_response({
        'transaction': tx.to_dict(),
        'new_balance': current_user.wallet_balance
    }, f'₹{amount:.2f} withdrawn successfully', 201)


@bp.route('/categories', methods=['GET'])
@api_login_required
def get_expense_categories():
    return json_response({
        'categories': EXPENSE_CATEGORIES,
        'count': len(EXPENSE_CATEGORIES)
    })


# =============================================================================
# PEER-TO-PEER (P2P) SEND & REQUEST MONEY ENDPOINTS
# =============================================================================

@bp.route('/search-user', methods=['GET'])
@api_login_required
def search_user():
    """
    Safely searches for a PocketPay user by email, phone, UPI ID, or virtual wallet ID.
    Returns sanitized public user profile without leaking sensitive credentials.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return error_response('Search query is required', 400)
        
    clean_q = query.lower()
    clean_phone = re.sub(r'[\s\-]', '', query)
    phone_candidates = list({
        query,
        clean_phone,
        '+' + clean_phone if not clean_phone.startswith('+') else clean_phone,
        clean_phone.lstrip('+'),
        '+91' + clean_phone.lstrip('+') if len(clean_phone.lstrip('+')) == 10 else clean_phone
    })
    
    target = User.query.filter(
        (User.email == clean_q) |
        (User.virtual_upi_id == clean_q) |
        (User.virtual_wallet_id == query.upper()) |
        (User.phone.in_(phone_candidates))
    ).first()
    
    if not target:
        return error_response('User not found on PocketPay', 404)
        
    if target.id == current_user.id:
        return error_response('You cannot send or request money from yourself', 400)
        
    # Mask email for privacy (e.g. j***@domain.com)
    email_parts = target.email.split('@')
    masked_email = email_parts[0][0] + '***@' + email_parts[1] if len(email_parts) == 2 else target.email
    
    if not target.is_active:
        return error_response('User account is inactive or suspended', 400, code='USER_INACTIVE')

    return json_response({
        'found': True,
        'verified': True,
        'user': {
            'id': target.id,
            'full_name': target.full_name,
            'masked_email': masked_email,
            'virtual_upi_id': target.virtual_upi_id,
            'virtual_wallet_id': target.virtual_wallet_id,
            'avatar_url': target.avatar_url,
            'is_active': target.is_active
        }
    })


@bp.route('/verify-id', methods=['POST', 'GET'])
@bp.route('/verify-wallet-id', methods=['POST', 'GET'])
@api_login_required
def verify_wallet_id():
    """
    Secure server-side verification for PocketPay Wallet IDs / Identifiers.
    Checks existence, user existence, wallet active status, and disallows self-transfers.
    """
    if request.method == 'GET':
        wallet_id = request.args.get('wallet_id') or request.args.get('id') or request.args.get('q') or ''
    else:
        data = request.get_json(silent=True) or {}
        wallet_id = data.get('wallet_id') or data.get('recipient') or data.get('id') or ''
        
    clean_id = str(wallet_id).strip()
    if not clean_id:
        return error_response('PocketPay Wallet ID is required', 400, code='WALLET_ID_REQUIRED')

    clean_q = clean_id.lower()
    clean_phone = re.sub(r'[\s\-]', '', clean_id)
    phone_candidates = list({
        clean_id,
        clean_phone,
        '+' + clean_phone if not clean_phone.startswith('+') else clean_phone,
        clean_phone.lstrip('+'),
        '+91' + clean_phone.lstrip('+') if len(clean_phone.lstrip('+')) == 10 else clean_phone
    })

    target = User.query.filter(
        (User.virtual_wallet_id == clean_id.upper()) |
        (User.virtual_upi_id == clean_q) |
        (User.email == clean_q) |
        (User.phone.in_(phone_candidates))
    ).first()

    if not target:
        return error_response('PocketPay Wallet ID not found', 404, code='WALLET_NOT_FOUND')

    if target.id == current_user.id:
        return error_response('Cannot transfer or send money to your own wallet', 400, code='SELF_TRANSFER_DISALLOWED')

    if not target.is_active:
        return error_response('PocketPay Wallet account is inactive or suspended', 400, code='WALLET_INACTIVE')

    email_parts = target.email.split('@')
    masked_email = email_parts[0][0] + '***@' + email_parts[1] if len(email_parts) == 2 else target.email

    return json_response({
        'valid': True,
        'verified': True,
        'status': 'active',
        'verification_type': 'pocketpay_wallet',
        'recipient': {
            'id': target.id,
            'full_name': target.full_name,
            'virtual_wallet_id': target.virtual_wallet_id,
            'virtual_upi_id': target.virtual_upi_id,
            'masked_email': masked_email,
            'is_active': target.is_active,
            'verified_badge': True
        }
    }, 'PocketPay Wallet ID verified successfully')


@bp.route('/verify-upi', methods=['POST'])
@api_login_required
def verify_upi_id_endpoint():
    """
    Dedicated endpoint to verify any external UPI ID / VPA.
    Runs format validation, handles @pocketpay virtual VPAs, and invokes provider/mock verification.
    """
    data = request.get_json() or {}
    vpa = str(data.get('upi_id') or data.get('vpa') or data.get('recipient') or '').strip()
    if not vpa:
        return error_response('UPI ID / VPA is required', 400, code='UPI_ID_REQUIRED')

    from app.services.upi_verification_service import UPIVerificationService
    result = UPIVerificationService.verify_vpa(vpa)

    if not result.get('valid'):
        return error_response(result.get('error', 'Invalid UPI ID'), 400, **result)

    return json_response(result, result.get('message', 'UPI ID verified successfully'))


@bp.route('/send-money', methods=['POST'])
@api_login_required
def send_money():
    """
    Transfers money directly between PocketPay users.
    Verifies Transaction PIN and 2FA TOTP before executing transfer.
    Atomically debits sender and credits recipient via LedgerService with dual ledger records.
    """
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['recipient', 'amount', 'pin'])
    if not valid:
        return error_response(msg, 400)
        
    try:
        amount = round(float(data.get('amount', 0)), 2)
    except (ValueError, TypeError):
        return error_response('Invalid transfer amount', 400)

    if amount <= 0:
        return error_response('Transfer amount must be positive', 400)
    if amount < 1.0:
        return error_response('Minimum peer transfer amount is ₹1.00', 400)
        
    pin = str(data.get('pin', '')).strip()
    if not current_user.transaction_pin_hash:
        if pin and pin.isdigit() and len(pin) == 4:
            current_user.set_transaction_pin(pin)
            db.session.commit()
        else:
            return error_response('Transaction PIN not set. Please enter a 4-digit PIN.', 400, code='PIN_NOT_SET')
    else:
        pin_ok, pin_err = current_user.verify_transaction_pin(pin)
        if not pin_ok:
            return error_response(pin_err or 'Incorrect PIN', 401, code='INCORRECT_PIN',
                                  pin_attempts=current_user.pin_attempts,
                                  pin_locked_until=current_user.pin_locked_until.isoformat() if current_user.pin_locked_until else None)
                              
    # 2FA TOTP verification
    if current_user.totp_enabled:
        totp_code = data.get('totp_code') or data.get('totp') or data.get('otp')
        if not totp_code:
            return error_response('Google Authenticator 6-digit 2FA code is required', 400, code='TOTP_REQUIRED')
        verified, err, err_code = current_user.verify_totp(totp_code)
        if not verified:
            return error_response(err or 'Invalid Authenticator 2FA code', 401, code=err_code or 'INCORRECT_TOTP')

    # Idempotency check
    idemp_key = get_idempotency_key(request, data)
    idemp_rec = None
    if idemp_key:
        idemp_rec, cached_resp = check_idempotency(idemp_key, '/api/wallet/send-money', current_user.id, data)
        if cached_resp:
            resp_body, resp_code = cached_resp
            return json_response(resp_body.get('data'), resp_body.get('message'), resp_code)

    # Resolve recipient
    recipient_identifier = str(data.get('recipient', '')).strip()
    clean_q = recipient_identifier.lower()
    clean_phone = re.sub(r'[\s\-]', '', recipient_identifier)
    phone_candidates = list({
        recipient_identifier,
        clean_phone,
        '+' + clean_phone if not clean_phone.startswith('+') else clean_phone,
        clean_phone.lstrip('+'),
        '+91' + clean_phone.lstrip('+') if len(clean_phone.lstrip('+')) == 10 else clean_phone
    })
    
    recipient = User.query.filter(
        (User.id == (int(recipient_identifier) if recipient_identifier.isdigit() and len(recipient_identifier) < 8 else -1)) |
        (User.email == clean_q) |
        (User.virtual_upi_id == clean_q) |
        (User.virtual_wallet_id == recipient_identifier.upper()) |
        (User.phone.in_(phone_candidates))
    ).first()
    
    if not recipient:
        return error_response('Recipient account not found on PocketPay', 404)
        
    if recipient.id == current_user.id:
        return error_response('Cannot send money to your own account', 400)

    if not recipient.is_active:
        return error_response('Recipient account is inactive or suspended', 400, code='RECIPIENT_INACTIVE')
        
    pocket_raw = data.get('pocket_id')
    source_pocket = None
    if pocket_raw is not None and str(pocket_raw).strip() != '' and str(pocket_raw).lower() != 'wallet':
        try:
            p_id = int(pocket_raw)
            source_pocket = Pocket.query.filter_by(id=p_id, user_id=current_user.id, archived=False).first()
            if not source_pocket:
                return error_response('Selected funding pocket not found', 404)
        except (ValueError, TypeError):
            source_pocket = None

    note = str(data.get('note', '')).strip() or f'Transfer to {recipient.full_name}'
    
    try:
        res = LedgerService.transfer_p2p(
            sender=current_user,
            recipient=recipient,
            amount=amount,
            source_pocket=source_pocket,
            note=note,
            idempotency_key=idemp_key
        )

        tx_sender = res['sender_transaction']
        receipt_qr = generate_qr_code(build_qr_tx_url(tx_sender), 250) or tx_sender.qr_code_url

        resp_data = {
            'transaction': tx_sender.to_dict(True),
            'recipient': {
                'id': recipient.id,
                'full_name': recipient.full_name,
                'virtual_upi_id': recipient.virtual_upi_id
            },
            'wallet_balance': current_user.wallet_balance,
            'total_funds': current_user.to_dict()['total_funds'],
            'pocket_balance': source_pocket.current_balance if source_pocket else None,
            'receipt_qr': receipt_qr
        }

        if idemp_rec:
            save_idempotency(idemp_rec, {'data': resp_data, 'message': f'₹{amount:,.2f} sent successfully to {recipient.full_name}'}, 201)

        # Instant Telegram notification dispatch (non-blocking / safe)
        try:
            from app.telegram.service import TelegramService
            if TelegramService.is_configured():
                TelegramService.send_event_notification(
                    recipient,
                    "Money Received! 💰",
                    f"You received <b>₹{amount:,.2f}</b> from <b>{current_user.full_name}</b> ({recipient.virtual_upi_id or recipient.email}).\n\n<i>Note: {note}</i>",
                    "success"
                )
                TelegramService.send_event_notification(
                    current_user,
                    "Money Sent 💸",
                    f"You successfully sent <b>₹{amount:,.2f}</b> to <b>{recipient.full_name}</b> ({recipient.virtual_upi_id or recipient.email}).",
                    "info"
                )
        except Exception:
            pass

        return json_response(resp_data, f'₹{amount:,.2f} sent successfully to {recipient.full_name}', 201)

    except FinancialInvariantError as fe:
        return error_response(str(fe), 400, code='INSUFFICIENT_BALANCE')
    except Exception as e:
        return error_response(f'Transfer failed: {str(e)}', 500)


@bp.route('/request-money', methods=['POST'])
@api_login_required
def request_money():
    """
    Creates a new peer-to-peer money request to another PocketPay user.
    Supports targeting an optional pocket and setting an expiry window.
    """
    data = request.get_json() or {}
    recipient_identifier = str(data.get('recipient') or data.get('target') or '').strip()
    if not recipient_identifier:
        return error_response('Recipient or target identifier is required', 400)
        
    valid, msg = validate_required_fields(data, ['amount'])
    if not valid:
        return error_response(msg, 400)
        
    try:
        amount = round(float(data.get('amount', 0)), 2)
    except (ValueError, TypeError):
        return error_response('Invalid request amount', 400)

    if amount <= 0:
        return error_response('Request amount must be positive', 400)
    if amount < 1.0:
        return error_response('Minimum money request amount is ₹1.00', 400)
        
    clean_q = recipient_identifier.lower()
    clean_phone = re.sub(r'[\s\-]', '', recipient_identifier)
    
    target = User.query.filter(
        (User.id == (int(recipient_identifier) if recipient_identifier.isdigit() and len(recipient_identifier) < 8 else -1)) |
        (User.email == clean_q) |
        (User.virtual_upi_id == clean_q) |
        (User.virtual_wallet_id == recipient_identifier.upper()) |
        (User.phone == recipient_identifier) |
        (User.phone == clean_phone)
    ).first()
    
    if not target:
        return error_response('Target user not found on PocketPay', 404)
        
    if target.id == current_user.id:
        return error_response('Cannot request money from yourself', 400)
        
    target_pocket_id = data.get('target_pocket_id')
    target_pocket = None
    if target_pocket_id:
        target_pocket = Pocket.query.filter_by(id=target_pocket_id, user_id=current_user.id, archived=False).first()

    note = str(data.get('note', '')).strip() or f'Money request from {current_user.full_name}'
    
    expiry_days = 7
    try:
        if data.get('expiry_days'):
            expiry_days = max(1, min(30, int(data.get('expiry_days'))))
    except (ValueError, TypeError):
        pass

    expires_at = datetime.utcnow() + timedelta(days=expiry_days)

    req = MoneyRequest(
        requester_id=current_user.id,
        target_user_id=target.id,
        amount=amount,
        target_pocket_id=target_pocket.id if target_pocket else None,
        note=note,
        status='pending',
        expires_at=expires_at
    )
    db.session.add(req)
    db.session.commit()
    
    # Notify target user
    Notification.create(
        target.id,
        'Money Request Received 📬',
        f'{current_user.full_name} requested ₹{amount:,.2f} from you. Note: "{note}"',
        'info',
        'high'
    )
    
    return json_response({
        'request': req.to_dict()
    }, f'Money request for ₹{amount:,.2f} sent to {target.full_name}', 201)


@bp.route('/requests', methods=['GET'])
@api_login_required
def list_money_requests():
    """
    Retrieves incoming and outgoing peer money requests with live expiry status check.
    """
    req_type = request.args.get('type', 'all').lower()
    status_filter = request.args.get('status', 'all').lower()
    
    query = MoneyRequest.query
    if req_type == 'incoming':
        query = query.filter_by(target_user_id=current_user.id)
    elif req_type == 'outgoing':
        query = query.filter_by(requester_id=current_user.id)
    else:
        query = query.filter(
            (MoneyRequest.target_user_id == current_user.id) |
            (MoneyRequest.requester_id == current_user.id)
        )
        
    all_reqs = query.order_by(MoneyRequest.created_at.desc()).all()
    
    # Run expiry check on pending requests
    for r in all_reqs:
        r.check_and_update_expiry()

    if status_filter != 'all':
        requests_list = [r.to_dict() for r in all_reqs if r.status == status_filter]
    else:
        requests_list = [r.to_dict() for r in all_reqs]
    
    pending_incoming = sum(1 for r in requests_list if r['target_user_id'] == current_user.id and r['status'] == 'pending')
    
    return json_response({
        'requests': requests_list,
        'total': len(requests_list),
        'pending_incoming_count': pending_incoming
    })


@bp.route('/requests/<int:req_id>/pay', methods=['POST'])
@api_login_required
def pay_money_request(req_id):
    """
    Approves and pays a pending money request via LedgerService.
    Supports funding from Available Balance or a Pocket, and optionally crediting the requester's target pocket.
    """
    req = MoneyRequest.query.filter_by(id=req_id, target_user_id=current_user.id).first()
    if not req:
        return error_response('Money request not found', 404)

    if req.status == 'expired' or req.check_and_update_expiry():
        return error_response('This money request has expired', 400, code='REQUEST_EXPIRED')

    if req.status != 'pending':
        return error_response(f'Money request has already been {req.status}', 400, code='REQUEST_NOT_PENDING')
        
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['pin'])
    if not valid:
        return error_response(msg, 400)
        
    pin = str(data.get('pin', '')).strip()
    if not current_user.transaction_pin_hash:
        return error_response('Transaction PIN not set. Please set up your PIN first.', 400, code='PIN_NOT_SET')
        
    pin_ok, pin_err = current_user.verify_transaction_pin(pin)
    if not pin_ok:
        return error_response(pin_err or 'Incorrect PIN', 401, code='INCORRECT_PIN',
                              pin_attempts=current_user.pin_attempts,
                              pin_locked_until=current_user.pin_locked_until.isoformat() if current_user.pin_locked_until else None)
        
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
        idemp_rec, cached_resp = check_idempotency(idemp_key, f'/api/wallet/requests/{req_id}/pay', current_user.id, data)
        if cached_resp:
            resp_body, resp_code = cached_resp
            return json_response(resp_body.get('data'), resp_body.get('message'), resp_code)
            
    amount = float(req.amount)
    pocket_id = data.get('pocket_id')
    source_pocket = None
    
    if pocket_id:
        source_pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id, archived=False).first()
        if not source_pocket:
            return error_response('Selected funding pocket not found', 404)
        if float(source_pocket.current_balance or 0) < amount:
            return error_response(f'Insufficient balance in {source_pocket.name}', 400, code='INSUFFICIENT_POCKET_BALANCE')

    requester = req.requester
    dest_pocket = None
    if req.target_pocket_id and req.target_pocket and not req.target_pocket.archived:
        dest_pocket = req.target_pocket

    note = f'Paid money request: {req.note or "Requested amount"}'

    try:
        res = LedgerService.transfer_p2p(
            sender=current_user,
            recipient=requester,
            amount=amount,
            source_pocket=source_pocket,
            dest_pocket=dest_pocket,
            note=note,
            idempotency_key=idemp_key
        )

        tx_sender = res['sender_transaction']
        tx_recipient = res['recipient_transaction']

        # Update money request record
        req.status = 'paid'
        req.responded_at = datetime.utcnow()
        req.transaction_id = tx_sender.transaction_id
        db.session.commit()

        receipt_qr = generate_qr_code(build_qr_tx_url(tx_sender), 250) or tx_sender.qr_code_url
        
        resp_data = {
            'request': req.to_dict(),
            'transaction': tx_sender.to_dict(True),
            'wallet_balance': current_user.wallet_balance,
            'total_funds': current_user.to_dict()['total_funds'],
            'receipt_qr': receipt_qr
        }

        if idemp_rec:
            save_idempotency(idemp_rec, {'data': resp_data, 'message': f'₹{amount:,.2f} paid successfully to {requester.full_name}'}, 200)

        # Notify via Telegram if configured
        try:
            from app.telegram.service import TelegramService
            if TelegramService.is_configured():
                TelegramService.send_event_notification(
                    requester,
                    "Money Request Paid! 💰",
                    f"<b>{current_user.full_name}</b> paid your request for <b>₹{amount:,.2f}</b>.",
                    "success"
                )
        except Exception:
            pass

        return json_response(resp_data, f'₹{amount:,.2f} paid successfully to {requester.full_name}')

    except FinancialInvariantError as fe:
        return error_response(str(fe), 400, code='INSUFFICIENT_BALANCE')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Payment failed: {str(e)}', 500)


@bp.route('/requests/<int:req_id>/decline', methods=['POST'])
@api_login_required
def decline_money_request(req_id):
    """
    Declines an incoming money request.
    """
    req = MoneyRequest.query.filter_by(id=req_id, target_user_id=current_user.id, status='pending').first()
    if not req:
        return error_response('Pending money request not found', 404)
        
    req.status = 'declined'
    req.responded_at = datetime.utcnow()
    db.session.commit()
    
    Notification.create(
        req.requester_id,
        'Money Request Declined',
        f'{current_user.full_name} declined your money request for ₹{float(req.amount):,.2f}.',
        'info',
        'medium'
    )
    
    return json_response({
        'request': req.to_dict()
    }, 'Money request declined')


@bp.route('/reconciliation', methods=['GET'])
@api_login_required
def get_reconciliation():
    """
    Returns real-time financial integrity audit and ledger reconciliation for the current user.
    Ensures: Available Balance + Sum(Active Pockets) == Total Funds and matches historical ledger debits & credits.
    """
    report = LedgerService.reconcile_user_account(current_user)
    return json_response(report, 'Reconciliation report generated successfully')


