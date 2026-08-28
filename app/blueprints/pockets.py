from flask import Blueprint, request
from flask_login import current_user
from app.extensions import db
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.notification import Notification
from app.utils.helpers import (
    json_response, error_response, validate_required_fields,
    api_login_required, get_paginated_query, paginated_response
)

bp = Blueprint('pockets', __name__)


@bp.route('', methods=['GET'])
@api_login_required
def list_pockets():
    include_archived = request.args.get('archived', 'false').lower() == 'true'
    include_stats = request.args.get('stats', 'false').lower() == 'true'
    
    query = Pocket.query.filter_by(user_id=current_user.id)
    if not include_archived:
        query = query.filter_by(archived=False)
    
    sort_by = request.args.get('sort_by', 'sort_order')
    if sort_by == 'balance':
        query = query.order_by(Pocket.current_balance.desc())
    elif sort_by == 'name':
        query = query.order_by(Pocket.name.asc())
    elif sort_by == 'spent':
        query = query.order_by(Pocket.total_spent.desc())
    elif sort_by == 'recent':
        query = query.order_by(Pocket.updated_at.desc())
    else:
        query = query.order_by(Pocket.sort_order.asc(), Pocket.created_at.desc())
    
    pagination = get_paginated_query(query)
    
    pockets = [p.to_dict(include_stats=include_stats) for p in pagination.items]
    
    summary = {
        'total_balance': sum(p['current_balance'] for p in pockets),
        'total_received': sum(p['total_received'] for p in pockets),
        'total_spent': sum(p['total_spent'] for p in pockets),
        'active_count': Pocket.query.filter_by(user_id=current_user.id, archived=False).count(),
        'archived_count': Pocket.query.filter_by(user_id=current_user.id, archived=True).count(),
    }
    
    return json_response({
        **paginated_response(pagination),
        'items': pockets,
        'summary': summary
    })


@bp.route('/<int:pocket_id>', methods=['GET'])
@api_login_required
def get_pocket(pocket_id):
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id).first()
    if not pocket:
        return error_response('Pocket not found', 404)
    
    recent_transactions = Transaction.query.filter(
        (Transaction.from_pocket_id == pocket_id) |
        (Transaction.to_pocket_id == pocket_id),
        Transaction.user_id == current_user.id
    ).order_by(Transaction.created_at.desc()).limit(10).all()
    
    return json_response({
        'pocket': pocket.to_dict(include_stats=True),
        'recent_transactions': [t.to_dict(True) for t in recent_transactions]
    })


@bp.route('', methods=['POST'])
@api_login_required
def create_pocket():
    data = request.get_json() or {}
    
    valid, msg = validate_required_fields(data, ['name'])
    if not valid:
        return error_response(msg, 400)
    
    name = str(data.get('name') or '').strip()
    if len(name) < 1 or len(name) > 100:
        return error_response('Pocket name must be between 1 and 100 characters', 400)
    
    existing = Pocket.query.filter_by(user_id=current_user.id, name=name, archived=False).first()
    if existing:
        return error_response(f'A pocket with this name already exists', 409)
    
    initial_bal = float(data.get('initial_balance', 0) or 0)
    if initial_bal < 0:
        return error_response('Initial balance cannot be negative', 400)
        
    if initial_bal > 0:
        if (current_user.wallet_balance or 0.0) < initial_bal:
            return error_response(
                f'Insufficient available balance (₹{current_user.wallet_balance:,.2f}) to allocate ₹{initial_bal:,.2f} to {name}. '
                'Please sync or top up your available balance first.',
                400,
                code='INSUFFICIENT_AVAILABLE_BALANCE'
            )
        current_user.wallet_balance = round(current_user.wallet_balance - initial_bal, 2)
    
    max_order = db.session.query(db.func.max(Pocket.sort_order))\
        .filter_by(user_id=current_user.id).scalar() or -1
    
    raw_desc = data.get('description')
    clean_desc = str(raw_desc).strip() if raw_desc is not None and str(raw_desc).strip() else None
    
    pocket = Pocket(
        user_id=current_user.id,
        name=name,
        description=clean_desc,
        color=str(data.get('color') or '#6366f1').strip(),
        icon=str(data.get('icon') or 'wallet').strip(),
        icon_type=str(data.get('icon_type') or 'lucide').strip(),
        budget_amount=float(data.get('budget_amount', 0) or 0),
        monthly_limit=float(data.get('monthly_limit', 0) or 0),
        priority=int(data.get('priority', 0) or 0),
        sort_order=max_order + 1,
        spending_rules=data.get('spending_rules', {}) or {},
        current_balance=initial_bal,
        total_received=initial_bal,
    )
    
    db.session.add(pocket)
    db.session.commit()
    
    if pocket.current_balance > 0:
        tx = Transaction(
            transaction_id=Transaction.generate_transaction_id(),
            user_id=current_user.id,
            type='topup',
            amount=pocket.current_balance,
            to_pocket_id=pocket.id,
            category='Pocket Allocation',
            description=f'Allocated ₹{pocket.current_balance:,.2f} to {pocket.name}',
            payment_method='transfer'
        )
        db.session.add(tx)
        tx.complete()
        Notification.transaction_alert(current_user.id, tx)
    
    Notification.create(
        current_user.id,
        'Pocket Created',
        f'Your "{pocket.name}" pocket has been created successfully with allocation of ₹{pocket.current_balance:,.2f}.',
        'success',
        'normal',
        pocket_id=pocket.id
    )
    
    return json_response({
        'pocket': pocket.to_dict(True),
        'wallet_balance': current_user.wallet_balance
    }, 'Pocket created successfully', 201)


@bp.route('/<int:pocket_id>', methods=['PUT'])
@api_login_required
def update_pocket(pocket_id):
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id).first()
    if not pocket:
        return error_response('Pocket not found', 404)
    if pocket.archived:
        return error_response('Cannot update an archived pocket. Restore it first.', 400)
    
    data = request.get_json() or {}
    
    updatable_fields = [
        'name', 'description', 'color', 'icon', 'icon_type',
        'budget_amount', 'monthly_limit', 'priority',
        'sort_order', 'spending_rules'
    ]
    
    changes = False
    for field in updatable_fields:
        if field in data:
            value = data[field]
            if field == 'name':
                value = str(value or '').strip()
                if not value or len(value) > 100:
                    return error_response('Pocket name must be between 1 and 100 characters', 400)
                existing = Pocket.query.filter(
                    Pocket.user_id == current_user.id,
                    Pocket.name == value,
                    Pocket.id != pocket_id,
                    Pocket.archived == False
                ).first()
                if existing:
                    return error_response('A pocket with this name already exists', 409)
            elif field in ('budget_amount', 'monthly_limit'):
                value = float(value or 0)
                if value < 0:
                    return error_response(f'{field} cannot be negative', 400)
            elif field in ('priority', 'sort_order'):
                value = int(value or 0)
            elif field == 'description':
                value = str(value).strip() if value is not None and str(value).strip() else None
            elif field in ('color', 'icon', 'icon_type'):
                value = str(value or '').strip()
            elif field == 'spending_rules':
                value = value or {}
            setattr(pocket, field, value)
            changes = True
    
    if changes:
        db.session.commit()
    
    return json_response({
        'pocket': pocket.to_dict(True)
    }, 'Pocket updated successfully')


@bp.route('/<int:pocket_id>/rename', methods=['PUT'])
@api_login_required
def rename_pocket(pocket_id):
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id).first()
    if not pocket:
        return error_response('Pocket not found', 404)
    
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['name'])
    if not valid:
        return error_response(msg, 400)
    
    new_name = data['name'].strip()
    if len(new_name) < 1 or len(new_name) > 100:
        return error_response('Pocket name must be between 1 and 100 characters', 400)
    
    existing = Pocket.query.filter(
        Pocket.user_id == current_user.id,
        Pocket.name == new_name,
        Pocket.id != pocket_id,
        Pocket.archived == False
    ).first()
    if existing:
        return error_response('A pocket with this name already exists', 409)
    
    old_name = pocket.name
    pocket.name = new_name
    db.session.commit()
    
    return json_response({
        'pocket': pocket.to_dict()
    }, f'Pocket renamed from "{old_name}" to "{new_name}"')


@bp.route('/<int:pocket_id>/color', methods=['PUT'])
@api_login_required
def change_pocket_color(pocket_id):
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id).first()
    if not pocket:
        return error_response('Pocket not found', 404)
    
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['color'])
    if not valid:
        return error_response(msg, 400)
    
    color = data['color'].strip()
    if not color.startswith('#') or len(color) not in (4, 7, 9):
        return error_response('Invalid color format. Use hex color format (e.g., #RRGGBB)', 400)
    
    pocket.color = color
    db.session.commit()
    
    return json_response({
        'pocket': pocket.to_dict()
    }, 'Pocket color updated')


@bp.route('/<int:pocket_id>/icon', methods=['PUT'])
@api_login_required
def change_pocket_icon(pocket_id):
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id).first()
    if not pocket:
        return error_response('Pocket not found', 404)
    
    data = request.get_json() or {}
    icon = data.get('icon', '').strip()
    icon_type = data.get('icon_type', 'lucide').strip()
    
    if not icon:
        return error_response('Icon is required', 400)
    
    pocket.icon = icon
    pocket.icon_type = icon_type
    db.session.commit()
    
    return json_response({
        'pocket': pocket.to_dict()
    }, 'Pocket icon updated')


@bp.route('/<int:pocket_id>/archive', methods=['POST'])
@api_login_required
def archive_pocket(pocket_id):
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id).first()
    if not pocket:
        return error_response('Pocket not found', 404)
    if pocket.archived:
        return error_response('Pocket is already archived', 400)
    
    pocket.archive()
    
    Notification.create(
        current_user.id,
        'Pocket Archived',
        f'Your "{pocket.name}" pocket has been archived.',
        'info',
        'normal',
        pocket_id=pocket.id
    )
    
    return json_response({
        'pocket': pocket.to_dict()
    }, 'Pocket archived successfully')


@bp.route('/<int:pocket_id>/restore', methods=['POST'])
@api_login_required
def restore_pocket(pocket_id):
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id).first()
    if not pocket:
        return error_response('Pocket not found', 404)
    if not pocket.archived:
        return error_response('Pocket is not archived', 400)
    
    pocket.restore()
    
    Notification.create(
        current_user.id,
        'Pocket Restored',
        f'Your "{pocket.name}" pocket has been restored.',
        'success',
        'normal',
        pocket_id=pocket.id
    )
    
    return json_response({
        'pocket': pocket.to_dict()
    }, 'Pocket restored successfully')


@bp.route('/<int:pocket_id>/add-money', methods=['POST'])
@api_login_required
def add_money_to_pocket(pocket_id):
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id).first()
    if not pocket:
        return error_response('Pocket not found', 404)
    if pocket.archived:
        return error_response('Cannot allocate to an archived pocket', 400)
        
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['amount'])
    if not valid:
        return error_response(msg, 400)
        
    amount = float(data.get('amount', 0))
    if amount <= 0:
        return error_response('Amount must be positive', 400)
        
    if (current_user.wallet_balance or 0.0) < amount:
        return error_response(
            f'Insufficient available balance. You have ₹{current_user.wallet_balance:,.2f} available in unallocated balance.',
            400,
            code='INSUFFICIENT_AVAILABLE_BALANCE',
            available_balance=current_user.wallet_balance,
            required_amount=amount
        )
        
    current_user.wallet_balance = round(current_user.wallet_balance - amount, 2)
    pocket.add_money(amount)
    
    tx = Transaction(
        transaction_id=Transaction.generate_transaction_id(),
        user_id=current_user.id,
        type='topup',
        amount=amount,
        to_pocket_id=pocket.id,
        category='Pocket Allocation',
        description=data.get('description') or f'Allocated ₹{amount:,.2f} from available balance to {pocket.name}',
        payment_method='internal'
    )
    db.session.add(tx)
    tx.complete()
    
    Notification.transaction_alert(current_user.id, tx)
    
    return json_response({
        'pocket': pocket.to_dict(True),
        'wallet_balance': current_user.wallet_balance,
        'transaction': tx.to_dict(True)
    }, f'₹{amount:,.2f} allocated to {pocket.name} successfully')


@bp.route('/<int:pocket_id>/withdraw', methods=['POST'])
@api_login_required
def withdraw_from_pocket(pocket_id):
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id).first()
    if not pocket:
        return error_response('Pocket not found', 404)
        
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['amount'])
    if not valid:
        return error_response(msg, 400)
        
    amount = float(data.get('amount', 0))
    if amount <= 0:
        return error_response('Amount must be positive', 400)
        
    if pocket.current_balance < amount:
        return error_response(
            f'Insufficient pocket balance. {pocket.name} has ₹{pocket.current_balance:,.2f}.',
            400,
            code='INSUFFICIENT_POCKET_BALANCE',
            pocket_balance=pocket.current_balance,
            required_amount=amount
        )
        
    pocket.deduct_money(amount)
    current_user.wallet_balance = round((current_user.wallet_balance or 0.0) + amount, 2)
    
    tx = Transaction(
        transaction_id=Transaction.generate_transaction_id(),
        user_id=current_user.id,
        type='transfer',
        amount=amount,
        from_pocket_id=pocket.id,
        category='Pocket Withdrawal',
        description=data.get('description') or f'Withdrew ₹{amount:,.2f} from {pocket.name} to available balance',
        payment_method='internal'
    )
    db.session.add(tx)
    tx.complete()
    
    Notification.transaction_alert(current_user.id, tx)
    
    return json_response({
        'pocket': pocket.to_dict(True),
        'wallet_balance': current_user.wallet_balance,
        'transaction': tx.to_dict(True)
    }, f'₹{amount:,.2f} moved to available balance successfully')


@bp.route('/<int:pocket_id>', methods=['DELETE'])
@api_login_required
def delete_pocket(pocket_id):
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id).first()
    if not pocket:
        return error_response('Pocket not found', 404)
    
    # Check if empty_to_wallet flag is provided
    empty_to_wallet = (
        request.args.get('empty_to_wallet', 'false').lower() == 'true' or
        (request.get_json(silent=True) or {}).get('empty_to_wallet') is True
    )
    
    if pocket.current_balance > 0:
        if empty_to_wallet:
            # Safely return pocket balance back to unallocated wallet balance
            remaining = pocket.current_balance
            current_user.wallet_balance = round((current_user.wallet_balance or 0.0) + remaining, 2)
            pocket.current_balance = 0.0
            
            tx = Transaction(
                transaction_id=Transaction.generate_transaction_id(),
                user_id=current_user.id,
                type='transfer',
                amount=remaining,
                from_pocket_id=pocket.id,
                category='Pocket Closed',
                description=f'Returned remaining ₹{remaining:,.2f} from closed pocket {pocket.name} to available balance',
                payment_method='internal'
            )
            db.session.add(tx)
            tx.complete()
        else:
            return error_response(
                f'Cannot delete pocket with balance. Transfer or withdraw ₹{pocket.current_balance:,.2f} first, '
                'or select "Transfer remaining balance to Available Balance".',
                400,
                code='POCKET_HAS_BALANCE',
                remaining_balance=pocket.current_balance
            )
    
    pocket_name = pocket.name
    db.session.delete(pocket)
    db.session.commit()
    
    Notification.create(
        current_user.id,
        'Pocket Deleted',
        f'Your "{pocket_name}" pocket has been permanently deleted.',
        'info',
        'normal'
    )
    
    return json_response({
        'deleted': True,
        'wallet_balance': current_user.wallet_balance
    }, f'Pocket "{pocket_name}" deleted permanently')


@bp.route('/reorder', methods=['POST'])
@api_login_required
def reorder_pockets():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['order'])
    if not valid:
        return error_response(msg, 400)
    
    order = data['order']
    if not isinstance(order, list):
        return error_response('Order must be an array of pocket IDs', 400)
    
    pockets = Pocket.query.filter(
        Pocket.user_id == current_user.id,
        Pocket.id.in_(order),
        Pocket.archived == False
    ).all()
    
    pocket_map = {p.id: p for p in pockets}
    updated_count = 0
    
    for idx, pocket_id in enumerate(order):
        if pocket_id in pocket_map:
            pocket_map[pocket_id].sort_order = idx
            updated_count += 1
    
    db.session.commit()
    
    return json_response({
        'updated_count': updated_count
    }, f'Reordered {updated_count} pockets successfully')


@bp.route('/transfer', methods=['POST'])
@api_login_required
def transfer_between_pockets():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['from_pocket_id', 'to_pocket_id', 'amount'])
    if not valid:
        return error_response(msg, 400)
    
    from_id = data.get('from_pocket_id')
    to_id = data.get('to_pocket_id')
    amount = float(data.get('amount', 0))
    description = data.get('description', '').strip() or None
    
    if amount <= 0:
        return error_response('Transfer amount must be positive', 400)
    
    if from_id == to_id:
        return error_response('Cannot transfer to the same pocket', 400)
    
    from_pocket = Pocket.query.filter_by(id=from_id, user_id=current_user.id, archived=False).first()
    to_pocket = Pocket.query.filter_by(id=to_id, user_id=current_user.id, archived=False).first()
    
    if not from_pocket:
        return error_response('Source pocket not found', 404)
    if not to_pocket:
        return error_response('Destination pocket not found', 404)
    
    if from_pocket.current_balance < amount:
        return error_response(
            f'Insufficient balance. {from_pocket.name} has only ₹{from_pocket.current_balance:.2f}',
            400,
            code='INSUFFICIENT_BALANCE',
            available_balance=from_pocket.current_balance,
            required_amount=amount
        )
    
    try:
        from_pocket.deduct_money(amount)
        to_pocket.add_money(amount)
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    
    tx = Transaction(
        transaction_id=Transaction.generate_transaction_id(),
        user_id=current_user.id,
        type='transfer',
        amount=amount,
        from_pocket_id=from_id,
        to_pocket_id=to_id,
        description=description or f'Transfer from {from_pocket.name} to {to_pocket.name}',
        payment_method='internal'
    )
    db.session.add(tx)
    tx.complete()
    
    Notification.transaction_alert(current_user.id, tx)
    
    return json_response({
        'transaction': tx.to_dict(True),
        'from_pocket': from_pocket.to_dict(),
        'to_pocket': to_pocket.to_dict()
    }, 'Transfer completed successfully')


@bp.route('/<int:pocket_id>/transactions', methods=['GET'])
@api_login_required
def get_pocket_transactions(pocket_id):
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id).first()
    if not pocket:
        return error_response('Pocket not found', 404)
    
    query = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        ((Transaction.from_pocket_id == pocket_id) | (Transaction.to_pocket_id == pocket_id))
    ).order_by(Transaction.created_at.desc())
    
    tx_type = request.args.get('type')
    if tx_type:
        query = query.filter_by(type=tx_type)
    
    pagination = get_paginated_query(query)
    
    return json_response(paginated_response(
        pagination, lambda t: t.to_dict(True)
    ))


@bp.route('/<int:pocket_id>/qr', methods=['GET'])
@api_login_required
def get_pocket_qr(pocket_id):
    pocket = Pocket.query.filter_by(id=pocket_id, user_id=current_user.id).first()
    if not pocket:
        return error_response('Pocket not found', 404)
        
    from app.utils.helpers import build_qr_pocket_url, generate_qr_code
    scannable_url = build_qr_pocket_url(pocket)
    qr_url = generate_qr_code(scannable_url, 350)
    
    return json_response({
        'pocket_id': pocket.id,
        'pocket_name': pocket.name,
        'scannable_url': scannable_url,
        'qr_code_url': qr_url
    })
