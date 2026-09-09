from functools import wraps
from flask import request, jsonify
from flask_login import current_user
from app.extensions import db
from app.models.idempotency import IdempotencyRecord
from app.utils.helpers import error_response


def get_idempotency_key(request_obj, body_data=None):
    """
    Extracts idempotency key from header or json payload.
    """
    key = request_obj.headers.get('Idempotency-Key') or request_obj.headers.get('X-Idempotency-Key')
    if not key and body_data and isinstance(body_data, dict):
        key = body_data.get('idempotency_key')
    return str(key).strip() if key else None


def check_idempotency(key, endpoint, user_id=None, request_data=None):
    """
    Checks if an idempotency record exists.
    Returns (record, cached_response_or_error)
    """
    if not key:
        return None, None

    clean_key = str(key).strip()
    req_hash = IdempotencyRecord.compute_hash(request_data)

    record = IdempotencyRecord.query.filter_by(key=clean_key).first()
    if record:
        if record.status == 'completed' and record.response_json is not None:
            # Replay previous response safely
            return record, (record.response_json, record.response_code or 200)
        elif record.status == 'processing':
            return record, ({
                'success': False,
                'message': 'A concurrent request with the same idempotency key is currently processing. Please wait.',
                'code': 'IDEMPOTENCY_IN_PROGRESS'
            }, 409)

    # Create new in-progress record
    try:
        new_record = IdempotencyRecord(
            key=clean_key,
            user_id=user_id,
            endpoint=endpoint,
            request_hash=req_hash,
            status='processing'
        )
        db.session.add(new_record)
        db.session.commit()
        return new_record, None
    except Exception:
        db.session.rollback()
        # Race condition: another thread inserted key concurrently
        existing = IdempotencyRecord.query.filter_by(key=clean_key).first()
        if existing and existing.status == 'completed' and existing.response_json is not None:
            return existing, (existing.response_json, existing.response_code or 200)
        return existing, ({
            'success': False,
            'message': 'Duplicate concurrent transaction request detected.',
            'code': 'CONCURRENT_REQUEST'
        }, 409)


def save_idempotency(record, response_json, status_code=200):
    """
    Finalizes an idempotency record with the resulting response.
    """
    if not record:
        return
    try:
        record.status = 'completed'
        record.response_code = status_code
        record.response_json = response_json
        db.session.commit()
    except Exception:
        db.session.rollback()
