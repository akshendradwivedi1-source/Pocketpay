from functools import wraps
from flask import jsonify, request, redirect, url_for, render_template, current_app
from flask_login import current_user, login_required
from datetime import datetime


def get_admin_email():
    admin_email = ''
    if current_app:
        admin_email = (
            current_app.config.get('POCKETPAY_ADMIN_EMAIL') or
            current_app.config.get('ADMIN_EMAIL') or
            current_app.config.get('MAIL_USERNAME') or
            ''
        )
    return str(admin_email).strip().lower()


def is_admin_user(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    admin_email = get_admin_email()
    if not admin_email:
        return False
    user_email = str(getattr(user, 'email', '') or '').strip().lower()
    return user_email == admin_email


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith('/api/') or request.path.startswith('/admin/api/'):
                return jsonify({
                    'success': False,
                    'error': 'Unauthorized',
                    'message': 'Admin login required'
                }), 401
            return redirect(url_for('main.index', next=request.url))
        
        if not is_admin_user(current_user):
            if request.is_json or request.path.startswith('/api/') or request.path.startswith('/admin/api/'):
                return jsonify({
                    'success': False,
                    'error': 'Forbidden',
                    'message': 'Access denied: Admin privileges required'
                }), 403
            return render_template('admin/403.html', user_email=getattr(current_user, 'email', '')), 403
        
        return f(*args, **kwargs)
    return decorated_function


def api_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'error': 'Unauthorized',
                'message': 'Admin login required'
            }), 401
        
        if not is_admin_user(current_user):
            return jsonify({
                'success': False,
                'error': 'Forbidden',
                'message': 'Access denied: Admin privileges required'
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function


def api_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'error': 'Authentication required',
                'message': 'Please log in to access this resource'
            }), 401
        return f(*args, **kwargs)
    return decorated_function


def json_response(data=None, message='Success', status_code=200, success=True, **extra):
    response = {
        'success': success,
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    if data is not None:
        response['data'] = data
    response.update(extra)
    return jsonify(response), status_code


def error_response(message='An error occurred', status_code=400, errors=None, code=None, **extra):
    response = {
        'success': False,
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    if errors:
        response['errors'] = errors
    if code:
        response['code'] = code
    response.update(extra)
    return jsonify(response), status_code


def get_paginated_query(query, page=None, per_page=None):
    default_per_page = 20
    max_per_page = 100
    try:
        page = max(1, int(page or request.args.get('page', 1, type=int) or 1))
        per_page = min(max_per_page, max(1, int(per_page or request.args.get('per_page', default_per_page, type=int) or default_per_page)))
    except (TypeError, ValueError):
        page = 1
        per_page = default_per_page
    return query.paginate(page=page, per_page=per_page, error_out=False)


def paginated_response(pagination, item_serializer=None):
    items = pagination.items
    if item_serializer:
        items = [item_serializer(item) for item in items]
    return {
        'items': items,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'total_pages': pagination.pages,
        'total_items': pagination.total,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
        'next_page': pagination.next_num if pagination.has_next else None,
        'prev_page': pagination.prev_num if pagination.has_prev else None,
    }


def validate_required_fields(data, required_fields):
    missing = []
    for field in required_fields:
        if isinstance(field, tuple):
            name, _ = field
            if name not in data or data[name] is None or data[name] == '':
                missing.append(name)
        else:
            if field not in data or data[field] is None or data[field] == '':
                missing.append(field)
    if missing:
        return False, f'Missing required fields: {", ".join(missing)}'
    return True, None


def generate_qr_code(data_string, size=300):
    import qrcode
    import io
    import base64
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((size, size))
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return f'data:image/png;base64,{img_base64}'
    except Exception:
        return None


def format_currency(amount, currency='INR'):
    try:
        amount = float(amount)
        if currency == 'INR':
            return f'₹{amount:,.2f}'
        elif currency == 'USD':
            return f'${amount:,.2f}'
        elif currency == 'EUR':
            return f'€{amount:,.2f}'
        else:
            return f'{currency} {amount:,.2f}'
    except (ValueError, TypeError):
        return f'{currency} {amount}'
