import uuid
from datetime import datetime
from app.extensions import db


class MoneyRequest(db.Model):
    __tablename__ = 'money_requests'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    note = db.Column(db.String(255), nullable=True)
    
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    # Statuses: 'pending', 'paid', 'declined', 'cancelled'
    
    transaction_id = db.Column(db.String(50), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)

    requester = db.relationship('User', foreign_keys=[requester_id], backref=db.backref('outgoing_money_requests', lazy='dynamic'))
    target_user = db.relationship('User', foreign_keys=[target_user_id], backref=db.backref('incoming_money_requests', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'uuid': self.uuid,
            'requester_id': self.requester_id,
            'requester_name': self.requester.full_name if self.requester else 'Unknown User',
            'requester_email': self.requester.email if self.requester else '',
            'requester_upi': self.requester.virtual_upi_id if self.requester else '',
            'target_user_id': self.target_user_id,
            'target_user_name': self.target_user.full_name if self.target_user else 'Unknown User',
            'target_user_email': self.target_user.email if self.target_user else '',
            'target_user_upi': self.target_user.virtual_upi_id if self.target_user else '',
            'amount': self.amount,
            'currency': self.currency,
            'note': self.note,
            'status': self.status,
            'transaction_id': self.transaction_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
        }
