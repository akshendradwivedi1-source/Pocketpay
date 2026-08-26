from datetime import datetime
from app.extensions import db


class DistributionRule(db.Model):
    __tablename__ = 'distribution_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    rule_type = db.Column(db.String(20), default='percentage')
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    allocations = db.Column(db.JSON, default=list)
    
    usage_count = db.Column(db.Integer, default=0)
    last_used_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', back_populates='distribution_rules')
    
    def validate_allocations(self, total_amount=None):
        if not self.allocations:
            return False, 'No allocations defined'
        if self.rule_type == 'percentage':
            total = sum(a.get('percentage', 0) for a in self.allocations)
            if abs(total - 100) > 0.01:
                return False, f'Percentages must sum to 100% (current: {total}%)'
        elif self.rule_type == 'fixed':
            if total_amount is not None:
                total = sum(a.get('amount', 0) for a in self.allocations)
                if abs(total - total_amount) > 0.01:
                    return False, f'Fixed amounts must sum to ₹{total_amount} (current: ₹{total})'
        return True, None
    
    def calculate_allocations(self, total_amount):
        valid, msg = self.validate_allocations(total_amount)
        if not valid:
            return None, msg
        result = []
        remaining = total_amount
        for i, alloc in enumerate(self.allocations):
            if self.rule_type == 'percentage':
                amount = round(total_amount * alloc.get('percentage', 0) / 100, 2)
                if i == len(self.allocations) - 1:
                    amount = round(remaining, 2)
                remaining = round(remaining - amount, 2)
            else:
                amount = alloc.get('amount', 0)
                if i == len(self.allocations) - 1:
                    amount = round(remaining, 2)
                remaining = round(remaining - amount, 2)
            result.append({
                'pocket_id': alloc.get('pocket_id'),
                'pocket_name': alloc.get('pocket_name'),
                'amount': amount,
                'percentage': alloc.get('percentage') if self.rule_type == 'percentage' else None,
            })
        return result, None
    
    def mark_used(self):
        self.usage_count += 1
        self.last_used_at = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'rule_type': self.rule_type,
            'is_default': self.is_default,
            'is_active': self.is_active,
            'allocations': self.allocations or [],
            'usage_count': self.usage_count,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
