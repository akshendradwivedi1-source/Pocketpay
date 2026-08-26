from datetime import datetime
from app.extensions import db


class AdminAuditLog(db.Model):
    """
    Immutable audit log recording every administrative action on PocketPay.
    Tracks who performed the action, what was modified, IP, and timestamp.
    """
    __tablename__ = 'admin_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    admin_email = db.Column(db.String(255), nullable=False, index=True)
    action = db.Column(db.String(64), nullable=False, index=True)
    target_type = db.Column(db.String(64), nullable=True)
    target_id = db.Column(db.String(64), nullable=True)
    details = db.Column(db.JSON, default=dict, nullable=False)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    @classmethod
    def record(cls, admin_email: str, action: str, target_type: str = None, target_id: str = None, details: dict = None, ip_address: str = None, user_agent: str = None):
        """Creates and commits a new audit entry"""
        try:
            from flask import request, has_request_context
            if has_request_context():
                if not ip_address:
                    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
                    if ip_address and ',' in ip_address:
                        ip_address = ip_address.split(',')[0].strip()
                if not user_agent:
                    user_agent = request.headers.get('User-Agent', '')[:255]

            log_entry = cls(
                admin_email=admin_email,
                action=action,
                target_type=target_type,
                target_id=str(target_id) if target_id is not None else None,
                details=details or {},
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.session.add(log_entry)
            db.session.commit()
            return log_entry
        except Exception as e:
            db.session.rollback()
            return None

    def to_dict(self):
        return {
            'id': self.id,
            'admin_email': self.admin_email,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
