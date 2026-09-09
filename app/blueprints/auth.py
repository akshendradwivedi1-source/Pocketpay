import re
import uuid
import logging
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

logger = logging.getLogger(__name__)

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
    
    # Only block registration if an ACTIVE (non-deleted) account uses this email
    if User.query.filter_by(email=email).filter(User.deleted_at == None).first():
        return error_response('An account with this email already exists', 409)
    
    if phone and User.query.filter_by(phone=phone).filter(User.deleted_at == None).first():
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
        
        # 1. Generate 6-digit verification code and dispatch directly to user's email
        otp = user.generate_otp(for_email=True)
        try:
            send_otp_email(user.email, otp, user.full_name, 'verification')
        except Exception as mail_err:
            current_app.logger.warning(f"Registration OTP email sending error: {mail_err}")

        # 2. Dispatch Admin Notification
        try:
            approval_token = user.create_admin_approval_request()
            send_admin_otp_request_notification(user.email, user.full_name, approval_token, request_obj=request)
        except Exception:
            pass
        
        Notification.create(
            user.id,
            'Welcome to PocketPay!',
            f'Thank you for joining PocketPay, {full_name.split()[0]}! Your verification code has been sent to {user.email}.',
            'info',
            'high'
        )
        
        return json_response({
            'user': user.to_dict(),
            'email': user.email,
            'requires_verification': True,
            'message': f'Account created! A 6-digit verification code has been sent to {user.email}.'
        }, 'Account created successfully. Please enter the verification code sent to your email.', 201)
        
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
        otp = user.generate_otp(for_email=True)
        send_otp_email(user.email, otp, user.full_name, 'verification')
        try:
            approval_token = user.create_admin_approval_request()
            send_admin_otp_request_notification(user.email, user.full_name, approval_token, request_obj=request)
        except Exception:
            pass
        return json_response({
            'sent': True,
            'email': user.email
        }, f'A fresh verification code has been sent to {user.email}.')
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
        otp = user.generate_otp(for_email=True)
        send_otp_email(user.email, otp, user.full_name, 'verification')
        try:
            approval_token = user.create_admin_approval_request()
            send_admin_otp_request_notification(user.email, user.full_name, approval_token, request_obj=request)
        except Exception:
            pass
        return json_response({
            'email': user.email,
            'sent': True
        }, f'A verification code has been sent to {user.email}.')
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
    
    try:
        from app.telegram.service import TelegramService
        TelegramService.send_event_notification(
            user,
            'Security Alert: Account Sign-in',
            f'Your PocketPay account ({user.email}) was just signed in.',
            event_type='login'
        )
    except Exception:
        pass
    
    try:
        from app.models.subscription import LoginEvent
        event = LoginEvent(
            user_id=user.id,
            ip_address=request.remote_addr or '127.0.0.1',
            user_agent=request.user_agent.string[:255] if request.user_agent else 'Browser',
            device_type='Mobile' if 'Mobile' in (request.user_agent.string if request.user_agent else '') else 'Desktop',
            status='SUCCESS'
        )
        db.session.add(event)
        db.session.commit()
    except Exception:
        pass
    
    is_sec_required = user.security_setup_required
    return json_response({
        'user': user.to_dict(),
        'needs_pin_setup': user.transaction_pin_hash is None,
        'needs_email_verification': not user.email_verified,
        'security_setup_required': is_sec_required,
        'security_setup_completed': not is_sec_required,
        'needs_security_onboarding': is_sec_required,
        'onboarding_completed': not is_sec_required
    }, 'Login successful')



@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    if current_user.is_authenticated:
        logout_user()
    return json_response(message='Logged out successfully')


@bp.route('/security-status', methods=['GET'])
@api_login_required
def security_status():
    """Returns current user's security onboarding and 2FA status"""
    return json_response({
        'email_verified': current_user.email_verified,
        'has_pin': bool(current_user.transaction_pin_hash),
        'totp_enabled': bool(current_user.totp_enabled),
        'needs_security_onboarding': current_user.needs_security_onboarding,
        'onboarding_completed': not current_user.needs_security_onboarding,
        'pin_attempts': current_user.pin_attempts,
        'pin_locked_until': current_user.pin_locked_until.isoformat() if current_user.pin_locked_until else None
    })


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
@bp.route('/set-transaction-pin', methods=['POST'])
@api_login_required
def setup_pin():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['pin'])
    if not valid:
        return error_response(msg, 400)
    
    pin = str(data.get('pin', '')).strip()
    if not pin.isdigit() or len(pin) != 4:
        return error_response('PIN must be exactly 4 digits', 400)
    
    confirm_pin = str(data.get('confirm_pin', '')).strip()
    if confirm_pin and pin != confirm_pin:
        return error_response('PINs do not match', 400)
    
    current_user.set_transaction_pin(pin)
    current_user.security_setup_completed = True
    db.session.commit()
    
    Notification.create(
        current_user.id,
        'Transaction PIN Set',
        'Your transaction PIN has been set successfully. You can now make payments.',
        'success',
        'normal'
    )
    
    return json_response({
        'has_pin': True,
        'security_setup_completed': True,
        'user': current_user.to_dict()
    }, 'Transaction PIN set successfully')


@bp.route('/complete-security-setup', methods=['POST'])
@api_login_required
def complete_security_setup():
    """
    Dedicated endpoint for First-Login Security Credential Setup.
    Validates, hashes, and stores transaction PIN, marks setup completed.
    Never exposes raw PIN in response or logs.
    """
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['pin'])
    if not valid:
        return error_response(msg, 400)
        
    pin = str(data.get('pin', '')).strip()
    if not pin.isdigit() or len(pin) != 4:
        return error_response('Security PIN must be exactly 4 numeric digits', 400)
        
    confirm_pin = str(data.get('confirm_pin', '')).strip()
    if confirm_pin and pin != confirm_pin:
        return error_response('PIN confirmation does not match. Please re-enter.', 400)
        
    current_user.set_transaction_pin(pin)
    current_user.security_setup_completed = True
    db.session.commit()
    
    Notification.create(
        current_user.id,
        'Security Credentials Configured 🔒',
        'Your PocketPay transaction credentials have been created successfully. All transfers and banking features are now unlocked.',
        'success',
        'high'
    )
    
    return json_response({
        'security_setup_completed': True,
        'has_transaction_pin': True,
        'user': current_user.to_dict()
    }, 'Security setup completed successfully')


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


@bp.route('/reset-pin', methods=['POST'])
@api_login_required
def reset_pin():
    """Securely resets transaction PIN using verified email OTP"""
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['otp', 'new_pin'])
    if not valid:
        return error_response(msg, 400)

    otp = str(data.get('otp', '')).strip()
    new_pin = str(data.get('new_pin', '')).strip()

    if not new_pin.isdigit() or len(new_pin) != 4:
        return error_response('New PIN must be exactly 4 digits', 400)

    success, error = current_user.verify_otp(otp, for_email=True)
    if not success:
        return error_response(error or 'Invalid or expired OTP', 400)

    current_user.set_transaction_pin(new_pin)
    current_user.pin_attempts = 0
    current_user.pin_locked_until = None
    db.session.commit()

    Notification.create(
        current_user.id,
        'Transaction PIN Reset',
        'Your transaction PIN has been successfully reset.',
        'success',
        'high'
    )

    return json_response({'has_pin': True}, 'Transaction PIN reset successfully')


@bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['email'])
    if not valid:
        return error_response(msg, 400)
    
    email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    
    if user:
        try:
            otp = user.generate_otp(for_email=True)
            send_otp_email(user.email, otp, user.full_name, 'password reset')
        except ValueError as ve:
            return error_response(str(ve), 429)
        except Exception:
            pass
    
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
    # Invalidate OTP explicitly upon successful reset
    user.email_otp = None
    user.otp_expires_at = None
    user.otp_resend_count = 0
    # Invalidate previous sessions
    user.security_version = (user.security_version or 1) + 1
    db.session.commit()
    
    try:
        from app.telegram.service import TelegramService
        TelegramService.send_event_notification(
            user,
            'Security Alert: Password Reset',
            'Your PocketPay account password was successfully reset.',
            event_type='password'
        )
    except Exception:
        pass
    
    return json_response(message='Password reset successfully. You can now sign in with your new password.')


@bp.route('/update-profile', methods=['PUT'])
@api_login_required
def update_profile():
    data = request.get_json() or {}
    
    allowed_fields = ['full_name', 'avatar_url', 'theme_preference', 'currency_preference', 'language_preference']
    
    changes_made = False
    password_changed = False
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
        password_changed = True
    
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
        if password_changed:
            try:
                from app.telegram.service import TelegramService
                TelegramService.send_event_notification(
                    current_user,
                    'Security Alert: Password Updated',
                    'Your PocketPay account password was updated from profile settings.',
                    event_type='password'
                )
            except Exception:
                pass

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
        'qr_code_base64': qr_url,
        'qr_payload': scannable_url,
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
    existing_banks = list(current_user.linked_banks or [])
    
    # Prevent reconnecting the exact same bank account duplicate times without disconnecting first
    for eb in existing_banks:
        if str(eb.get('account_number', '')).strip() == clean_acc and eb.get('status') != 'disconnected':
            return error_response('This bank account is already connected to your PocketPay profile', 400)
    
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
        'imported_balance': initial_balance,
        'status': 'verified',
        'is_sandbox': True,
        'linked_at': now_iso,
        'last_synced_at': now_iso
    }
    
    existing_banks.append(bank_entry)
    current_user.linked_banks = existing_banks
    
    # Initialize / sync wallet balance with the permitted sandbox bank balance
    current_user.wallet_balance = round((current_user.wallet_balance or 0.0) + initial_balance, 2)
    
    # Record initial bank synchronization transaction in ledger
    tx = Transaction(
        transaction_id=Transaction.generate_transaction_id(),
        user_id=current_user.id,
        type='topup',
        amount=initial_balance,
        category='Bank Sync',
        merchant=bank_name,
        description=f'Initial balance sync from {bank_name} ({masked}) [Sandbox Demo]',
        payment_method='bank_transfer',
        status='completed',
        completed_at=datetime.utcnow(),
        extra_data={'is_sandbox': True, 'bank_id': bank_entry['id'], 'action': 'link_bank'}
    )
    db.session.add(tx)
    db.session.commit()
    
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
        'own_wallet_balance': current_user.own_wallet_balance,
        'connected_bank_balance': current_user.connected_bank_balance,
        'total_balance': current_user.wallet_balance + current_user.total_pocket_balance()
    }, 'Bank account linked successfully (Sandbox Mode)', 201)


@bp.route('/linked-banks', methods=['GET'])
@api_login_required
def get_linked_banks():
    return json_response({
        'linked_banks': current_user.linked_banks or [],
        'connected_bank_balance': current_user.connected_bank_balance,
        'own_wallet_balance': current_user.own_wallet_balance,
        'wallet_balance': current_user.wallet_balance
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
    """
    Safely disconnects connected bank account and reconciles imported balance.
    Preserves user's independent PocketPay funds.
    Prevents duplicate disconnect deductions.
    """
    data = request.get_json() or {}
    bank_id = data.get('bank_id')
    
    banks = list(current_user.linked_banks or [])
    if not banks:
        return error_response('No connected bank accounts to disconnect', 400)
        
    if bank_id:
        target_bank = next((b for b in banks if b.get('id') == bank_id), None)
        if not target_bank:
            return error_response('Connected bank account not found or already disconnected', 404)
        banks_to_remove = [target_bank]
        new_banks = [b for b in banks if b.get('id') != bank_id]
    else:
        banks_to_remove = list(banks)
        new_banks = []
        
    # Proper accounting: Deduct only the amount that originated from the connected bank(s)
    # Example: Bank balance = ₹25,000, Total PocketPay balance = ₹25,500
    # After disconnecting: ₹25,500 - ₹25,000 = ₹500
    deduct_amount = round(sum(float(b.get('balance', b.get('imported_balance', 0.0)) or 0.0) for b in banks_to_remove), 2)
    current_wallet = float(current_user.wallet_balance or 0.0)
    
    reconciled_wallet = max(0.0, round(current_wallet - deduct_amount, 2))
    current_user.wallet_balance = reconciled_wallet
    current_user.linked_banks = new_banks
    
    # Financial ledger record for the bank disconnect reconciliation
    if deduct_amount > 0:
        bank_labels = ", ".join(b.get('bank_name', 'Bank') for b in banks_to_remove)
        tx = Transaction(
            transaction_id=Transaction.generate_transaction_id(),
            user_id=current_user.id,
            type='withdraw',
            amount=deduct_amount,
            category='Bank Disconnect',
            merchant=bank_labels,
            description=f'Balance adjustment: disconnected {bank_labels}',
            payment_method='bank_transfer',
            status='completed',
            completed_at=datetime.utcnow(),
            extra_data={'action': 'disconnect_bank', 'removed_bank_ids': [b.get('id') for b in banks_to_remove]}
        )
        db.session.add(tx)
        
    db.session.commit()
    
    Notification.create(
        current_user.id,
        'Bank Account Disconnected',
        f'Your bank integration has been safely disconnected. Reconciled imported balance of ₹{deduct_amount:,.2f}. Your independent PocketPay funds of ₹{reconciled_wallet:,.2f} are preserved.',
        'info',
        'medium'
    )
    
    return json_response({
        'linked_banks': current_user.linked_banks,
        'wallet_balance': current_user.wallet_balance,
        'own_wallet_balance': current_user.own_wallet_balance,
        'total_funds': current_user.wallet_balance + current_user.total_pocket_balance()
    }, 'Bank account disconnected successfully and balance reconciled.')


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
    Permanently soft-deletes the authenticated user's own account.
    Requirements:
    - User can only delete their own account (enforced via current_user)
    - Password confirmation required
    - 2FA verification required if TOTP enabled on account
    - Wallet balance must be ₹0.00 and pocket balances must be ₹0.00
    - No pending transactions allowed
    - Atomic: either succeeds completely or rolls back on database error
    - Financial transaction history is preserved (linked to anonymized user ID)
    - After deletion: session invalidated, email/phone immediately freed for fresh re-registration
    """
    data = request.get_json(silent=True) or {}
    password = str(data.get('password') or '').strip()
    confirm_text = str(data.get('confirm_text') or '').strip().upper()

    if not password:
        return error_response('Your account password is required to confirm deletion', 400, code='PASSWORD_REQUIRED')

    if confirm_text and confirm_text != 'DELETE':
        return error_response('Please type DELETE to confirm permanent account deletion', 400, code='CONFIRM_REQUIRED')

    # Verify password
    if not current_user.verify_password(password):
        return error_response('Incorrect password. Account deletion cancelled.', 401, code='WRONG_PASSWORD')

    # Mandatory 2FA TOTP check if enabled
    if current_user.totp_enabled:
        totp_code = str(data.get('totp_code') or data.get('totp') or data.get('code') or '').strip()
        if not totp_code:
            return error_response('Google Authenticator 6-digit 2FA code is required to confirm deletion', 400, code='TOTP_REQUIRED')
        verified, err, err_code = current_user.verify_totp(totp_code)
        if not verified:
            return error_response(err or 'Invalid Authenticator 2FA code', 401, code=err_code or 'INCORRECT_TOTP')

    # Enforce zero balance before deletion
    wallet_balance = round(float(current_user.wallet_balance or 0.0), 2)
    pocket_balance = round(sum(
        p.current_balance for p in current_user.pockets.filter_by(archived=False).all()
    ), 2)

    if wallet_balance > 0:
        return error_response(
            f'Your wallet balance is ₹{wallet_balance:,.2f}. Please withdraw or transfer all funds before deleting your account.',
            400, code='BALANCE_NOT_ZERO'
        )
    if pocket_balance > 0:
        return error_response(
            f'Your pockets contain ₹{pocket_balance:,.2f}. Please empty all pockets before deleting your account.',
            400, code='POCKET_BALANCE_NOT_ZERO'
        )

    # Check for pending transactions
    from app.models.transaction import Transaction
    pending_tx = Transaction.query.filter_by(user_id=current_user.id, status='pending').first()
    if pending_tx:
        return error_response(
            f'You have a pending transaction ({pending_tx.transaction_id}). Please wait for it to complete or resolve before deleting your account.',
            400, code='PENDING_TRANSACTIONS'
        )

    # Admins cannot self-delete via this endpoint (safety measure)
    if current_user.is_admin:
        return error_response(
            'Admin accounts cannot be self-deleted. Please contact the system administrator.',
            403, code='ADMIN_CANNOT_DELETE'
        )

    try:
        user_id = current_user.id
        user_name = current_user.full_name

        # 1. Archive all pockets
        from app.models.pocket import Pocket
        Pocket.query.filter_by(user_id=user_id).update({'archived': True})

        # 2. Disconnect any linked Telegram account
        from app.models.telegram_user import TelegramUser
        TelegramUser.query.filter_by(user_id=user_id).delete()

        # 3. Clean up money requests
        from app.models.money_request import MoneyRequest
        MoneyRequest.query.filter(
            (MoneyRequest.requester_id == user_id) | (MoneyRequest.target_user_id == user_id)
        ).delete()

        # 4. Clean up goals, budgets, distribution rules, notifications
        from app.models.goal import SavingsGoal
        from app.models.budget import Budget
        from app.models.distribution_rule import DistributionRule
        from app.models.notification import Notification

        SavingsGoal.query.filter_by(user_id=user_id).delete()
        Budget.query.filter_by(user_id=user_id).delete()
        DistributionRule.query.filter_by(user_id=user_id).delete()
        Notification.query.filter_by(user_id=user_id).delete()

        # 5. Anonymize user record & free up email/phone for re-registration
        current_user.soft_delete()

        db.session.commit()

        # 6. Invalidate Flask-Login session
        logout_user()

        return json_response({
            'deleted': True,
            'message': 'Your PocketPay account has been permanently deleted. You may register again with the same email address.'
        }, f'Account for {user_name} has been permanently deleted.')

    except Exception as e:
        db.session.rollback()
        logger.error(f"[Delete Account Error] user_id={getattr(current_user, 'id', None)}: {str(e)}")
        return error_response(
            f'Account deletion failed due to a database error: {str(e)}. No changes were made.',
            500, code='DELETION_FAILED'
        )


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


# =============================================================================
# TELEGRAM ACCOUNT LINKING ENDPOINTS
# =============================================================================

@bp.route('/telegram/generate-link-token', methods=['POST'])
@api_login_required
def generate_telegram_link_token():
    """Generates a secure single-use linking code (valid for 15 mins) for Telegram Bot connection"""
    token = current_user.generate_telegram_link_token()
    from app.telegram.service import TelegramService
    bot_info = TelegramService.get_me()
    bot_username = bot_info.get('result', {}).get('username') if bot_info.get('ok') else 'PocketPayBot'
    direct_link = f"https://t.me/{bot_username}?start=link_{token}"
    
    return json_response({
        'token': token,
        'bot_username': bot_username,
        'direct_link': direct_link,
        'expires_in_seconds': 900
    }, 'Single-use linking code generated. Code is valid for 15 minutes.')


@bp.route('/telegram/status', methods=['GET'])
@api_login_required
def get_telegram_link_status():
    """Returns the current user's Telegram connection status and preferences"""
    linked_tg = current_user.get_linked_telegram_user()
    return json_response({
        'linked': linked_tg is not None,
        'telegram_id': linked_tg.telegram_id if linked_tg else None,
        'telegram_username': linked_tg.username if linked_tg else None,
        'first_name': linked_tg.first_name if linked_tg else None,
        'notifications_enabled': bool(current_user.telegram_notifications_enabled)
    })


@bp.route('/telegram/toggle-notifications', methods=['POST'])
@api_login_required
def toggle_telegram_notifications():
    """Toggles Telegram notifications preference on or off"""
    current_user.telegram_notifications_enabled = not bool(current_user.telegram_notifications_enabled)
    linked_tg = current_user.get_linked_telegram_user()
    if linked_tg:
        linked_tg.notifications_enabled = current_user.telegram_notifications_enabled
    db.session.commit()
    return json_response({
        'notifications_enabled': bool(current_user.telegram_notifications_enabled)
    }, f"Telegram notifications {'enabled' if current_user.telegram_notifications_enabled else 'disabled'}")


@bp.route('/telegram/disconnect', methods=['POST'])
@api_login_required
def disconnect_telegram():
    """Disconnects and unlinks the connected Telegram account"""
    from app.models.telegram_user import TelegramUser
    TelegramUser.query.filter_by(user_id=current_user.id).delete()
    current_user.telegram_linking_token = None
    current_user.telegram_linking_token_expires_at = None
    db.session.commit()
    return json_response({'disconnected': True}, 'Telegram account disconnected successfully')


@bp.route('/set-upi-id', methods=['POST'])
@api_login_required
def set_upi_id():
    """Sets/updates custom Virtual UPI ID for the user, verifying with Google Authenticator TOTP if enabled"""
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['upi_id'])
    if not valid:
        return error_response(msg, 400)
    
    raw_upi = str(data.get('upi_id', '')).strip().lower()
    if not raw_upi:
        return error_response('UPI ID cannot be empty', 400)
    
    # Auto-append @pocketpay if user enters only username handle
    if '@' not in raw_upi:
        raw_upi = f"{raw_upi}@pocketpay"
        
    # Format validation: handle@bank
    if not re.match(r'^[a-zA-Z0-9.\-_]{2,30}@[a-zA-Z0-9]{2,20}$', raw_upi):
        return error_response('Invalid UPI ID format. Example: yourname@pocketpay or user@okhdfcbank', 400, code='INVALID_UPI_FORMAT')
        
    # Check uniqueness
    existing = User.query.filter(User.virtual_upi_id == raw_upi, User.id != current_user.id).first()
    if existing:
        return error_response('This UPI ID is already claimed by another user', 409, code='UPI_ID_TAKEN')
        
    # Google Authenticator 2FA TOTP verification
    if current_user.totp_enabled:
        totp_code = data.get('totp_code') or data.get('totp') or data.get('otp')
        if not totp_code:
            return error_response('Google Authenticator 6-digit 2FA code is required to update your UPI ID', 400, code='TOTP_REQUIRED')
        verified, err, err_code = current_user.verify_totp(totp_code)
        if not verified:
            return error_response(err or 'Invalid Google Authenticator 2FA code', 401, code=err_code or 'INCORRECT_TOTP')
            
    current_user.virtual_upi_id = raw_upi
    current_user.updated_at = datetime.utcnow()
    db.session.commit()
    
    return json_response({
        'virtual_upi_id': current_user.virtual_upi_id,
        'user': current_user.to_dict()
    }, 'Virtual UPI ID updated successfully!')


@bp.route('/send-phone-otp', methods=['POST'])
@api_login_required
def send_phone_otp():
    """Generates and sends a 6-digit phone verification OTP"""
    data = request.get_json() or {}
    phone = data.get('phone')
    if phone:
        clean_phone = str(phone).strip()
        if len(re.sub(r'[\s\-+]', '', clean_phone)) < 10:
            return error_response('Please enter a valid phone number (at least 10 digits)', 400)
        current_user.phone = clean_phone
        current_user.phone_verified = False
        db.session.commit()
        
    if not current_user.phone:
        return error_response('No phone number specified', 400)
        
    otp = current_user.generate_otp(for_email=False)
    
    return json_response({
        'sent': True,
        'phone': current_user.phone,
        'simulated_otp': otp
    }, f'6-digit verification code sent to {current_user.phone}')


# =============================================================================
# PART 23: PREMIUM SECURITY CENTRE
# =============================================================================

@bp.route('/security/centre', methods=['GET'])
@api_login_required
def get_security_centre():
    """Returns user's security center data: sessions, login history, limits, freeze state"""
    from app.models.subscription import LoginEvent
    events = LoginEvent.query.filter_by(user_id=current_user.id).order_by(LoginEvent.created_at.desc()).limit(20).all()
    return json_response({
        'transfer_frozen': bool(getattr(current_user, 'transfer_frozen', False)),
        'transaction_limit': float(getattr(current_user, 'transaction_limit', 100000.0)),
        'totp_enabled': bool(current_user.totp_enabled),
        'has_transaction_pin': bool(current_user.transaction_pin_hash),
        'login_events': [e.to_dict() for e in events],
        'active_session': {
            'ip': request.remote_addr or '127.0.0.1',
            'device': 'Current Browser',
            'status': 'Active'
        }
    })


@bp.route('/security/toggle-freeze', methods=['POST'])
@api_login_required
def toggle_transfer_freeze():
    """Emergency transfer freeze / unfreeze toggle"""
    data = request.get_json() or {}
    pin = str(data.get('pin', '')).strip()

    if current_user.transaction_pin_hash:
        if not pin:
            return error_response('Security PIN is required to change transfer freeze status', 400, code='PIN_REQUIRED')
        success, err = current_user.verify_transaction_pin(pin)
        if not success:
            return error_response(err or 'Incorrect PIN', 401, code='INCORRECT_PIN')

    current_user.transfer_frozen = not getattr(current_user, 'transfer_frozen', False)
    db.session.commit()

    action_str = "frozen" if current_user.transfer_frozen else "unfrozen"
    return json_response({
        'transfer_frozen': current_user.transfer_frozen
    }, f"Transfers on your account have been {action_str}.")


@bp.route('/security/set-limit', methods=['POST'])
@api_login_required
def set_transaction_limit():
    """Sets user's custom daily transaction limit"""
    data = request.get_json() or {}
    try:
        limit = round(float(data.get('limit', 100000.0)), 2)
    except (ValueError, TypeError):
        return error_response('Invalid limit amount', 400)

    if limit <= 0:
        return error_response('Transaction limit must be greater than zero', 400)

    current_user.transaction_limit = limit
    db.session.commit()
    return json_response({
        'transaction_limit': current_user.transaction_limit
    }, f"Daily transaction limit updated to ₹{limit:,.2f}.")






