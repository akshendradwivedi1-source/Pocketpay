import logging
from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, jsonify, current_app
from flask_login import current_user, login_user, logout_user
from sqlalchemy import func, or_, desc

from app.extensions import db
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.admin_audit_log import AdminAuditLog
from app.models.support_ticket import SupportTicket
from app.utils.helpers import (
    admin_required,
    api_admin_required,
    is_admin_user,
    json_response,
    error_response,
    get_paginated_query,
    paginated_response,
    get_admin_email
)
from app.utils.email_service import send_otp_email, send_ticket_resolution_email

logger = logging.getLogger(__name__)

bp = Blueprint('admin', __name__)


# =============================================================================
# ADMIN AUTHENTICATION ROUTES
# =============================================================================

@bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """Dedicated Admin Login page with server-side credentials authentication"""
    if request.method == 'GET':
        if current_user.is_authenticated and is_admin_user(current_user):
            return redirect(url_for('admin.dashboard'))
        return render_template('admin/login.html', admin_email=get_admin_email())
    
    # POST
    data = request.get_json(silent=True) if request.is_json else request.form
    email = (data.get('email') or data.get('username') or '').strip().lower()
    password = data.get('password') or ''
    remember = bool(data.get('remember', False))
    next_url = request.args.get('next') or url_for('admin.dashboard')
    
    if not email or not password:
        err = 'Email and password are required'
        if request.is_json:
            return error_response(err, 400)
        return render_template('admin/login.html', error=err, admin_email=get_admin_email()), 400
        
    user = User.query.filter_by(email=email).first()
    if not user or not user.verify_password(password) or not is_admin_user(user):
        err = 'Invalid admin credentials or unauthorized account.'
        if request.is_json:
            return error_response(err, 401)
        return render_template('admin/login.html', error=err, email=email, admin_email=get_admin_email()), 401
        
    if not user.is_active:
        err = 'Admin account is deactivated.'
        if request.is_json:
            return error_response(err, 403)
        return render_template('admin/login.html', error=err, admin_email=get_admin_email()), 403
        
    login_user(user, remember=remember, force=True)
    user.last_login_at = datetime.utcnow()
    db.session.commit()
    
    AdminAuditLog.record(
        admin_email=user.email,
        action='admin_login',
        target_type='admin_session',
        target_id=str(user.id),
        details={'email': user.email, 'login_time': datetime.utcnow().isoformat()}
    )
    
    if request.is_json:
        return json_response({'user': serialize_admin_user(user), 'next_url': next_url}, 'Admin authenticated successfully')
        
    return redirect(next_url)


@bp.route('/logout', methods=['GET', 'POST'])
def admin_logout():
    """Logs out admin and redirects back to dedicated admin login"""
    if current_user.is_authenticated:
        AdminAuditLog.record(
            admin_email=getattr(current_user, 'email', 'unknown'),
            action='admin_logout',
            target_type='admin_session',
            target_id=str(getattr(current_user, 'id', ''))
        )
        logout_user()
    if request.is_json:
        return json_response(message='Admin logged out successfully')
    return redirect(url_for('admin.admin_login'))



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
    premium_users = User.query.filter_by(is_premium=True).count()
    free_users = User.query.filter(or_(User.is_premium == False, User.is_premium == None)).count()

    total_pockets = Pocket.query.filter_by(archived=False).count()
    total_pockets_balance = float(db.session.query(func.coalesce(func.sum(Pocket.current_balance), 0.0)).filter_by(archived=False).scalar() or 0.0)
    total_wallet_balance = float(db.session.query(func.coalesce(func.sum(User.wallet_balance), 0.0)).scalar() or 0.0)
    total_platform_funds = round(total_wallet_balance + total_pockets_balance, 2)

    total_transactions = Transaction.query.count()
    completed_transactions = Transaction.query.filter_by(status='completed').count()
    failed_transactions = Transaction.query.filter_by(status='failed').count()
    pending_transactions = Transaction.query.filter_by(status='pending').count()
    gross_volume = float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0.0)).filter_by(status='completed').scalar() or 0.0)

    return {
        'total_users': total_users,
        'verified_users': verified_users,
        'pending_approvals': pending_approvals,
        'active_users': active_users,
        'suspended_users': suspended_users,
        'premium_users': premium_users,
        'free_users': free_users,
        'total_pockets': total_pockets,
        'total_pockets_balance': total_pockets_balance,
        'total_wallet_balance': total_wallet_balance,
        'total_platform_funds': total_platform_funds,
        'total_transactions': total_transactions,
        'completed_transactions': completed_transactions,
        'failed_transactions': failed_transactions,
        'pending_transactions': pending_transactions,
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
        'is_premium': bool(u.is_premium),
        'is_admin': bool(u.is_admin),
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


@bp.route('/resolution')
@admin_required
def resolution():
    """Transaction Failure Resolution Interface"""
    metrics = get_live_admin_metrics()
    return render_template(
        'admin/resolution.html',
        metrics=metrics,
        admin_email=get_admin_email(),
        active_page='resolution'
    )


@bp.route('/support')
@admin_required
def support():
    """Support Ticket Management Page"""
    metrics = get_live_admin_metrics()
    open_count = SupportTicket.query.filter(SupportTicket.status.in_(['OPEN', 'IN_PROGRESS'])).count()
    return render_template(
        'admin/support.html',
        metrics=metrics,
        open_ticket_count=open_count,
        admin_email=get_admin_email(),
        active_page='support'
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
    elif status == 'premium':
        query = query.filter(User.is_premium == True)
    elif status == 'free':
        query = query.filter(or_(User.is_premium == False, User.is_premium == None))

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

    if user.email.lower() in {get_admin_email().lower(), 'akshendra.dwivedi1@gmail.com', 'admin@pocketpay.app'}:
        return error_response('Cannot modify status of a protected root administrator account', 400)

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


@bp.route('/api/users/<int:user_id>/toggle-premium', methods=['POST'])
@api_admin_required
def api_toggle_user_premium(user_id):
    """Toggles user demo premium subscription tier"""
    user = db.session.get(User, user_id)
    if not user:
        return error_response('User not found', 404)

    user.is_premium = not user.is_premium
    db.session.commit()

    AdminAuditLog.record(
        admin_email=current_user.email,
        action='toggle_premium',
        target_type='user',
        target_id=str(user.id),
        details={'user_email': user.email, 'new_status': 'premium' if user.is_premium else 'free'}
    )

    return json_response({
        'id': user.id,
        'is_premium': user.is_premium
    }, f"User {user.full_name} is now {'Premium' if user.is_premium else 'Free'}.")


@bp.route('/api/users/<int:user_id>/delete', methods=['DELETE', 'POST'])
@api_admin_required
def api_delete_user(user_id):
    """
    Administrative account deletion/closure with audit logging.
    - Soft-deletes user record and frees up email/phone for re-registration
    - Preserves historical transaction ledger for audit and compliance
    - Archives pockets and disconnects auxiliary integrations
    - Records administrative action in AdminAuditLog
    """
    user = db.session.get(User, user_id)
    if not user:
        return error_response('User not found', 404)

    if user.email.lower() in {get_admin_email().lower(), 'akshendra.dwivedi1@gmail.com', 'admin@pocketpay.app'}:
        return error_response('Cannot delete root administrator account', 400)

    email = user.email
    full_name = user.full_name

    try:
        # 1. Archive pockets
        Pocket.query.filter_by(user_id=user_id).update({'archived': True})

        # 2. Disconnect Telegram user link
        from app.models.telegram_user import TelegramUser
        TelegramUser.query.filter_by(user_id=user_id).delete()

        # 3. Clean up money requests
        from app.models.money_request import MoneyRequest
        MoneyRequest.query.filter(
            (MoneyRequest.requester_id == user_id) | (MoneyRequest.target_user_id == user_id)
        ).delete()

        # 4. Clean up auxiliary entities
        from app.models.goal import SavingsGoal
        from app.models.budget import Budget
        from app.models.distribution_rule import DistributionRule
        from app.models.notification import Notification

        SavingsGoal.query.filter_by(user_id=user_id).delete()
        Budget.query.filter_by(user_id=user_id).delete()
        DistributionRule.query.filter_by(user_id=user_id).delete()
        Notification.query.filter_by(user_id=user_id).delete()

        # 5. Soft-delete user (anonymizes PII, frees email/phone, preserves transaction history)
        user.soft_delete()

        db.session.commit()

        # 6. Audit Logging
        AdminAuditLog.record(
            admin_email=current_user.email,
            action='admin_delete_user',
            target_type='user',
            target_id=str(user_id),
            details={
                'user_email': email,
                'full_name': full_name,
                'soft_deleted': True,
                'timestamp': datetime.utcnow().isoformat()
            }
        )

        return json_response(
            {'id': user_id, 'deleted': True},
            f"User account for {full_name} ({email}) closed and deleted successfully."
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"[Admin Delete User Error] user_id={user_id}: {str(e)}")
        return error_response(f"Failed to delete user account: {str(e)}", 500)


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


@bp.route('/api/analytics/charts', methods=['GET'])
@api_admin_required
def api_analytics_charts():
    """Generates real database charts data (7-day volume, category split, user growth)"""
    from datetime import datetime, timedelta

    # 1. 7-Day Daily Transaction Volume from Real Database Records
    daily_volume = []
    today = datetime.utcnow().date()
    for i in range(6, -1, -1):
        day_date = today - timedelta(days=i)
        day_start = datetime.combine(day_date, datetime.min.time())
        day_end = datetime.combine(day_date, datetime.max.time())
        
        day_txs = Transaction.query.filter(
            Transaction.created_at >= day_start,
            Transaction.created_at <= day_end,
            Transaction.status == 'completed'
        ).all()
        
        day_vol = sum(t.amount for t in day_txs)
        daily_volume.append({
            'date': day_date.strftime('%b %d'),
            'volume': round(day_vol, 2),
            'count': len(day_txs)
        })

    # 2. Category Breakdown from Real Database Transactions
    cat_query = db.session.query(
        Transaction.category,
        func.count(Transaction.id).label('tx_count'),
        func.coalesce(func.sum(Transaction.amount), 0.0).label('total_amount')
    ).filter(
        Transaction.status == 'completed'
    ).group_by(Transaction.category).all()

    category_breakdown = [{
        'category': row[0] or 'General',
        'count': row[1],
        'amount': float(row[2])
    } for row in cat_query]

    # 3. User Growth (Past 7 days)
    user_growth = []
    for i in range(6, -1, -1):
        day_date = today - timedelta(days=i)
        day_start = datetime.combine(day_date, datetime.min.time())
        day_end = datetime.combine(day_date, datetime.max.time())
        
        reg_count = User.query.filter(
            User.created_at >= day_start,
            User.created_at <= day_end
        ).count()
        
        user_growth.append({
            'date': day_date.strftime('%b %d'),
            'registrations': reg_count
        })

    return json_response({
        'daily_volume': daily_volume,
        'category_breakdown': category_breakdown,
        'user_growth': user_growth,
        'generated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    }, 'Live chart analytics retrieved successfully')


@bp.route('/api/recent-activity', methods=['GET'])
@api_admin_required
def api_recent_activity():
    """Returns chronological live activity feed combining audit logs, transactions, and user registrations"""
    activity = []

    # Audit Logs
    audit_logs = AdminAuditLog.query.order_by(AdminAuditLog.created_at.desc()).limit(15).all()
    for al in audit_logs:
        activity.append({
            'type': 'audit',
            'title': f"Admin Action: {al.action.replace('_', ' ').title()}",
            'description': f"By {al.admin_email} on {al.target_type} ({al.target_id})",
            'timestamp': al.created_at.strftime('%Y-%m-%d %H:%M:%S') if al.created_at else None,
            'raw_time': al.created_at or datetime.min
        })

    # Recent Transactions
    recent_txs = Transaction.query.order_by(Transaction.created_at.desc()).limit(15).all()
    for tx in recent_txs:
        u = db.session.get(User, tx.user_id) if tx.user_id else None
        u_name = u.full_name if u else 'User'
        activity.append({
            'type': 'transaction',
            'title': f"Transaction {tx.type.upper()}: ₹{tx.amount:,.2f}",
            'description': f"{u_name} ({tx.status}) - {tx.category or 'General'}",
            'timestamp': tx.created_at.strftime('%Y-%m-%d %H:%M:%S') if tx.created_at else None,
            'raw_time': tx.created_at or datetime.min
        })

    # Sort merged activity descending by timestamp
    activity.sort(key=lambda x: x['raw_time'], reverse=True)
    for item in activity:
        item.pop('raw_time', None)

    return json_response(activity[:20], 'Recent live activity feed retrieved')


# =============================================================================
# SUPPORT TICKET API ENDPOINTS
# =============================================================================

def serialize_ticket(t):
    """Serializes a SupportTicket for admin display"""
    return {
        'id': t.id,
        'ticket_number': t.ticket_number,
        'user_id': t.user_id,
        'name': t.name,
        'email': t.email,
        'category': t.category,
        'subject': t.subject,
        'description': t.description,
        'transaction_id': t.transaction_id,
        'status': t.status,
        'admin_notes': t.admin_notes,
        'admin_response': t.admin_response,
        'resolved_by': t.resolved_by,
        'resolved_at': t.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if t.resolved_at else None,
        'created_at': t.created_at.strftime('%Y-%m-%d %H:%M:%S') if t.created_at else None,
        'updated_at': t.updated_at.strftime('%Y-%m-%d %H:%M:%S') if t.updated_at else None,
    }


@bp.route('/api/support/tickets', methods=['GET'])
@api_admin_required
def api_support_tickets():
    """Paginated, searchable, filterable support tickets"""
    q = request.args.get('q', '').strip()
    status = request.args.get('status', 'all').strip()
    category = request.args.get('category', 'all').strip()

    query = SupportTicket.query

    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                SupportTicket.ticket_number.ilike(search),
                SupportTicket.name.ilike(search),
                SupportTicket.email.ilike(search),
                SupportTicket.subject.ilike(search),
                SupportTicket.description.ilike(search),
                SupportTicket.transaction_id.ilike(search)
            )
        )

    if status != 'all':
        query = query.filter(SupportTicket.status == status.upper())

    if category != 'all':
        query = query.filter(SupportTicket.category == category)

    query = query.order_by(SupportTicket.created_at.desc())
    pagination = get_paginated_query(query)
    return json_response(paginated_response(pagination, serialize_ticket))


@bp.route('/api/support/tickets/<int:ticket_id>', methods=['GET'])
@api_admin_required
def api_support_ticket_detail(ticket_id):
    """Returns full detail for a single support ticket"""
    ticket = db.session.get(SupportTicket, ticket_id)
    if not ticket:
        return error_response('Ticket not found', 404)
    return json_response(serialize_ticket(ticket), 'Ticket retrieved')


@bp.route('/api/support/tickets/<int:ticket_id>/respond', methods=['POST'])
@api_admin_required
def api_support_ticket_respond(ticket_id):
    """Responds to a support ticket and optionally changes its status"""
    ticket = db.session.get(SupportTicket, ticket_id)
    if not ticket:
        return error_response('Ticket not found', 404)

    data = request.get_json() or {}
    admin_response = str(data.get('response') or data.get('admin_response') or '').strip()
    if not admin_response:
        return error_response('A response message is required', 400)

    new_status = str(data.get('status') or '').strip().upper() or 'RESOLVED'
    valid_statuses = {'OPEN', 'IN_PROGRESS', 'WAITING_FOR_USER', 'RESOLVED', 'CLOSED'}
    if new_status not in valid_statuses:
        new_status = 'RESOLVED'

    admin_notes = str(data.get('admin_notes') or '').strip()

    ticket.admin_response = admin_response
    ticket.status = new_status
    ticket.resolved_by = current_user.email
    ticket.resolved_at = datetime.utcnow()
    if admin_notes:
        ticket.admin_notes = admin_notes
    ticket.updated_at = datetime.utcnow()
    db.session.commit()

    # Email the user with resolution
    try:
        send_ticket_resolution_email(ticket, admin_response, current_user.email)
    except Exception as e:
        logger.warning(f"Could not send resolution email for ticket {ticket_id}: {e}")

    AdminAuditLog.record(
        admin_email=current_user.email,
        action='respond_support_ticket',
        target_type='support_ticket',
        target_id=str(ticket_id),
        details={
            'ticket_number': ticket.ticket_number,
            'status': new_status,
            'user_email': ticket.email
        }
    )

    return json_response(serialize_ticket(ticket), f'Ticket {ticket.ticket_number} updated and resolution email dispatched.')


@bp.route('/api/support/tickets/<int:ticket_id>/status', methods=['POST'])
@api_admin_required
def api_support_ticket_status(ticket_id):
    """Updates ticket status without responding"""
    ticket = db.session.get(SupportTicket, ticket_id)
    if not ticket:
        return error_response('Ticket not found', 404)

    data = request.get_json() or {}
    new_status = str(data.get('status') or '').strip().upper()
    valid_statuses = {'OPEN', 'IN_PROGRESS', 'WAITING_FOR_USER', 'RESOLVED', 'CLOSED'}
    if new_status not in valid_statuses:
        return error_response(f'Invalid status. Choose from: {", ".join(valid_statuses)}', 400)

    ticket.status = new_status
    ticket.updated_at = datetime.utcnow()
    db.session.commit()

    AdminAuditLog.record(
        admin_email=current_user.email,
        action='update_ticket_status',
        target_type='support_ticket',
        target_id=str(ticket_id),
        details={'ticket_number': ticket.ticket_number, 'status': new_status}
    )

    return json_response(serialize_ticket(ticket), f'Ticket status updated to {new_status}')


@bp.route('/api/support/stats', methods=['GET'])
@api_admin_required
def api_support_stats():
    """Returns support ticket summary statistics"""
    total = SupportTicket.query.count()
    open_count = SupportTicket.query.filter_by(status='OPEN').count()
    in_progress = SupportTicket.query.filter_by(status='IN_PROGRESS').count()
    resolved = SupportTicket.query.filter(SupportTicket.status.in_(['RESOLVED', 'CLOSED'])).count()
    return json_response({
        'total': total,
        'open': open_count,
        'in_progress': in_progress,
        'resolved': resolved
    }, 'Support stats retrieved')


# =============================================================================
# TRANSACTION RESOLUTION API ENDPOINTS
# =============================================================================

@bp.route('/api/resolution/transactions', methods=['GET'])
@api_admin_required
def api_resolution_transactions():
    """Returns paginated list of failed, pending, or disputed transactions for resolution"""
    q = request.args.get('q', '').strip()
    status = request.args.get('status', 'failed').strip()

    query = Transaction.query

    # Default to showing failed + pending
    if status == 'all':
        query = query.filter(Transaction.status.in_(['failed', 'pending', 'disputed']))
    else:
        query = query.filter(Transaction.status == status)

    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                Transaction.transaction_id.ilike(search),
                Transaction.merchant.ilike(search),
                Transaction.description.ilike(search),
                Transaction.upi_reference.ilike(search)
            )
        )

    query = query.order_by(Transaction.created_at.desc())
    pagination = get_paginated_query(query)
    return json_response(paginated_response(pagination, serialize_admin_transaction))


@bp.route('/api/resolution/transactions/<int:tx_id>/refund', methods=['POST'])
@api_admin_required
def api_resolve_refund(tx_id):
    """
    Refunds a failed/disputed transaction — restores money to the user's wallet.
    Atomic: creates a refund Transaction record and credits the user's wallet.
    """
    tx = db.session.get(Transaction, tx_id)
    if not tx:
        return error_response('Transaction not found', 404)

    if tx.status not in ('failed', 'pending', 'disputed'):
        return error_response(f'Cannot refund a transaction with status "{tx.status}"', 400)

    user = db.session.get(User, tx.user_id)
    if not user:
        return error_response('Associated user not found', 404)

    data = request.get_json() or {}
    reason = str(data.get('reason') or 'Admin-initiated refund').strip()

    try:
        # Credit refund amount back to user wallet
        user.wallet_balance = round((user.wallet_balance or 0.0) + tx.amount, 2)

        # Mark original transaction as refunded
        tx.status = 'refunded'
        tx.description = f"[REFUNDED] {tx.description or ''} | Reason: {reason}"

        # Create a refund credit transaction for the audit trail
        refund_tx = Transaction(
            transaction_id=Transaction.generate_transaction_id(),
            user_id=user.id,
            type='refund',
            amount=tx.amount,
            category='Admin Refund',
            merchant='PocketPay Admin',
            description=f'Refund for Tx {tx.transaction_id}: {reason}',
            payment_method='admin_resolution',
            status='completed'
        )
        refund_tx.status = 'completed'
        db.session.add(refund_tx)
        db.session.commit()

        AdminAuditLog.record(
            admin_email=current_user.email,
            action='refund_transaction',
            target_type='transaction',
            target_id=str(tx_id),
            details={
                'transaction_id': tx.transaction_id,
                'amount': tx.amount,
                'user_email': user.email,
                'reason': reason
            }
        )

        return json_response({
            'transaction_id': tx.transaction_id,
            'refund_tx_id': refund_tx.transaction_id,
            'amount': tx.amount,
            'user_email': user.email,
            'new_wallet_balance': user.wallet_balance
        }, f'₹{tx.amount:.2f} refunded to {user.full_name} ({user.email}) — wallet credited.')

    except Exception as e:
        db.session.rollback()
        logger.error(f'[Admin] Refund failed for tx {tx_id}: {e}')
        return error_response(f'Refund failed: {str(e)}', 500)


@bp.route('/api/resolution/transactions/<int:tx_id>/complete', methods=['POST'])
@api_admin_required
def api_resolve_complete(tx_id):
    """
    Force-completes a pending/stuck transaction.
    Use only when funds were confirmed transferred externally.
    """
    tx = db.session.get(Transaction, tx_id)
    if not tx:
        return error_response('Transaction not found', 404)

    if tx.status not in ('pending', 'failed'):
        return error_response(f'Cannot force-complete a transaction with status "{tx.status}"', 400)

    data = request.get_json() or {}
    reason = str(data.get('reason') or 'Admin force-completed').strip()

    try:
        tx.status = 'completed'
        tx.description = f"[FORCE-COMPLETED] {tx.description or ''} | Admin: {reason}"
        db.session.commit()

        AdminAuditLog.record(
            admin_email=current_user.email,
            action='force_complete_transaction',
            target_type='transaction',
            target_id=str(tx_id),
            details={
                'transaction_id': tx.transaction_id,
                'amount': tx.amount,
                'reason': reason
            }
        )

        return json_response(
            serialize_admin_transaction(tx),
            f'Transaction {tx.transaction_id} force-completed successfully.'
        )

    except Exception as e:
        db.session.rollback()
        return error_response(f'Force-complete failed: {str(e)}', 500)


@bp.route('/api/resolution/transactions/<int:tx_id>/escalate', methods=['POST'])
@api_admin_required
def api_resolve_escalate(tx_id):
    """Marks a transaction as disputed for further escalation review"""
    tx = db.session.get(Transaction, tx_id)
    if not tx:
        return error_response('Transaction not found', 404)

    data = request.get_json() or {}
    reason = str(data.get('reason') or 'Escalated by admin for senior review').strip()

    try:
        tx.status = 'disputed'
        tx.description = f"[ESCALATED] {tx.description or ''} | Reason: {reason}"
        db.session.commit()

        AdminAuditLog.record(
            admin_email=current_user.email,
            action='escalate_transaction',
            target_type='transaction',
            target_id=str(tx_id),
            details={
                'transaction_id': tx.transaction_id,
                'reason': reason
            }
        )

        return json_response(
            serialize_admin_transaction(tx),
            f'Transaction {tx.transaction_id} escalated for senior review.'
        )

    except Exception as e:
        db.session.rollback()
        return error_response(f'Escalate failed: {str(e)}', 500)
