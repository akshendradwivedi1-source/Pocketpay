from datetime import datetime
from types import SimpleNamespace
from app.extensions import db


class Budget(db.Model):
    __tablename__ = 'budgets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    pocket_id = db.Column(db.Integer, db.ForeignKey('pockets.id'), nullable=True, index=True)
    
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    category = db.Column(db.String(100), nullable=True)
    
    period = db.Column(db.String(20), default='monthly')
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    
    limit_amount = db.Column(db.Float, nullable=False)
    alert_threshold = db.Column(db.Float, default=80.0)
    
    is_active = db.Column(db.Boolean, default=True)
    repeat = db.Column(db.Boolean, default=True)
    
    alert_sent_75 = db.Column(db.Boolean, default=False)
    alert_sent_90 = db.Column(db.Boolean, default=False)
    alert_sent_100 = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', back_populates='budgets')
    pocket = db.relationship('Pocket', back_populates='budgets')
    
    def get_spent(self):
        from app.models.transaction import Transaction
        from sqlalchemy import and_
        query = Transaction.query.filter_by(
            user_id=self.user_id,
            type='expense'
        ).filter(
            and_(
                db.func.date(Transaction.created_at) >= self.start_date,
                db.func.date(Transaction.created_at) <= self.end_date
            )
        )
        if self.pocket_id:
            query = query.filter_by(from_pocket_id=self.pocket_id)
        if self.category:
            query = query.filter_by(category=self.category)
        return sum(t.amount for t in query.all())
    
    def get_remaining(self):
        return max(0, self.limit_amount - self.get_spent())
    
    def get_percentage_used(self):
        if self.limit_amount <= 0:
            return 0
        return min(100, (self.get_spent() / self.limit_amount) * 100)
    
    def check_and_send_alerts(self):
        from app.models.notification import Notification
        percent = self.get_percentage_used()
        pocket_ref = self.pocket or SimpleNamespace(id=self.pocket_id, name=self.name)
        if percent >= 75 and not self.alert_sent_75:
            Notification.budget_alert(self.user_id, pocket_ref, 75)
            self.alert_sent_75 = True
        if percent >= 90 and not self.alert_sent_90:
            Notification.budget_alert(self.user_id, pocket_ref, 90)
            self.alert_sent_90 = True
        if percent >= 100 and not self.alert_sent_100:
            Notification.budget_alert(self.user_id, pocket_ref, 100)
            self.alert_sent_100 = True
        db.session.commit()
    
    def to_dict(self):
        spent = self.get_spent()
        return {
            'id': self.id,
            'user_id': self.user_id,
            'pocket_id': self.pocket_id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'period': self.period,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'limit_amount': self.limit_amount,
            'spent': spent,
            'remaining': max(0, self.limit_amount - spent),
            'percentage_used': min(100, (spent / self.limit_amount * 100) if self.limit_amount > 0 else 0),
            'alert_threshold': self.alert_threshold,
            'is_active': self.is_active,
            'repeat': self.repeat,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
