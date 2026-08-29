from datetime import datetime
from app.extensions import db


class TelegramUser(db.Model):
    """
    Maps a Telegram User ID to a PocketPay User account and persists
    per-user conversation states and multi-step transaction data.
    """
    __tablename__ = 'telegram_users'

    telegram_id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    username = db.Column(db.String(128), nullable=True)
    first_name = db.Column(db.String(128), nullable=True)
    state = db.Column(db.String(64), default='START', nullable=False)
    state_data = db.Column(db.JSON, default=dict, nullable=False)
    notifications_enabled = db.Column(db.Boolean, default=True, nullable=False)
    last_active_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


    user = db.relationship('User', backref=db.backref('telegram_users', lazy='dynamic', cascade='all, delete-orphan'))

    @property
    def is_authenticated(self):
        return self.user_id is not None and self.user is not None

    def set_state(self, state: str, data: dict = None):
        self.state = state
        if data is not None:
            self.state_data = data
        self.last_active_at = datetime.utcnow()
        db.session.commit()

    def update_state_data(self, **kwargs):
        current_data = dict(self.state_data or {})
        current_data.update(kwargs)
        self.state_data = current_data
        self.last_active_at = datetime.utcnow()
        db.session.commit()

    def clear_state(self):
        self.state = 'LOGGED_IN' if self.is_authenticated else 'START'
        self.state_data = {}
        self.last_active_at = datetime.utcnow()
        db.session.commit()

    def link_user(self, user):
        self.user_id = user.id
        self.state = 'LOGGED_IN'
        self.state_data = {}
        self.last_active_at = datetime.utcnow()
        db.session.commit()

    def unlink_user(self):
        self.user_id = None
        self.state = 'START'
        self.state_data = {}
        self.last_active_at = datetime.utcnow()
        db.session.commit()

    def to_dict(self):
        return {
            'telegram_id': self.telegram_id,
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'state': self.state,
            'is_authenticated': self.is_authenticated,
            'notifications_enabled': self.notifications_enabled,
            'last_active_at': self.last_active_at.isoformat() if self.last_active_at else None
        }

