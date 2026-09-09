import hashlib
import json
from datetime import datetime
from app.extensions import db


class IdempotencyRecord(db.Model):
    __tablename__ = 'idempotency_records'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(128), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    endpoint = db.Column(db.String(255), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), default='processing', nullable=False)  # 'processing', 'completed', 'failed'
    response_code = db.Column(db.Integer, nullable=True)
    response_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def compute_hash(data):
        if data is None:
            return hashlib.sha256(b'').hexdigest()
        if isinstance(data, str):
            payload = data.encode('utf-8')
        else:
            try:
                payload = json.dumps(data, sort_keys=True).encode('utf-8')
            except Exception:
                payload = str(data).encode('utf-8')
        return hashlib.sha256(payload).hexdigest()
