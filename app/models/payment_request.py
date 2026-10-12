import uuid
import random
import string
from datetime import datetime, timedelta
from app.extensions import db


class PaymentRequest(db.Model):
    __tablename__ = 'payment_requests'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    merchant = db.Column(db.String(100), nullable=False, default='TravelEase')
    booking_id = db.Column(db.String(100), nullable=False, index=True)
    booking_type = db.Column(db.String(50), nullable=True, default='booking')
    reference = db.Column(db.String(100), nullable=True, index=True)
    version = db.Column(db.String(20), default='1', nullable=True)
    
    amount = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False)
    currency = db.Column(db.String(10), default='INR')
    description = db.Column(db.String(255), nullable=True)
    
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    # Status values: 'pending', 'paid', 'expired', 'cancelled'
    
    transaction_id = db.Column(db.String(50), nullable=True, index=True)
    payer_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    token_signature = db.Column(db.String(128), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    extra_data = db.Column(db.JSON, default=dict)

    payer = db.relationship('User', foreign_keys=[payer_user_id], backref=db.backref('merchant_payments', lazy='dynamic'))

    @staticmethod
    def generate_request_id():
        ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f'PPR{ts}{rand}'

    def is_expired(self):
        if self.status == 'pending' and self.expires_at and self.expires_at < datetime.utcnow():
            self.status = 'expired'
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            return True
        return self.status == 'expired'

    def to_dict(self):
        self.is_expired()
        return {
            'id': self.id,
            'request_id': self.request_id,
            'merchant': self.merchant,
            'booking_id': self.booking_id,
            'booking_type': self.booking_type or 'flight',
            'reference': self.reference or self.booking_id,
            'version': self.version or '1',
            'amount': round(float(self.amount or 0.0), 2),
            'currency': self.currency,
            'description': self.description,
            'status': self.status,
            'transaction_id': self.transaction_id,
            'payer_user_id': self.payer_user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'extra_data': self.extra_data or {},
        }
