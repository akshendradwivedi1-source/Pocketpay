import uuid
from datetime import datetime
from app.extensions import db


TRANSACTION_TYPES = (
    ('income', 'Income'),
    ('expense', 'Expense'),
    ('transfer', 'Transfer'),
    ('topup', 'Top-up'),
    ('withdraw', 'Withdraw'),
    ('refund', 'Refund'),
    ('peer_send', 'Sent Money'),
    ('peer_receive', 'Received Money'),
)

TRANSACTION_STATUS = (
    ('pending', 'Pending'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
    ('cancelled', 'Cancelled'),
)

EXPENSE_CATEGORIES = [
    'Food & Dining', 'Shopping', 'Transportation', 'Entertainment',
    'Bills & Utilities', 'Healthcare', 'Education', 'Travel',
    'Groceries', 'Rent', 'Insurance', 'Investments',
    'Subscriptions', 'Gifts & Donations', 'Sports & Fitness',
    'Business', 'Gaming', 'Pets', 'Beauty & Personal Care',
    'Home & Garden', 'Technology', 'Custom'
]

INCOME_CATEGORIES = [
    'Salary', 'Freelance', 'Bonus', 'Rental Income',
    'Investment Returns', 'Dividends', 'Interest', 'Gifts Received',
    'Refunds', 'Cashback', 'Tax Refund', 'Other Income'
]


class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    transaction_id = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    type = db.Column(db.String(20), nullable=False, default='expense')
    status = db.Column(db.String(20), nullable=False, default='completed')
    
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    
    from_pocket_id = db.Column(db.Integer, db.ForeignKey('pockets.id'), nullable=True, index=True)
    to_pocket_id = db.Column(db.Integer, db.ForeignKey('pockets.id'), nullable=True, index=True)
    
    category = db.Column(db.String(100), nullable=True)
    merchant = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    
    payment_method = db.Column(db.String(50), default='wallet')
    qr_code_url = db.Column(db.String(500), nullable=True)
    upi_reference = db.Column(db.String(100), nullable=True)
    
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    location_name = db.Column(db.String(255), nullable=True)
    
    tags = db.Column(db.JSON, default=list)
    extra_data = db.Column(db.JSON, default=dict)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    user = db.relationship('User', back_populates='transactions')
    from_pocket = db.relationship('Pocket', foreign_keys=[from_pocket_id], back_populates='transactions_from')
    to_pocket = db.relationship('Pocket', foreign_keys=[to_pocket_id], back_populates='transactions_to')
    
    __table_args__ = (
        db.Index('ix_user_transactions', 'user_id', 'created_at'),
        db.Index('ix_pocket_transactions_from', 'from_pocket_id', 'created_at'),
        db.Index('ix_pocket_transactions_to', 'to_pocket_id', 'created_at'),
    )
    
    @staticmethod
    def generate_transaction_id():
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        import random
        import string
        rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f'PPT{timestamp}{rand}'
    
    def complete(self):
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        db.session.commit()
    
    def fail(self, reason=None):
        self.status = 'failed'
        if reason:
            meta = self.extra_data or {}
            meta['fail_reason'] = reason
            self.extra_data = meta
        db.session.commit()
    
    def cancel(self):
        self.status = 'cancelled'
        db.session.commit()
    
    def to_dict(self, include_pocket_details=False):
        data = {
            'id': self.id,
            'uuid': self.uuid,
            'transaction_id': self.transaction_id,
            'user_id': self.user_id,
            'type': self.type,
            'status': self.status,
            'amount': self.amount,
            'currency': self.currency,
            'from_pocket_id': self.from_pocket_id,
            'to_pocket_id': self.to_pocket_id,
            'category': self.category,
            'merchant': self.merchant,
            'description': self.description,
            'payment_method': self.payment_method,
            'qr_code_url': self.qr_code_url,
            'upi_reference': self.upi_reference,
            'location_name': self.location_name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'tags': self.tags or [],
            'extra_data': self.extra_data or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
        if include_pocket_details:
            if self.from_pocket:
                data['from_pocket'] = {
                    'id': self.from_pocket.id,
                    'name': self.from_pocket.name,
                    'color': self.from_pocket.color,
                    'icon': self.from_pocket.icon,
                }
            if self.to_pocket:
                data['to_pocket'] = {
                    'id': self.to_pocket.id,
                    'name': self.to_pocket.name,
                    'color': self.to_pocket.color,
                    'icon': self.to_pocket.icon,
                }
        return data
