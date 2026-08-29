import os
import re
import uuid
import random
import string
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    full_name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar_url = db.Column(db.String(500), nullable=True)
    
    transaction_pin_hash = db.Column(db.String(255), nullable=True)
    pin_attempts = db.Column(db.Integer, default=0)
    pin_locked_until = db.Column(db.DateTime, nullable=True)
    
    wallet_balance = db.Column(db.Float, default=0.0)
    virtual_wallet_id = db.Column(db.String(20), unique=True, nullable=True)
    virtual_upi_id = db.Column(db.String(50), unique=True, nullable=True)
    
    email_verified = db.Column(db.Boolean, default=False)
    phone_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    is_premium = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    theme_preference = db.Column(db.String(10), default='dark')
    currency_preference = db.Column(db.String(10), default='INR')
    language_preference = db.Column(db.String(10), default='en')
    
    email_otp = db.Column(db.String(6), nullable=True)
    phone_otp = db.Column(db.String(6), nullable=True)
    otp_expires_at = db.Column(db.DateTime, nullable=True)
    otp_resend_count = db.Column(db.Integer, default=0)
    otp_last_sent_at = db.Column(db.DateTime, nullable=True)
    
    otp_approval_token = db.Column(db.String(128), nullable=True, index=True)
    otp_approval_status = db.Column(db.String(32), default='none')
    otp_approval_expires_at = db.Column(db.DateTime, nullable=True)
    otp_approved_at = db.Column(db.DateTime, nullable=True)
    
    linked_banks = db.Column(db.JSON, default=list)
    
    totp_secret = db.Column(db.String(64), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False)
    totp_backup_codes = db.Column(db.JSON, default=list)
    totp_last_verified_counter = db.Column(db.Integer, nullable=True)
    
    telegram_linking_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    telegram_linking_token_expires_at = db.Column(db.DateTime, nullable=True)
    telegram_notifications_enabled = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    
    pockets = db.relationship('Pocket', back_populates='user', cascade='all, delete-orphan', lazy='dynamic')
    transactions = db.relationship('Transaction', back_populates='user', cascade='all, delete-orphan', lazy='dynamic')
    distribution_rules = db.relationship('DistributionRule', back_populates='user', cascade='all, delete-orphan', lazy='dynamic')
    notifications = db.relationship('Notification', back_populates='user', cascade='all, delete-orphan', lazy='dynamic')
    budgets = db.relationship('Budget', back_populates='user', cascade='all, delete-orphan', lazy='dynamic')
    
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def set_password(self, password):
        self.password = password

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def set_transaction_pin(self, pin):
        self.transaction_pin_hash = generate_password_hash(pin)

    
    def verify_transaction_pin(self, pin):
        if self.pin_locked_until and self.pin_locked_until > datetime.utcnow():
            return False, 'PIN locked. Try again later.'
        if check_password_hash(self.transaction_pin_hash or '', pin):
            self.pin_attempts = 0
            self.pin_locked_until = None
            db.session.commit()
            return True, None
        else:
            self.pin_attempts += 1
            from flask import current_app
            attempts_limit = current_app.config.get('PIN_ATTEMPTS_LIMIT', 5) if current_app else 5
            lockout_min = current_app.config.get('PIN_LOCKOUT_MINUTES', 15) if current_app else 15
            if self.pin_attempts >= attempts_limit:
                self.pin_locked_until = datetime.utcnow() + timedelta(minutes=lockout_min)
                self.pin_attempts = 0
            db.session.commit()
            return False, 'Incorrect PIN'
    
    def create_admin_approval_request(self):
        import secrets
        now = datetime.utcnow()
        token = secrets.token_urlsafe(32)
        self.otp_approval_token = token
        self.otp_approval_status = 'pending_admin_approval'
        self.otp_approval_expires_at = now + timedelta(hours=2)
        db.session.commit()
        return token

    def generate_otp(self, for_email=True):
        now = datetime.utcnow()
        # Safe rate-limiting check: max 5 resends within 15 minutes, minimum 15 seconds cooldown
        if self.otp_last_sent_at and (now - self.otp_last_sent_at).total_seconds() < 15:
            raise ValueError('Please wait a moment before requesting another code')
            
        if self.otp_last_sent_at and (now - self.otp_last_sent_at).total_seconds() > 900:
            self.otp_resend_count = 0
            
        if self.otp_resend_count and self.otp_resend_count >= 5:
            raise ValueError('Maximum OTP verification attempts reached. Please try again in 15 minutes.')
            
        otp = ''.join(random.choices(string.digits, k=6))
        from flask import current_app
        expiry_min = current_app.config.get('OTP_EXPIRY_MINUTES', 5) if current_app else 5
        self.otp_expires_at = now + timedelta(minutes=expiry_min)
        self.otp_last_sent_at = now
        self.otp_resend_count = (self.otp_resend_count or 0) + 1
        
        if for_email:
            self.email_otp = otp
        else:
            self.phone_otp = otp
        db.session.commit()
        return otp
    
    def verify_otp(self, otp, for_email=True):
        if self.otp_expires_at and self.otp_expires_at < datetime.utcnow():
            return False, 'OTP expired. Please request a new verification code.'
        stored = self.email_otp if for_email else self.phone_otp
        if stored and stored == otp:
            if for_email:
                self.email_verified = True
                self.email_otp = None
                self.otp_approval_token = None
                self.otp_approval_status = 'verified'
            else:
                self.phone_verified = True
                self.phone_otp = None
            self.otp_expires_at = None
            self.otp_resend_count = 0
            db.session.commit()
            return True, None
        return False, 'Invalid verification code. Please check and try again.'
    
    def generate_virtual_ids(self):
        if not self.virtual_wallet_id:
            self.virtual_wallet_id = 'PPW' + ''.join(random.choices(string.digits, k=12))
        if not self.virtual_upi_id:
            username = self.email.split('@')[0].lower().replace('.', '')
            self.virtual_upi_id = f"{username}@pocketpay"
        db.session.commit()
    
    def generate_totp_setup(self):
        import pyotp
        import qrcode
        import io
        import base64
        import secrets
        
        secret = str(pyotp.random_base32()).replace('\x00', '').strip()
        totp = pyotp.TOTP(secret)
        
        provisioning_uri = totp.provisioning_uri(name=str(self.email or 'user@pocketpay.app'), issuer_name='PocketPay')
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0a0b14", back_color="#ffffff")
        
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"
        
        backup_codes = [
            f"{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper()
            for _ in range(8)
        ]
        
        manual_key = ' '.join([secret[i:i+4] for i in range(0, len(secret), 4)])
        
        # Persist candidate secret on user record (totp_enabled stays False until verified)
        self.totp_secret = secret
        self.totp_backup_codes = list(backup_codes)
        db.session.commit()
        
        return {
            'secret': secret,
            'manual_key': manual_key,
            'provisioning_uri': provisioning_uri,
            'qr_code': qr_base64,
            'backup_codes': backup_codes
        }

    def enable_totp(self, code, candidate_secret=None, backup_codes=None):
        import pyotp
        raw_secret = candidate_secret or self.totp_secret
        if not raw_secret or not code:
            return False, 'Secret and verification code are required'
            
        active_secret = re.sub(r'[\x00-\x1f\s]', '', str(raw_secret)).strip()
        clean_code = re.sub(r'[\x00-\x1f\s\-]', '', str(code)).strip()
        
        totp = pyotp.TOTP(active_secret)
        # valid_window=3 provides +/- 90 seconds tolerance for mobile phone clock drift
        if not totp.verify(clean_code, valid_window=3):
            return False, 'Invalid 6-digit code. Please verify the code in Google Authenticator or Microsoft Authenticator and ensure your device time is accurate.'
            
        clean_backup_codes = [
            re.sub(r'[\x00-\x1f\s]', '', str(c)).upper()
            for c in (backup_codes or self.totp_backup_codes or [])
            if c
        ]
        if not clean_backup_codes:
            import secrets
            clean_backup_codes = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper() for _ in range(8)]
            
        self.totp_secret = active_secret
        self.totp_enabled = True
        self.totp_backup_codes = list(clean_backup_codes)
        db.session.commit()
        return True, None

    def disable_totp(self):
        self.totp_secret = None
        self.totp_enabled = False
        self.totp_backup_codes = []
        self.totp_last_verified_counter = None
        db.session.commit()
        return True, None

    def regenerate_backup_codes(self):
        import secrets
        if not self.totp_enabled:
            return None, 'Two-factor authentication is not enabled'
        new_codes = [
            f"{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper()
            for _ in range(8)
        ]
        self.totp_backup_codes = list(new_codes)
        db.session.commit()
        return new_codes, None

    def verify_totp(self, code):
        """
        Verifies 6-digit TOTP code or single-use backup recovery code.
        If user has not enabled TOTP, passes automatically.
        """
        if not self.totp_enabled or not self.totp_secret:
            return True, None, None
            
        if not code:
            return False, 'Authenticator 6-digit verification code is required', 'TOTP_REQUIRED'
            
        raw_code = str(code).strip().upper()
        clean_code = ''.join(raw_code.split()).replace('-', '')
        
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        
        # Check standard 6-digit TOTP code with drift tolerance
        if clean_code.isdigit() and len(clean_code) == 6:
            if totp.verify(clean_code, valid_window=3):
                return True, None, None
            return False, 'Invalid Authenticator code. Check the 6-digit code in your app.', 'INCORRECT_TOTP'
            
        # Check single-use backup recovery code
        current_backups = list(self.totp_backup_codes or [])
        matched_backup = None
        for b_code in current_backups:
            clean_b = ''.join(str(b_code).split()).replace('-', '').upper()
            if clean_b == clean_code or str(b_code).upper() == raw_code:
                matched_backup = b_code
                break
                
        if matched_backup:
            current_backups.remove(matched_backup)
            self.totp_backup_codes = current_backups
            db.session.commit()
            return True, None, None
            
        return False, 'Invalid Authenticator code or recovery backup code.', 'INCORRECT_TOTP'

    def generate_telegram_link_token(self):
        import secrets
        now = datetime.utcnow()
        # Generate clean 8-character uppercase linking code e.g. PKP-8A3F or 6-digit
        code = 'PKP' + ''.join(random.choices(string.digits + string.ascii_uppercase, k=6))
        self.telegram_linking_token = code
        self.telegram_linking_token_expires_at = now + timedelta(minutes=15)
        db.session.commit()
        return code

    def get_linked_telegram_user(self):
        from app.models.telegram_user import TelegramUser
        return TelegramUser.query.filter_by(user_id=self.id).first()

    def total_pocket_balance(self):
        return sum(p.current_balance for p in self.pockets.filter_by(archived=False).all())

    def to_dict(self, include_sensitive=False):
        linked_tg = self.get_linked_telegram_user()
        data = {
            'id': self.id,
            'uuid': self.uuid,
            'email': self.email,
            'phone': self.phone,
            'full_name': self.full_name,
            'avatar_url': self.avatar_url,
            'wallet_balance': self.wallet_balance,
            'virtual_wallet_id': self.virtual_wallet_id,
            'virtual_upi_id': self.virtual_upi_id,
            'email_verified': self.email_verified,
            'phone_verified': self.phone_verified,
            'is_premium': self.is_premium,
            'is_admin': bool(self.is_admin),
            'has_transaction_pin': self.transaction_pin_hash is not None,
            'totp_enabled': bool(self.totp_enabled),
            'has_backup_codes': len(self.totp_backup_codes or []) > 0,
            'backup_codes_count': len(self.totp_backup_codes or []),
            'telegram_linked': linked_tg is not None,
            'telegram_username': linked_tg.username if linked_tg else None,
            'telegram_id': linked_tg.telegram_id if linked_tg else None,
            'telegram_notifications_enabled': bool(self.telegram_notifications_enabled),
            'theme_preference': self.theme_preference,
            'currency_preference': self.currency_preference,
            'linked_banks': self.linked_banks or [],
            'total_pocket_balance': self.total_pocket_balance(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_sensitive:
            data['pin_attempts'] = self.pin_attempts
            data['pin_locked_until'] = self.pin_locked_until.isoformat() if self.pin_locked_until else None
        return data

