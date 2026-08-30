from datetime import datetime
from app.extensions import db


class SupportTicket(db.Model):
    """
    PocketPay Customer Support Ticket Model.
    Tracks user complaints, inquiries, transaction disputes, and admin resolutions.
    """
    __tablename__ = 'support_tickets'

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    category = db.Column(db.String(64), nullable=False, default='General Inquiry')
    subject = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    transaction_id = db.Column(db.String(64), nullable=True, index=True)
    
    status = db.Column(db.String(32), default='OPEN', nullable=False, index=True)
    # Statuses: OPEN, IN_PROGRESS, WAITING_FOR_USER, RESOLVED, CLOSED
    
    admin_notes = db.Column(db.Text, nullable=True)
    admin_response = db.Column(db.Text, nullable=True)
    resolved_by = db.Column(db.String(255), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('support_tickets', lazy='dynamic', cascade='all'))

    @classmethod
    def generate_ticket_number(cls):
        """Generates sequential ticket number e.g. PP-2026-000001"""
        year = datetime.utcnow().year
        count = cls.query.count() + 1
        return f"PP-{year}-{count:06d}"

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_number': self.ticket_number,
            'user_id': self.user_id,
            'name': self.name,
            'email': self.email,
            'category': self.category,
            'subject': self.subject,
            'description': self.description,
            'transaction_id': self.transaction_id,
            'status': self.status,
            'admin_notes': self.admin_notes,
            'admin_response': self.admin_response,
            'resolved_by': self.resolved_by,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
