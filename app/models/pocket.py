from datetime import datetime
from app.extensions import db


class Pocket(db.Model):
    __tablename__ = 'pockets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    color = db.Column(db.String(50), default='#6366f1')
    icon = db.Column(db.String(50), default='wallet')
    icon_type = db.Column(db.String(20), default='lucide')
    
    budget_amount = db.Column(db.Numeric(12, 2, asdecimal=False), default=0.0)
    monthly_limit = db.Column(db.Numeric(12, 2, asdecimal=False), default=0.0)
    priority = db.Column(db.Integer, default=0)
    sort_order = db.Column(db.Integer, default=0)
    
    current_balance = db.Column(db.Numeric(12, 2, asdecimal=False), default=0.0)
    total_received = db.Column(db.Numeric(12, 2, asdecimal=False), default=0.0)
    total_spent = db.Column(db.Numeric(12, 2, asdecimal=False), default=0.0)
    
    archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime, nullable=True)
    
    spending_rules = db.Column(db.JSON, default=dict)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Pocket Lock (Part 2 - Premium Feature)
    is_locked = db.Column(db.Boolean, default=False)
    locked_until_date = db.Column(db.DateTime, nullable=True)
    locked_goal_amount = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=True)
    lock_reason = db.Column(db.String(255), nullable=True)
    
    user = db.relationship('User', back_populates='pockets')
    transactions_from = db.relationship('Transaction', foreign_keys='Transaction.from_pocket_id',
                                         back_populates='from_pocket', cascade='all, delete-orphan')
    transactions_to = db.relationship('Transaction', foreign_keys='Transaction.to_pocket_id',
                                       back_populates='to_pocket', cascade='all, delete-orphan')
    budgets = db.relationship('Budget', back_populates='pocket', cascade='all, delete-orphan')
    
    __table_args__ = (db.Index('ix_user_pocket_sort', 'user_id', 'sort_order'),)
    
    def is_currently_locked(self):
        """
        Returns True if the pocket is currently locked and cannot be debited for payments.
        Checks explicit lock, date lock, and goal amount lock.
        """
        if not self.is_locked:
            return False
        # If locked until a date in the future
        if self.locked_until_date and datetime.utcnow() < self.locked_until_date:
            return True
        # If locked until a goal amount is reached
        if self.locked_goal_amount and float(self.current_balance or 0.0) < float(self.locked_goal_amount):
            return True
        # If lock was set with no auto-expiry, it remains locked until manually unlocked
        if not self.locked_until_date and not self.locked_goal_amount:
            return True
        return False
    
    def add_money(self, amount, commit=False):
        if amount <= 0:
            raise ValueError('Amount must be positive')
        self.current_balance = round(float(self.current_balance or 0.0) + float(amount), 2)
        self.total_received = round(float(self.total_received or 0.0) + float(amount), 2)
        if commit:
            db.session.commit()
    
    def deduct_money(self, amount, commit=False):
        if amount <= 0:
            raise ValueError('Amount must be positive')
        if float(self.current_balance or 0.0) < float(amount):
            raise ValueError('Insufficient balance')
        self.current_balance = round(float(self.current_balance or 0.0) - float(amount), 2)
        self.total_spent = round(float(self.total_spent or 0.0) + float(amount), 2)
        if commit:
            db.session.commit()
    
    def can_afford(self, amount):
        return self.current_balance >= amount
    
    def monthly_spending(self, year=None, month=None):
        from datetime import datetime
        from sqlalchemy import and_, or_
        if year is None:
            year = datetime.utcnow().year
        if month is None:
            month = datetime.utcnow().month
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        from app.models.transaction import Transaction
        spent = db.session.query(db.func.sum(Transaction.amount)).filter(
            Transaction.from_pocket_id == self.id,
            Transaction.type == 'expense',
            Transaction.created_at >= start,
            Transaction.created_at < end
        ).scalar() or 0.0
        return spent
    
    def budget_usage_percent(self):
        if self.budget_amount and self.budget_amount > 0:
            return min(100, (self.total_spent / self.budget_amount) * 100)
        if self.monthly_limit and self.monthly_limit > 0:
            spent = self.monthly_spending()
            return min(100, (spent / self.monthly_limit) * 100)
        return 0
    
    def archive(self):
        self.archived = True
        self.archived_at = datetime.utcnow()
        db.session.commit()
    
    def restore(self):
        self.archived = False
        self.archived_at = None
        db.session.commit()
    
    def to_dict(self, include_stats=False):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'icon': self.icon,
            'icon_type': self.icon_type,
            'budget_amount': round(float(self.budget_amount or 0.0), 2),
            'monthly_limit': round(float(self.monthly_limit or 0.0), 2),
            'priority': self.priority,
            'sort_order': self.sort_order,
            'current_balance': round(float(self.current_balance or 0.0), 2),
            'total_received': round(float(self.total_received or 0.0), 2),
            'total_spent': round(float(self.total_spent or 0.0), 2),
            'archived': self.archived,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'is_locked': bool(self.is_locked),
            'is_currently_locked': self.is_currently_locked(),
            'locked_until_date': self.locked_until_date.isoformat() if self.locked_until_date else None,
            'locked_goal_amount': round(float(self.locked_goal_amount), 2) if self.locked_goal_amount is not None else None,
            'lock_reason': self.lock_reason or '',
            'spending_rules': self.spending_rules or {},
            'budget_usage_percent': self.budget_usage_percent(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_stats:
            data['monthly_spending'] = self.monthly_spending()
        return data
