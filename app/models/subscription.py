import uuid
from datetime import datetime
from app.extensions import db


class Subscription(db.Model):
    """
    PocketPay Premium Subscription Model.
    Tracks user subscriptions, payment gateway references, and status lifecycle.
    """
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    plan_id = db.Column(db.String(50), nullable=False)  # 'monthly', 'yearly'
    provider = db.Column(db.String(50), nullable=False, default='razorpay')  # 'razorpay', 'stripe'
    
    provider_customer_id = db.Column(db.String(100), nullable=True)
    provider_order_id = db.Column(db.String(100), nullable=True, index=True)
    provider_payment_id = db.Column(db.String(100), nullable=True, unique=True, index=True)
    provider_signature = db.Column(db.String(255), nullable=True)
    
    amount = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=False, default=0.0)
    currency = db.Column(db.String(10), default='INR')
    
    # Lifecycle: ACTIVE, EXPIRED, CANCELLED, PENDING, PAYMENT_FAILED
    status = db.Column(db.String(32), default='PENDING', index=True)
    
    start_date = db.Column(db.DateTime, nullable=True)
    expiry_date = db.Column(db.DateTime, nullable=True, index=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    meta_data = db.Column(db.JSON, default=dict)

    user = db.relationship('User', back_populates='subscriptions')

    def __init__(self, **kwargs):
        if 'plan' in kwargs and 'plan_id' not in kwargs:
            kwargs['plan_id'] = kwargs.pop('plan')
        if 'gateway' in kwargs and 'provider' not in kwargs:
            kwargs['provider'] = kwargs.pop('gateway')
        super().__init__(**kwargs)

    @property
    def plan(self):
        return self.plan_id

    @property
    def gateway(self):
        return self.provider

    @property
    def is_active(self):
        if self.status != 'ACTIVE':
            return False
        if self.expiry_date and self.expiry_date < datetime.utcnow():
            return False
        return True

    def to_dict(self):
        return {
            'id': self.id,
            'uuid': self.uuid,
            'user_id': self.user_id,
            'plan_id': self.plan_id,
            'plan': self.plan_id,
            'provider': self.provider,
            'gateway': self.provider,
            'provider_order_id': self.provider_order_id,
            'provider_payment_id': self.provider_payment_id,
            'amount': float(self.amount or 0.0),
            'currency': self.currency,
            'status': self.status,
            'is_active': self.is_active,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class PocketRule(db.Model):
    """
    Server-side smart automation rules for pockets.
    Executes only on explicit user enablement and validated balance.
    """
    __tablename__ = 'pocket_rules'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    source_pocket_id = db.Column(db.Integer, db.ForeignKey('pockets.id', ondelete='CASCADE'), nullable=True)
    target_pocket_id = db.Column(db.Integer, db.ForeignKey('pockets.id', ondelete='CASCADE'), nullable=False)
    
    rule_type = db.Column(db.String(50), nullable=False)  # 'incoming_split', 'min_balance_keep', 'surplus_transfer'
    trigger_condition = db.Column(db.String(100), default='on_deposit')
    amount = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=False, default=0.0)
    percentage = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Enhanced IF -> THEN Rule Engine fields
    name = db.Column(db.String(100), nullable=True)
    trigger_type = db.Column(db.String(50), default='INCOME_RECEIVED')  # 'INCOME_RECEIVED', 'BALANCE_EXCEEDS', 'RECURRING_INCOME'
    trigger_threshold = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=True)
    action_type = db.Column(db.String(50), default='ALLOCATE_PERCENT')  # 'ALLOCATE_PERCENT', 'MOVE_FIXED_AMOUNT'
    action_value = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=True)
    last_executed_at = db.Column(db.DateTime, nullable=True)
    execution_count = db.Column(db.Integer, default=0)
    last_status = db.Column(db.String(32), default='READY')  # READY, EXECUTED, FAILED

    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', back_populates='pocket_rules')
    target_pocket = db.relationship('Pocket', foreign_keys=[target_pocket_id])
    source_pocket = db.relationship('Pocket', foreign_keys=[source_pocket_id])
    executions = db.relationship('PocketRuleExecution', back_populates='rule', cascade='all, delete-orphan', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name or f"Rule #{self.id}",
            'user_id': self.user_id,
            'source_pocket_id': self.source_pocket_id,
            'target_pocket_id': self.target_pocket_id,
            'source_pocket_name': self.source_pocket.name if self.source_pocket else None,
            'target_pocket_name': self.target_pocket.name if self.target_pocket else None,
            'rule_type': self.rule_type,
            'trigger_condition': self.trigger_condition,
            'trigger_type': self.trigger_type or 'INCOME_RECEIVED',
            'trigger_threshold': float(self.trigger_threshold) if self.trigger_threshold is not None else None,
            'action_type': self.action_type or 'ALLOCATE_PERCENT',
            'action_value': float(self.action_value) if self.action_value is not None else (self.percentage or float(self.amount or 0.0)),
            'amount': float(self.amount or 0.0),
            'percentage': self.percentage,
            'is_active': self.is_active,
            'last_executed_at': self.last_executed_at.isoformat() if self.last_executed_at else None,
            'execution_count': self.execution_count or 0,
            'last_status': self.last_status or 'READY',
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class PocketRuleExecution(db.Model):
    """
    Audit log of rule executions.
    Guarantees no rule is ever executed twice for the same qualifying transaction.
    """
    __tablename__ = 'pocket_rule_executions'

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('pocket_rules.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    trigger_transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id', ondelete='SET NULL'), nullable=True, index=True)
    executed_amount = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False, default=0.0)
    status = db.Column(db.String(32), default='SUCCESS')  # 'SUCCESS', 'SKIPPED', 'FAILED'
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    rule = db.relationship('PocketRule', back_populates='executions')

    def to_dict(self):
        return {
            'id': self.id,
            'rule_id': self.rule_id,
            'user_id': self.user_id,
            'trigger_transaction_id': self.trigger_transaction_id,
            'executed_amount': float(self.executed_amount or 0.0),
            'status': self.status,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class DetectedSubscription(db.Model):
    """
    Premium Recurring Subscription Detector.
    Tracks recurring merchant transactions identified from transaction history.
    """
    __tablename__ = 'detected_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    merchant_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=False, default=0.0)
    frequency = db.Column(db.String(32), default='monthly')  # 'monthly', 'yearly', 'weekly'
    estimated_monthly_cost = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=False, default=0.0)
    last_payment_date = db.Column(db.DateTime, nullable=True)
    next_expected_date = db.Column(db.DateTime, nullable=True)
    is_confirmed = db.Column(db.Boolean, default=True)
    is_ignored = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'merchant_name': self.merchant_name,
            'service': self.merchant_name,
            'amount': float(self.amount or 0.0),
            'frequency': self.frequency,
            'estimated_monthly_cost': float(self.estimated_monthly_cost or 0.0),
            'last_payment_date': self.last_payment_date.isoformat() if self.last_payment_date else None,
            'next_expected_date': self.next_expected_date.isoformat() if self.next_expected_date else None,
            'is_confirmed': bool(self.is_confirmed),
            'is_ignored': bool(self.is_ignored)
        }


class LoginEvent(db.Model):
    """
    Security Centre Audit: Tracks login and device history without storing credentials.
    """
    __tablename__ = 'login_events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    device_type = db.Column(db.String(64), default='Desktop')
    location = db.Column(db.String(128), default='India')
    status = db.Column(db.String(32), default='SUCCESS')  # SUCCESS, FAILED
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', back_populates='login_events')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'device_type': self.device_type,
            'location': self.location,
            'status': self.status,
            'timestamp': self.created_at.isoformat() if self.created_at else None
        }
