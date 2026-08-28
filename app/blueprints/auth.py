import re
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_user, logout_user, login_required, current_user
from email_validator import validate_email, EmailNotValidError
from app.extensions import db, mail
from app.models.user import User
from app.models.notification import Notification
from app.models.transaction import Transaction
from app.utils.helpers import json_response, error_response, validate_required_fields, api_login_required, generate_qr_code
from app.utils.email_service import send_otp_email, send_admin_otp_request_notification

bp = Blueprint('auth', __name__)


@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    
    valid, msg = validate_required_fields(data, ['full_name', 'email', 'password'])
    if not valid:
        return error_response(msg, 400)
    
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip() or None
    password = data.get('password', '')
    password_confirm = data.get('password_confirm') or data.get('confirm_password')
    
    if len(password) < 8:
        return error_response('Password must be at least 8 characters', 400)
    if password_confirm and password != password_confirm:
        return error_response('Passwords do not match. Please re-enter your password.', 400)
    if len(full_name) < 2:
        return error_response('Full name must be at least 2 characters', 400)
    
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError as e:
        return error_response(f'Invalid email address: {str(e)}', 400)
    
    if phone and not re.match(r'^[+\d][\d\s\-\(\)]{8,}$', phone):
        return error_response('Invalid phone number format', 400)
    
    if User.query.filter_by(email=email).first():
        return error_response('An account with this email already exists', 409)
    
    if phone and User.query.filter_by(phone=phone).first():
        return error_response('Phone number already registered', 409)
    
    try:
        user = User(
            full_name=full_name,
            email=email,
            phone=phone,
            password=password,
            email_verified=False
        )
        db.session.add(user)
        db.session.commit()
        
        user.generate_virtual_ids()
        
        # 1. Create secure single-use Admin Approval Request Token
        approval_token = user.create_admin_approval_request()
        
        # 2. Dispatch Admin Notification with [SEND OTP TO USER] button
        send_admin_otp_request_notification(user.email, user.full_name, approval_token, request_obj=request)
        
        Notification.create(
            user.id,
            'Welcome to PocketPay!',
            f'Thank you for joining PocketPay, {full_name.split()[0]}! Your verification request has been submitted for admin approval.',
            'info',
            'high'
        )
        
        return json_response({
            'user': user.to_dict(),
            'email': user.email,
            'requires_verification': True,
            'requires_admin_approval': True,
            'message': f'Account created! An OTP request has been sent for admin approval. Once approved, the 6-digit code will arrive at {user.email}.'
        }, 'Account created successfully. Verification request sent for admin approval.', 201)
        
    except ValueError as ve:
        db.session.rollback()
        return error_response(str(ve), 429)
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to create account: {str(e)}', 500)


@bp.route('/admin-approve-otp', methods=['GET'])
def admin_approve_otp():
    """
    Secure endpoint triggered when Admin clicks [SEND OTP TO USER] in admin email.
    Validates single-use token, generates 6-digit OTP, sends OTP to user's email, and renders confirmation.
    """
    token = request.args.get('token', '').strip()
    if not token:
        return render_template(
            'admin_approval_result.html',
            success=False,
            error_message='Missing approval token. Please use the direct link provided in your admin notification email.'
        ), 400
    
    user = User.query.filter_by(otp_approval_token=token).first()
    if not user:
        return render_template(
            'admin_approval_result.html',
            success=False,
            error_message='Invalid or expired approval token. The request may have already been processed.'
        ), 404
        
    if user.otp_approval_status != 'pending_admin_approval':
        return render_template(
            'admin_approval_result.html',
            success=False,
            error_message='This request has already been approved or processed.'
        ), 400
        
    if user.otp_approval_expires_at and user.otp_approval_expires_at < datetime.utcnow():
        return render_template(
            'admin_approval_result.html',
            success=False,
            error_message='This approval link has expired (valid for 2 hours). Have the user resend a verification request.'
        ), 410
        
    try:
        # Generate 6-digit OTP with 5-minute expiry
        otp = user.generate_otp(for_email=True)
        
        # Dispatch OTP exclusively to user's entered email
        send_otp_email(user.email, otp, user.full_name, 'verification')
        
        # Invalidate single-use approval token & mark approved
        user.otp_approval_token = None
        user.otp_approval_status = 'approved_sent'
        user.otp_approved_at = datetime.utcnow()
        db.session.commit()
        
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        return render_template(
            'admin_approval_result.html',
            success=True,
            user_email=user.email,
            user_name=user.full_name,
            timestamp=now_str
        ), 200
        
    except Exception as e:
        db.session.rollback()
        return render_template(
            'admin_approval_result.html',
            success=False,
            error_message=f'Failed to process approval: {str(e)}'
        ), 500


@bp.route('/verify-registration-otp', methods=['POST'])
def verify_registration_otp():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['email', 'otp'])
    if not valid:
        return error_response(msg, 400)
    
    email = data.get('email', '').strip().lower()
    otp = str(data.get('otp', '')).strip()
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return error_response('Account not found with this email', 404)
    
    success, error = user.verify_otp(otp, for_email=True)
    if not success:
        return error_response(error or 'Invalid or expired OTP', 400)
    
    user.email_verified = True
    user.last_login_at = datetime.utcnow()
    db.session.commit()
    
    login_user(user, remember=True, force=True)
    
    Notification.create(
        user.id,
        'Email Verified!',
        'Your email address has been verified. Welcome aboard!',
        'success',
        'high'
    )
    
    return json_response({
        'user': user.to_dict(),
        'email_verified': True,
        'needs_pin_setup': user.transaction_pin_hash is None
    }, 'Email verified and logged in successfully')


@bp.route('/resend-registration-otp', methods=['POST'])
def resend_registration_otp():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['email'])
    if not valid:
        return error_response(msg, 400)
    
    email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        return error_response('Account not found', 404)
    
    if user.email_verified:
        return error_response('Email is already verified. Please sign in.', 400)
    
    try:
        approval_token = user.create_admin_approval_request()
        send_admin_otp_request_notification(user.email, user.full_name, approval_token, request_obj=request)
        return json_response({
            'sent': True,
            'email': user.email,
            'requires_admin_approval': True
        }, f'Verification request sent to admin for approval.')
    except ValueError as ve:
        return error_response(str(ve), 429)
    except Exception as e:
        return error_response('Failed to send verification request. Please try again.', 500)


@bp.route('/request-verification', methods=['POST'])
def request_email_verification():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['email'])
    if not valid:
        return error_response(msg, 400)
    
    email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        return error_response('No account found with this email address', 404)
    
    if user.email_verified:
        return error_response('This email is already verified. You can sign in directly.', 400)
    
    try:
        approval_token = user.create_admin_approval_request()
        send_admin_otp_request_notification(user.email, user.full_name, approval_token, request_obj=request)
        return json_response({
            'email': user.email,
            'sent': True,
            'requires_admin_approval': True
        }, f'Verification request sent to admin for approval.')
    except ValueError as ve:
        return error_response(str(ve), 429)
    except Exception as e:
        return error_response('Failed to send verification request. Please try again.', 500)


@bp.route('/otp-status', methods=['POST'])
def check_otp_status():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        return error_response('User not found', 404)
    
    has_active_otp = user.email_otp is not None and (user.otp_expires_at is not None and user.otp_expires_at > datetime.utcnow())
    return json_response({
        'email': user.email,
        'email_verified': user.email_verified,
        'approval_status': user.otp_approval_status,
        'has_active_otp': has_active_otp
    })


@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    
    valid, msg = validate_required_fields(data, ['email', 'password'])
    if not valid:
        return error_response(msg, 400)
    
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    remember = data.get('remember', False)
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return error_response('Invalid email or password', 401)
    
    if not user.verify_password(password):
        return error_response('Invalid email or password', 401)
    
    if not user.is_active:
        return error_response('Account is suspended. Please contact support.', 403)
    
    user.last_login_at = datetime.utcnow()
    db.session.commit()
    
    login_user(user, remember=remember, force=True)
    
    return json_response({
        'user': user.to_dict(),
        'needs_pin_setup': user.transaction_pin_hash is None,
        'needs_email_verification': not user.email_verified
    }, 'Login successful')


@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    if current_user.is_authenticated:
        logout_user()
    return json_response(message='Logged out successfully')


@bp.route('/me', methods=['GET'])
@api_login_required
def get_current_user():
    from app.models.transaction import Transaction
    from app.models.pocket import Pocket
    
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.created_at.desc()).limit(5).all()
    active_pockets = Pocket.query.filter_by(user_id=current_user.id, archived=False)\
        .order_by(Pocket.sort_order.asc(), Pocket.created_at.desc()).all()
    
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    
    user_data = current_user.to_dict()
    user_data.update({
        'active_pockets_count': len(active_pockets),
        'transactions_count': Transaction.query.filter_by(user_id=current_user.id).count(),
        'unread_notifications': unread_notifications,
    })
    
    return json_response({
        'user': user_data,
        'recent_transactions': [t.to_dict(True) for t in recent_transactions],
        'pockets': [p.to_dict(True) for p in active_pockets]
    })


@bp.route('/verify-email', methods=['POST'])
@api_login_required
def verify_email():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['otp'])
    if not valid:
        return error_response(msg, 400)
    
    success, error = current_user.verify_otp(data['otp'], for_email=True)
    if success:
        return json_response({'email_verified': True}, 'Email verified successfully')
    return error_response(error or 'Verification failed', 400)


@bp.route('/verify-phone', methods=['POST'])
@api_login_required
def verify_phone():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['otp'])
    if not valid:
        return error_response(msg, 400)
    
    success, error = current_user.verify_otp(data['otp'], for_email=False)
    if success:
        return json_response({'phone_verified': True}, 'Phone verified successfully')
    return error_response(error or 'Verification failed', 400)


@bp.route('/resend-otp', methods=['POST'])
@api_login_required
def resend_otp():
    data = request.get_json() or {}
    otp_type = data.get('type', 'email')
    
    if otp_type == 'email':
        if current_user.email_verified:
            return error_response('Email already verified', 400)
        otp = current_user.generate_otp(for_email=True)
        send_otp_email(current_user.email, otp, current_user.full_name, 'verification')
    else:
        if current_user.phone_verified:
            return error_response('Phone already verified', 400)
        if not current_user.phone:
            return error_response('No phone number on file', 400)
        otp = current_user.generate_otp(for_email=False)
    
    return json_response({
        'sent': True,
        'otp_type': otp_type
    }, f'Verification code sent to your {otp_type}')


@bp.route('/setup-pin', methods=['POST'])
@api_login_required
def setup_pin():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['pin'])
    if not valid:
        return error_response(msg, 400)
    
    pin = str(data.get('pin', ''))
    if not pin.isdigit() or len(pin) != 4:
        return error_response('PIN must be exactly 4 digits', 400)
    
    confirm_pin = str(data.get('confirm_pin', ''))
    if confirm_pin and pin != confirm_pin:
        return error_response('PINs do not match', 400)
    
    current_user.set_transaction_pin(pin)
    db.session.commit()
    
    Notification.create(
        current_user.id,
        'Transaction PIN Set',
        'Your transaction PIN has been set successfully. You can now make payments.',
        'success',
        'normal'
    )
    
    return json_response({'has_pin': True}, 'Transaction PIN set successfully')


@bp.route('/change-pin', methods=['POST'])
@api_login_required
def change_pin():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['old_pin', 'new_pin'])
    if not valid:
        return error_response(msg, 400)
    
    old_pin = str(data.get('old_pin', ''))
    new_pin = str(data.get('new_pin', ''))
    
    if not new_pin.isdigit() or len(new_pin) != 4:
        return error_response('New PIN must be exactly 4 digits', 400)
    
    success, error = current_user.verify_transaction_pin(old_pin)
    if not success:
        return error_response(error or 'Incorrect current PIN', 400)
    
    current_user.set_transaction_pin(new_pin)
    db.session.commit()
    
    Notification.create(
        current_user.id,
        'PIN Changed',
        'Your transaction PIN has been changed successfully.',
        'info',
        'high'
    )
    
    return json_response(message='Transaction PIN changed successfully')


@bp.route('/verify-pin', methods=['POST'])
@api_login_required
def verify_pin():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['pin'])
    if not valid:
        return error_response(msg, 400)
    
    pin = str(data.get('pin', ''))
    success, error = current_user.verify_transaction_pin(pin)
    
    if success:
        return json_response({'verified': True}, 'PIN verified')
    return error_response(error or 'Incorrect PIN', 401,
                          code='INCORRECT_PIN',
                          pin_attempts=current_user.pin_attempts,
                          pin_locked_until=current_user.pin_locked_until.isoformat() if current_user.pin_locked_until else None)


@bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['email'])
    if not valid:
        return error_response(msg, 400)
    
    email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    
    if user:
        otp = user.generate_otp(for_email=True)
        send_otp_email(user.email, otp, user.full_name, 'password reset')
    
    return json_response({
        'email': email
    }, 'If an account exists with this email, a password reset OTP has been sent.')


@bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['email', 'otp', 'new_password'])
    if not valid:
        return error_response(msg, 400)
    
    email = data.get('email', '').strip().lower()
    otp = str(data.get('otp', ''))
    new_password = data.get('new_password', '')
    
    if len(new_password) < 8:
        return error_response('Password must be at least 8 characters', 400)
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return error_response('Invalid request', 400)
    
    success, error = user.verify_otp(otp, for_email=True)
    if not success:
        return error_response(error or 'Invalid or expired OTP', 400)
    
    user.password = new_password
    db.session.commit()
    
    return json_response(message='Password reset successfully')


@bp.route('/update-profile', methods=['PUT'])
@api_login_required
def update_profile():
    data = request.get_json() or {}
    
    allowed_fields = ['full_name', 'avatar_url', 'theme_preference', 'currency_preference', 'language_preference']
    
    changes_made = False
    for field in allowed_fields:
        if field in data and data[field] is not None:
            if field == 'full_name' and len(data[field].strip()) < 2:
                return error_response('Full name must be at least 2 characters', 400)
            setattr(current_user, field, data[field].strip() if isinstance(data[field], str) else data[field])
            changes_made = True
    
    if 'password' in data and data['password']:
        old_password = data.get('old_password', '')
        if not current_user.verify_password(old_password):
            return error_response('Current password is incorrect', 400)
        new_password = str(data['password'])
        if len(new_password) < 8:
            return error_response('New password must be at least 8 characters', 400)
        current_user.password = new_password
        changes_made = True
    
    if 'phone' in data and data['phone']:
        phone = data['phone'].strip()
        if not re.match(r'^[+\d][\d\s\-\(\)]{8,}$', phone):
            return error_response('Invalid phone number format', 400)
        existing = User.query.filter(User.phone == phone, User.id != current_user.id).first()
        if existing:
            return error_response('Phone number already in use', 409)
        current_user.phone = phone
        current_user.phone_verified = False
        changes_made = True
    
    if changes_made:
        current_user.updated_at = datetime.utcnow()
        db.session.commit()
    
    return json_response({'user': current_user.to_dict()}, 'Profile updated successfully')


@bp.route('/wallet-qr', methods=['GET'])
@api_login_required
def get_wallet_qr():
    if not current_user.virtual_wallet_id or not current_user.virtual_upi_id:
        current_user.generate_virtual_ids()
    
    wallet_id = current_user.virtual_wallet_id or 'PPW000000000000'
    upi_id = current_user.virtual_upi_id or f"user{current_user.id}@pocketpay"
    full_name = current_user.full_name or 'PocketPay User'
    
    from app.utils.helpers import build_qr_wallet_url
    scannable_url = build_qr_wallet_url(current_user)
    qr_url = generate_qr_code(scannable_url, 350)
    upi_uri = f'upi://pay?pa={upi_id}&pn={full_name}'
    
    return json_response({
        'qr_code_url': qr_url,
        'wallet_id': wallet_id,
        'upi_id': upi_id,
        'qr_data': scannable_url,
        'scannable_url': scannable_url,
        'upi_uri': upi_uri
    })


@bp.route('/link-bank-account', methods=['POST'])
@api_login_required
def link_bank_account():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['bank_name', 'account_holder', 'account_number'])
    if not valid:
        return error_response(msg, 400)
    
    bank_name = str(data.get('bank_name', '')).strip()
    account_holder = str(data.get('account_holder', '')).strip()
    account_type = str(data.get('account_type', 'Savings Account')).strip()
    acc_num = str(data.get('account_number', '')).strip()
    ifsc = str(data.get('ifsc_code', '')).strip().upper()
    initial_balance = float(data.get('initial_balance', 25000.0) or 25000.0)
    
    clean_acc = re.sub(r'[\s\-]', '', acc_num)
    # Mask account number for safe public display
    masked = '•••• ' + (clean_acc[-4:] if len(clean_acc) >= 4 else clean_acc)
    now_iso = datetime.utcnow().isoformat()
    
    bank_entry = {
        'id': str(uuid.uuid4())[:8],
        'bank_name': bank_name,
        'account_holder': account_holder,
        'account_type': account_type,
        'account_mask': masked,
        'account_number': clean_acc,
        'ifsc_code': ifsc or 'SBIN0001234',
        'balance': initial_balance,
        'status': 'verified',
        'is_sandbox': True,
        'linked_at': now_iso,
        'last_synced_at': now_iso
    }
    
    existing_banks = list(current_user.linked_banks or [])
    existing_banks.append(bank_entry)
    current_user.linked_banks = existing_banks
    
    # Initialize / sync wallet balance with the permitted sandbox bank balance
    current_user.wallet_balance = round((current_user.wallet_balance or 0.0) + initial_balance, 2)
    db.session.commit()
    
    # Record initial bank synchronization transaction
    tx = Transaction(
        transaction_id=Transaction.generate_transaction_id(),
        user_id=current_user.id,
        type='topup',
        amount=initial_balance,
        category='Bank Sync',
        description=f'Initial balance sync from {bank_name} ({masked}) [Sandbox Demo]',
        payment_method='bank_transfer',
        extra_data={'is_sandbox': True, 'bank_id': bank_entry['id']}
    )
    db.session.add(tx)
    tx.complete()
    
    Notification.create(
        current_user.id,
        'Bank Account Connected',
        f'Your {bank_name} account ({masked}) has been safely connected in Sandbox Mode with simulated balance of ₹{initial_balance:,.2f}.',
        'success',
        'medium'
    )
    
    return json_response({
        'bank': bank_entry,
        'linked_banks': current_user.linked_banks,
        'wallet_balance': current_user.wallet_balance,
        'total_balance': current_user.wallet_balance + current_user.total_pocket_balance()
    }, 'Bank account linked successfully (Sandbox Mode)', 201)


@bp.route('/linked-banks', methods=['GET'])
@api_login_required
def get_linked_banks():
    return json_response({
        'linked_banks': current_user.linked_banks or []
    })


@bp.route('/sync-bank-balance', methods=['POST'])
@api_login_required
def sync_bank_balance():
    """
    Simulates contacting the connected sandbox bank provider to retrieve the latest balance and sync time.
    """
    banks = list(current_user.linked_banks or [])
    if not banks:
        return error_response('No connected bank accounts found to synchronize', 400)
    
    now_iso = datetime.utcnow().isoformat()
    for b in banks:
        b['last_synced_at'] = now_iso
        
    current_user.linked_banks = banks
    db.session.commit()
    
    total_pocket_balance = current_user.total_pocket_balance()
    total_balance = current_user.wallet_balance + total_pocket_balance
    
    return json_response({
        'linked_banks': current_user.linked_banks,
        'last_synced_at': now_iso,
        'balances': {
            'wallet': current_user.wallet_balance,
            'pockets': total_pocket_balance,
            'total': total_balance
        }
    }, 'Bank balance synchronized successfully (Sandbox Mode)')


@bp.route('/unlink-bank-account', methods=['POST'])
@api_login_required
def unlink_bank_account():
    data = request.get_json() or {}
    bank_id = data.get('bank_id')
    
    banks = list(current_user.linked_banks or [])
    if not banks:
        return error_response('No connected bank accounts to disconnect', 400)
        
    if bank_id:
        new_banks = [b for b in banks if b.get('id') != bank_id]
    else:
        new_banks = []
        
    current_user.linked_banks = new_banks
    db.session.commit()
    
    Notification.create(
        current_user.id,
        'Bank Account Disconnected',
        'Your bank integration has been disconnected.',
        'info',
        'medium'
    )
    
    return json_response({
        'linked_banks': current_user.linked_banks
    }, 'Bank account disconnected successfully')


@bp.route('/upgrade-premium', methods=['POST'])
@api_login_required
def upgrade_premium():
    """
    Simulated Sandbox Upgrade to PocketPay Premium Tier.
    No real money charged - purely for fintech demo presentation.
    """
    data = request.get_json() or {}
    plan = data.get('plan', 'annual')
    
    current_user.is_premium = True
    db.session.commit()

    Notification.create(
        current_user.id,
        '🎉 PocketPay Premium Activated (Demo)',
        f'Your account has been upgraded to PocketPay Premium ({plan.capitalize()} plan) in sandbox demo mode.',
        'success',
        'high'
    )

    return json_response({
        'user': current_user.to_dict(),
        'is_premium': True,
        'plan': plan,
        'demo_mode': True
    }, 'Congratulations! You are now a PocketPay Premium member (Demo Mode).')


@bp.route('/delete-account', methods=['POST'])
@api_login_required
def delete_account():
    """
    Allows a user to permanently delete/deactivate their account ONLY IF:
    1. PocketPay available balance is ₹0
    2. All pocket balances are ₹0
    3. No pending transactions/operations exist
    4. Valid password confirmation is provided
    """
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['password'])
    if not valid:
        return error_response(msg, 400)
        
    password = data.get('password', '')
    if not current_user.verify_password(password):
        return error_response('Incorrect password. Account deletion cancelled.', 401)
        
    if current_user.totp_enabled:
        totp_code = data.get('totp_code') or data.get('totp') or data.get('code')
        verified, err, err_code = current_user.verify_totp(totp_code)
        if not verified:
            return error_response(err or 'Invalid Authenticator 2FA code', 401, code=err_code or 'INCORRECT_TOTP')
        
    from app.models.pocket import Pocket
    from app.models.transaction import Transaction
    
    # 1. Check wallet balance
    wallet_bal = round(current_user.wallet_balance or 0.0, 2)
    
    # 2. Check all pocket balances
    pockets = Pocket.query.filter_by(user_id=current_user.id, archived=False).all()
    pockets_bal = round(sum(p.current_balance for p in pockets), 2)
    
    # 3. Check total remaining funds
    total_remaining = wallet_bal + pockets_bal
    if total_remaining > 0:
        return error_response(
            f'Your account cannot be deleted because there is still ₹{total_remaining:,.2f} '
            f'(₹{wallet_bal:,.2f} in available balance and ₹{pockets_bal:,.2f} in pockets). '
            'Please withdraw or transfer all funds to ₹0 before deleting your account.',
            400,
            code='ACCOUNT_HAS_BALANCE',
            remaining_balance=total_remaining,
            wallet_balance=wallet_bal,
            pocket_balance=pockets_bal
        )
        
    # 4. Check pending transactions
    pending_txs = Transaction.query.filter_by(user_id=current_user.id, status='pending').count()
    if pending_txs > 0:
        return error_response(
            f'Your account cannot be deleted because you have {pending_txs} pending transaction(s). '
            'Please wait for pending operations to resolve.',
            400,
            code='PENDING_OPERATIONS'
        )
        
    # All checks passed: execute permanent account deletion
    user_email = current_user.email
    user_id = current_user.id
    
    # 1. Unlink any associated Telegram mappings
    from app.models.telegram_user import TelegramUser
    TelegramUser.query.filter_by(user_id=user_id).delete()
    
    # 2. Clean up associated Money Requests
    from app.models.money_request import MoneyRequest
    MoneyRequest.query.filter(
        (MoneyRequest.requester_id == user_id) | (MoneyRequest.target_user_id == user_id)
    ).delete()
    
    # 3. Record in admin audit log
    from app.models.admin_audit_log import AdminAuditLog
    AdminAuditLog.record(
        admin_email=user_email,
        action='user_self_deleted_account',
        target_type='user',
        target_id=str(user_id),
        details={'email': user_email, 'action': 'Account and all associated records permanently purged'}
    )
    
    # 4. Permanently remove user object (cascades pockets, transactions, rules, budgets, notifications)
    user_to_delete = current_user._get_current_object()
    logout_user()
    db.session.delete(user_to_delete)
    db.session.commit()
    
    return json_response({
        'deleted': True,
        'email': user_email
    }, 'Your PocketPay account has been permanently deleted. You can register again with a new account anytime.')


# =============================================================================
# TOTP TWO-FACTOR AUTHENTICATION (2FA) ENDPOINTS
# =============================================================================

@bp.route('/totp/status', methods=['GET'])
@api_login_required
def totp_status():
    """Returns user's current 2FA TOTP status and backup codes count"""
    return json_response({
        'totp_enabled': bool(current_user.totp_enabled),
        'has_backup_codes': len(current_user.totp_backup_codes or []) > 0,
        'backup_codes_count': len(current_user.totp_backup_codes or [])
    })


@bp.route('/totp/setup', methods=['POST'])
@api_login_required
def totp_setup():
    """Initiates TOTP setup, generates secret, QR code, and single-use backup recovery codes"""
    setup_data = current_user.generate_totp_setup()
    return json_response({
        'secret': setup_data['secret'],
        'manual_key': setup_data['manual_key'],
        'qr_code': setup_data['qr_code'],
        'provisioning_uri': setup_data['provisioning_uri'],
        'backup_codes': setup_data['backup_codes']
    }, 'Scan the QR code in Google Authenticator or Microsoft Authenticator to complete setup.')


@bp.route('/totp/verify-setup', methods=['POST'])
@api_login_required
def totp_verify_setup():
    """Verifies the initial 6-digit TOTP code and activates 2FA for the account"""
    data = request.get_json() or {}
    code = re.sub(r'[\x00-\x1f\s\-]', '', str(data.get('code') or '')).strip()
    raw_secret = data.get('secret') or current_user.totp_secret
    secret = re.sub(r'[\x00-\x1f\s]', '', str(raw_secret or '')).strip()
    raw_backup_codes = data.get('backup_codes') or current_user.totp_backup_codes or []
    backup_codes = [re.sub(r'[\x00-\x1f\s]', '', str(c)).upper() for c in raw_backup_codes if c]
    
    if not code:
        return error_response('6-digit verification code from your Authenticator app is required', 400, code='CODE_REQUIRED')
    if not secret:
        return error_response('Setup session expired. Please tap Enable 2FA to generate a fresh QR code.', 400, code='SETUP_EXPIRED')
        
    success, error_msg = current_user.enable_totp(code, secret, backup_codes)
    if not success:
        return error_response(error_msg or 'Verification failed', 400, code='INCORRECT_TOTP')
        
    return json_response({
        'totp_enabled': True,
        'backup_codes': current_user.totp_backup_codes
    }, 'Two-Factor Authentication (2FA) has been enabled successfully!')


@bp.route('/totp/disable', methods=['POST'])
@api_login_required
def totp_disable():
    """Disables Two-Factor Authentication with password verification or current code"""
    data = request.get_json() or {}
    password = re.sub(r'[\x00]', '', str(data.get('password') or '')).strip()
    code = re.sub(r'[\x00-\x1f\s\-]', '', str(data.get('code') or '')).strip()
    
    # Must verify password or code
    authorized = False
    if password and current_user.verify_password(password):
        authorized = True
    elif code:
        verified, err, _ = current_user.verify_totp(code)
        if verified:
            authorized = True
            
    if not authorized:
        return error_response('Invalid password or verification code. Could not disable 2FA.', 401, code='UNAUTHORIZED')
        
    current_user.disable_totp()
    return json_response({
        'totp_enabled': False
    }, 'Two-Factor Authentication (2FA) has been disabled.')


@bp.route('/totp/regenerate-backup-codes', methods=['POST'])
@api_login_required
def totp_regenerate_backup_codes():
    """Re-issues 8 new single-use backup recovery codes after password verification"""
    data = request.get_json() or {}
    password = re.sub(r'[\x00]', '', str(data.get('password') or '')).strip()
    code = re.sub(r'[\x00-\x1f\s\-]', '', str(data.get('code') or '')).strip()
    
    authorized = False
    if password and current_user.verify_password(password):
        authorized = True
    elif code:
        verified, err, _ = current_user.verify_totp(code)
        if verified:
            authorized = True
            
    if not authorized:
        return error_response('Password or Authenticator code is required to regenerate backup codes.', 401, code='UNAUTHORIZED')
        
    new_codes, err = current_user.regenerate_backup_codes()
    if err:
        return error_response(err, 400)
        
    return json_response({
        'backup_codes': new_codes,
        'count': len(new_codes)
    }, 'New backup recovery codes generated. Store them safely!')


