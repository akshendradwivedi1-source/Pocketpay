from datetime import datetime
from app.extensions import db


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='info')
    priority = db.Column(db.String(20), default='normal')
    
    pocket_id = db.Column(db.Integer, nullable=True)
    transaction_id = db.Column(db.Integer, nullable=True)
    extra_data = db.Column(db.JSON, default=dict)
    
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    user = db.relationship('User', back_populates='notifications')
    
    def mark_read(self):
        self.is_read = True
        self.read_at = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'priority': self.priority,
            'pocket_id': self.pocket_id,
            'transaction_id': self.transaction_id,
            'extra_data': self.extra_data or {},
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    @staticmethod
    def create(user_id, title, message, notif_type='info', priority='normal', commit=True, **kwargs):
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notif_type,
            priority=priority,
            **kwargs
        )
        db.session.add(notif)
        if commit:
            db.session.commit()
        
        try:
            from app.models.user import User
            from app.telegram.service import TelegramService
            user = db.session.get(User, user_id)
            if user:
                TelegramService.send_event_notification(user, title, message, event_type=notif_type)
        except Exception:
            pass
            
        return notif

    
    @staticmethod
    def budget_alert(user_id, pocket, percent_used):
        title = f'Budget Alert: {pocket.name}'
        if percent_used >= 100:
            message = f'You have exhausted your budget for {pocket.name}!'
            priority = 'high'
            notif_type = 'warning'
        elif percent_used >= 90:
            message = f'You have used {percent_used:.0f}% of your {pocket.name} budget.'
            priority = 'high'
            notif_type = 'warning'
        elif percent_used >= 75:
            message = f'You have used {percent_used:.0f}% of your {pocket.name} budget.'
            priority = 'normal'
            notif_type = 'info'
        else:
            return None
        return Notification.create(user_id, title, message, notif_type, priority,
                                   pocket_id=pocket.id)
    
    @staticmethod
    def low_balance_alert(user_id, pocket):
        title = f'Low Balance: {pocket.name}'
        message = f'Your {pocket.name} pocket has only ₹{pocket.current_balance:.2f} remaining.'
        return Notification.create(user_id, title, message, 'warning', 'high',
                                   pocket_id=pocket.id)
    
    @staticmethod
    def transaction_alert(user_id, transaction, commit=True):
        if transaction.type == 'expense':
            title = 'Payment Made'
            pocket = transaction.from_pocket
            message = f'₹{transaction.amount:.2f} spent from {pocket.name if pocket else "Wallet"}'
        elif transaction.type == 'income':
            title = 'Money Received'
            pocket = transaction.to_pocket
            message = f'₹{transaction.amount:.2f} added to {pocket.name if pocket else "Wallet"}'
        elif transaction.type == 'transfer':
            title = 'Transfer Complete'
            message = f'₹{transaction.amount:.2f} transferred between pockets'
        else:
            title = 'Transaction Complete'
            message = f'₹{transaction.amount:.2f} {transaction.type}'
        return Notification.create(user_id, title, message, 'success', 'normal',
                                   commit=commit,
                                   transaction_id=transaction.id)
