import uuid
from datetime import datetime, date
from app.extensions import db


class SavingsGoal(db.Model):
    __tablename__ = 'savings_goals'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    target_amount = db.Column(db.Float, nullable=False, default=0.0)
    current_amount = db.Column(db.Float, nullable=False, default=0.0)
    target_date = db.Column(db.Date, nullable=True)

    category = db.Column(db.String(100), default='General')
    icon = db.Column(db.String(50), default='target')
    color = db.Column(db.String(20), default='#6366f1')
    is_completed = db.Column(db.Boolean, default=False)
    released_amount = db.Column(db.Float, default=0.0)
    released_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('savings_goals', cascade='all, delete-orphan', lazy='dynamic'))

    def deposit(self, amount: float) -> float:
        """Deposits money toward this goal"""
        amt = float(amount)
        if amt <= 0:
            raise ValueError("Deposit amount must be positive")
        self.current_amount = round(self.current_amount + amt, 2)
        if self.current_amount >= self.target_amount and self.target_amount > 0:
            self.is_completed = True
        return self.current_amount

    def release_to_wallet(self, user) -> float:
        """
        Releases the completed goal savings and transfers them directly into the user's available wallet balance.
        """
        amount_to_release = round(float(self.current_amount or 0.0), 2)
        if amount_to_release <= 0:
            return 0.0
        
        self.released_amount = round(float(self.released_amount or 0.0) + amount_to_release, 2)
        self.released_at = datetime.utcnow()
        self.current_amount = 0.0
        self.is_completed = True

        # Directly add to user's available balance
        user.wallet_balance = round(float(user.wallet_balance or 0.0) + amount_to_release, 2)
        return amount_to_release

    def withdraw(self, amount: float) -> float:
        """Withdraws money from this goal"""
        amt = float(amount)
        if amt <= 0:
            raise ValueError("Withdraw amount must be positive")
        if amt > self.current_amount:
            raise ValueError(f"Cannot withdraw ₹{amt:,.2f}; goal only has ₹{self.current_amount:,.2f}")
        self.current_amount = round(self.current_amount - amt, 2)
        if self.current_amount < self.target_amount:
            self.is_completed = False
        return self.current_amount

    def get_progress_percentage(self) -> float:
        if not self.target_amount or self.target_amount <= 0:
            return 100.0 if self.current_amount > 0 else 0.0
        pct = (self.current_amount / self.target_amount) * 100.0
        return round(min(100.0, max(0.0, pct)), 1)

    def days_remaining(self) -> int:
        if not self.target_date:
            return -1
        today = date.today()
        delta = (self.target_date - today).days
        return max(0, delta)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'uuid': self.uuid,
            'name': self.name,
            'description': self.description,
            'target_amount': self.target_amount,
            'current_amount': self.current_amount,
            'remaining_amount': max(0.0, round(self.target_amount - self.current_amount, 2)),
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'days_remaining': self.days_remaining(),
            'progress_percentage': self.get_progress_percentage(),
            'category': self.category,
            'icon': self.icon,
            'color': self.color,
            'is_completed': self.is_completed,
            'released_amount': float(self.released_amount or 0.0),
            'released_at': self.released_at.isoformat() if self.released_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
