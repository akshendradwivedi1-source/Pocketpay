import logging
from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, jsonify, current_app
from flask_login import current_user
from sqlalchemy import func, or_, desc

from app.extensions import db
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.admin_audit_log import AdminAuditLog
from app.utils.helpers import (
    admin_required,
    api_admin_required,
    json_response,
    error_response,
    get_paginated_query,
    paginated_response,
    get_admin_email
)
from app.utils.email_service import send_otp_email

logger = logging.getLogger(__name__)

bp = Blueprint('admin', __name__)


# =============================================================================
# HELPER QUERY FUNCTIONS (Real Live DB Metrics)
# =============================================================================

def get_live_admin_metrics():
    """Computes real live aggregates directly from the database"""
    total_users = User.query.count()
    verified_users = User.query.filter_by(email_verified=True).count()
    pending_approvals = User.query.filter(User.otp_approval_status == 'pending_admin_approval').count()
    active_users = User.query.filter_by(is_active=True).count()
    suspended_users = User.query.filter_by(is_active=False).count()

    total_pockets = Pocket.query.filter_by(archived=False).count()
    total_pockets_balance = float(db.session.query(func.coalesce(func.sum(Pocket.current_balance), 0.0)).filter_by(archived=False).scalar() or 0.0)
    total_wallet_balance = float(db.session.query(func.coalesce(func.sum(User.wallet_balance), 0.0)).scalar() or 0.0)
    total_platform_funds = round(total_wallet_balance + total_pockets_balance, 2)

    total_transactions = Transaction.query.count()
    completed_transactions = Transaction.query.filter_by(status='completed').count()
    failed_transactions = Transaction.query.filter_by(status='failed').count()
    gross_volume = float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0.0)).filter_by(status='completed').scalar() or 0.0)

    return {
        'total_users': total_users,
        'verified_users': verified_users,
        'pending_approvals': pending_approvals,
        'active_users': active_users,
        'suspended_users': suspended_users,
        'total_pockets': total_pockets,
        'total_pockets_balance': total_pockets_balance,
        'total_wallet_balance': total_wallet_balance,
        'total_platform_funds': total_platform_funds,
        'total_transactions': total_transactions,
        'completed_transactions': completed_transactions,
        'failed_transactions': failed_transactions,
        'gross_volume': gross_volume,
        'admin_email': get_admin_email(),
        'last_updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    }


def serialize_admin_user(u):
    """Sanitizes user for admin display (Strictly NO passwords, OTPs, or secrets)"""
    pockets_count = u.pockets.filter_by(archived=False).count() if hasattr(u, 'pockets') else 0
    tx_count = u.transactions.count() if hasattr(u, 'transactions') else 0
    return {
        'id': u.id,
        'uuid': u.uuid,
        'full_name': u.full_name,
        'email': u.email,
        'phone': u.phone,
        'email_verified': u.email_verified,
        'phone_verified': u.phone_verified,
        'is_active': u.is_active,
        'wallet_balance': u.wallet_balance or 0.0,
        'virtual_wallet_id': u.virtual_wallet_id,
        'virtual_upi_id': u.virtual_upi_id,
        'otp_approval_status': u.otp_approval_status or 'none',
        'totp_enabled': bool(u.totp_enabled),
        'has_pin': bool(u.transaction_pin_hash),
        'pockets_count': pockets_count,
        'transactions_count': tx_count,
        'linked_banks_count': len(u.linked_banks or []),
        'created_at': u.created_at.strftime('%Y-%m-%d %H:%M:%S') if u.created_at else None,
        'last_login_at': u.last_login_at.strftime('%Y-%m-%d %H:%M:%S') if u.last_login_at else 'Never'
    }


def serialize_admin_transaction(t):
    """Sanitizes transaction for admin audit log"""
    user = db.session.get(User, t.user_id) if t.user_id else None
    return {
        'id': t.id,
        'transaction_id': t.transaction_id,
        'user_id': t.user_id,
        'user_name': user.full_name if user else 'Unknown',
        'user_email': user.email if user else 'Unknown',
        'type': t.type,
        'amount': t.amount,
        'status': t.status,
        'category': t.category,
        'merchant': t.merchant,
        'payment_method': t.payment_method,
        'description': t.description,
        'upi_reference': t.upi_reference,
        'created_at': t.created_at.strftime('%Y-%m-%d %H:%M:%S') if t.created_at else None
    }


def serialize_admin_pocket(p):
    """Sanitizes pocket for admin audit"""
    user = db.session.get(User, p.user_id) if p.user_id else None
    return {
        'id': p.id,
        'user_id': p.user_id,
        'user_name': user.full_name if user else 'Unknown',
        'user_email': user.email if user else 'Unknown',
        'name': p.name,
        'current_balance': p.current_balance,
        'budget_amount': p.budget_amount,
        'total_spent': p.total_spent,
        'total_received': p.total_received,
        'color': p.color,
        'icon': p.icon,
        'archived': p.archived,
        'created_at': p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else None
    }


# =============================================================================
# HTML ADMIN PAGES (Server-rendered)
# =============================================================================

@bp.route('/')
@bp.route('/dashboard')
@admin_required
def dashboard():
    """Main Admin Dashboard with live stats, pending approvals, and recent activity"""
    metrics = get_live_admin_metrics()
    
    # Live Recent Registrations
    recent_users = User.query.order_by(User.created_at.desc()).limit(6).all()
    # Live Recent Transactions
    recent_txs = Transaction.query.order_by(Transaction.created_at.desc()).limit(6).all()
    # Live Pending Approvals
    pending_users = User.query.filter(User.otp_approval_status == 'pending_admin_approval').order_by(User.created_at.desc()).limit(10).all()

    return render_template(
        'admin/dashboard.html',
        metrics=metrics,
        recent_users=[serialize_admin_user(u) for u in recent_users],
        recent_txs=[serialize_admin_transaction(t) for t in recent_txs],
        pending_users=[serialize_admin_user(u) for u in pending_users],
        admin_email=get_admin_email(),
        active_page='dashboard'
    )


@bp.route('/users')
@admin_required
def users():
    """User Management Page"""
    metrics = get_live_admin_metrics()
    return render_template(
        'admin/users.html',
        metrics=metrics,
        admin_email=get_admin_email(),
        active_page='users'
    )


@bp.route('/approvals')
@admin_required
def approvals():
    """Pending Registration & OTP Approvals Queue"""
    metrics = get_live_admin_metrics()
    pending_users = User.query.filter(User.otp_approval_status == 'pending_admin_approval').order_by(User.created_at.desc()).all()
    return render_template(
        'admin/approvals.html',
        metrics=metrics,
        pending_users=[serialize_admin_user(u) for u in pending_users],
        admin_email=get_admin_email(),
        active_page='approvals'
    )


@bp.route('/pockets')
@admin_required
def pockets():
    """Platform Pockets Overview Page"""
    metrics = get_live_admin_metrics()
    return render_template(
        'admin/pockets.html',
        metrics=metrics,
        admin_email=get_admin_email(),
        active_page='pockets'
    )


@bp.route('/transactions')
@admin_required
def transactions():
    """Platform Transactions Ledger Page"""
    metrics = get_live_admin_metrics()
    return render_template(
        'admin/transactions.html',
        metrics=metrics,
        admin_email=get_admin_email(),
        active_page='transactions'
    )


@bp.route('/audit-logs')
@admin_required
def audit_logs():
    """Admin Action Audit Trail Page"""
    metrics = get_live_admin_metrics()
    return render_template(
        'admin/audit_logs.html',
        metrics=metrics,
        admin_email=get_admin_email(),
        active_page='audit_logs'
    )


# =============================================================================
# JSON API ENDPOINTS (Protected with @api_admin_required)
# =============================================================================

@bp.route('/api/stats', methods=['GET'])
@api_admin_required
def api_stats():
    """Returns live database metrics in JSON"""
    metrics = get_live_admin_metrics()
    return json_response(metrics, 'Live admin metrics retrieved successfully')


@bp.route('/api/users', methods=['GET'])
@api_admin_required
def api_users():
    """Paginated, searchable, filterable users query"""
    q = request.args.get('q', '').strip()
    status = request.args.get('status', 'all').strip()

    query = User.query

    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search),
                User.email.ilike(search),
                User.phone.ilike(search),
                User.uuid.ilike(search)
            )
        )

    if status == 'verified':
        query = query.filter(User.email_verified == True)
    elif status == 'pending':
        query = query.filter(User.otp_approval_status == 'pending_admin_approval')
    elif status == 'active':
        query = query.filter(User.is_active == True)
    elif status == 'suspended':
        query = query.filter(User.is_active == False)

    query = query.order_by(User.created_at.desc())
    pagination = get_paginated_query(query)

    return json_response(paginated_response(pagination, serialize_admin_user))


@bp.route('/api/users/<int:user_id>', methods=['GET'])
@api_admin_required
def api_user_detail(user_id):
    """Detailed user profile with associated pockets and transaction count"""
    user = db.session.get(User, user_id)
    if not user:
        return error_response('User not found', 404)

    pockets = Pocket.query.filter_by(user_id=user.id, archived=False).all()
    recent_txs = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).limit(10).all()

    data = serialize_admin_user(user)
    data['pockets'] = [serialize_admin_pocket(p) for p in pockets]
    data['recent_transactions'] = [serialize_admin_transaction(t) for t in recent_txs]
    data['linked_banks'] = user.linked_banks or []

    return json_response(data, 'User details retrieved')


@bp.route('/api/users/<int:user_id>/toggle-status', methods=['POST'])
@api_admin_required
def api_toggle_user_status(user_id):
    """Activates or suspends a user account"""
    user = db.session.get(User, user_id)
    if not user:
        return error_response('User not found', 404)

    if user.email.lower() == get_admin_email():
        return error_response('Cannot suspend the primary administrator account', 400)

    user.is_active = not user.is_active
    db.session.commit()

    action = 'activate_user' if user.is_active else 'suspend_user'
    AdminAuditLog.record(
        admin_email=current_user.email,
        action=action,
        target_type='user',
        target_id=str(user.id),
        details={'user_email': user.email, 'new_status': 'active' if user.is_active else 'suspended'}
    )

    status_str = 'activated' if user.is_active else 'suspended'
    return json_response(
        {'id': user.id, 'is_active': user.is_active},
        f"User {user.full_name} ({user.email}) has been {status_str}."
    )


@bp.route('/api/approvals', methods=['GET'])
@api_admin_required
def api_approvals():
    """Lists pending registration approvals"""
    pending_users = User.query.filter(User.otp_approval_status == 'pending_admin_approval').order_by(User.created_at.desc()).all()
    return json_response([serialize_admin_user(u) for u in pending_users], 'Pending approvals retrieved')


@bp.route('/api/approvals/<int:user_id>/approve', methods=['POST'])
@api_admin_required
def api_approve_registration(user_id):
    """Approves user registration and dispatches OTP email directly"""
    user = db.session.get(User, user_id)
    if not user:
        return error_response('User not found', 404)

    if user.otp_approval_status != 'pending_admin_approval':
        return error_response('This user is not pending admin approval', 400)

    try:
        # Generate 6-digit OTP
        otp = user.generate_otp(for_email=True)
        # Invalidate single-use approval token & mark approved
        user.otp_approval_token = None
        user.otp_approval_status = 'approved_sent'
        user.otp_approved_at = datetime.utcnow()
        db.session.commit()

        # Send OTP email
        send_otp_email(user.email, otp, user.full_name, 'verification')

        # Audit Log
        AdminAuditLog.record(
            admin_email=current_user.email,
            action='approve_registration',
            target_type='user',
            target_id=str(user.id),
            details={'user_email': user.email, 'action': 'OTP generated and emailed to user'}
        )

        return json_response(
            serialize_admin_user(user),
            f"Approved! 6-digit verification code has been dispatched to {user.email}."
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Admin] Error approving user {user_id}: {str(e)}")
        return error_response(f"Failed to approve registration: {str(e)}", 500)


@bp.route('/api/approvals/<int:user_id>/reject', methods=['POST'])
@api_admin_required
def api_reject_registration(user_id):
    """Rejects pending registration request"""
    user = db.session.get(User, user_id)
    if not user:
        return error_response('User not found', 404)

    user.otp_approval_status = 'rejected'
    user.otp_approval_token = None
    db.session.commit()

    AdminAuditLog.record(
        admin_email=current_user.email,
        action='reject_registration',
        target_type='user',
        target_id=str(user.id),
        details={'user_email': user.email}
    )

    return json_response(
        serialize_admin_user(user),
        f"Registration request for {user.full_name} ({user.email}) rejected."
    )


@bp.route('/api/pockets', methods=['GET'])
@api_admin_required
def api_pockets():
    """Paginated platform pockets list"""
    q = request.args.get('q', '').strip()
    query = Pocket.query.filter_by(archived=False)

    if q:
        search = f"%{q}%"
        query = query.filter(Pocket.name.ilike(search))

    query = query.order_by(Pocket.created_at.desc())
    pagination = get_paginated_query(query)

    return json_response(paginated_response(pagination, serialize_admin_pocket))


@bp.route('/api/transactions', methods=['GET'])
@api_admin_required
def api_transactions():
    """Paginated, filterable platform transaction ledger"""
    q = request.args.get('q', '').strip()
    tx_type = request.args.get('type', 'all').strip()
    status = request.args.get('status', 'all').strip()

    query = Transaction.query

    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                Transaction.transaction_id.ilike(search),
                Transaction.merchant.ilike(search),
                Transaction.category.ilike(search),
                Transaction.description.ilike(search),
                Transaction.upi_reference.ilike(search)
            )
        )

    if tx_type != 'all':
        query = query.filter(Transaction.type == tx_type)

    if status != 'all':
        query = query.filter(Transaction.status == status)

    query = query.order_by(Transaction.created_at.desc())
    pagination = get_paginated_query(query)

    return json_response(paginated_response(pagination, serialize_admin_transaction))


@bp.route('/api/audit-logs', methods=['GET'])
@api_admin_required
def api_audit_logs():
    """Paginated admin audit logs"""
    query = AdminAuditLog.query.order_by(AdminAuditLog.created_at.desc())
    pagination = get_paginated_query(query)

    def serialize_log(entry):
        return entry.to_dict()

    return json_response(paginated_response(pagination, serialize_log))
