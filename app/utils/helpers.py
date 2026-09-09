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
            'akshendra.dwivedi1@gmail.com'
        )
    return str(admin_email).strip().lower()


def is_admin_user(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_admin', False):
        return True
    admin_email = get_admin_email()
    if admin_email:
        user_email = str(getattr(user, 'email', '') or '').strip().lower()
        if user_email == admin_email:
            return True
    return False


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
            return redirect(url_for('admin.admin_login', next=request.url))
        
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


def get_public_base_url(req=None):
    """
    Returns the public base URL for links and QR destinations,
    prioritizing active request host or APP_BASE_URL config.
    """
    import os
    req_obj = req
    if not req_obj:
        try:
            from flask import has_request_context
            if has_request_context():
                req_obj = request
        except Exception:
            pass

    if req_obj:
        try:
            proto = req_obj.headers.get('X-Forwarded-Proto', 'https' if getattr(req_obj, 'is_secure', False) else req_obj.scheme or 'http')
            host = req_obj.headers.get('X-Forwarded-Host', getattr(req_obj, 'host', ''))
            if host:
                return f"{proto}://{host}".rstrip('/')
            if getattr(req_obj, 'host_url', None):
                return req_obj.host_url.rstrip('/')
        except Exception:
            pass

    if current_app:
        configured = (current_app.config.get('APP_BASE_URL') or os.environ.get('APP_BASE_URL') or '').strip().rstrip('/')
        if configured:
            return configured

    return 'http://localhost:5000'


def build_qr_wallet_url(user, req=None):
    upi = getattr(user, 'virtual_upi_id', None) or f"{getattr(user, 'email', 'user').split('@')[0]}@pocketpay"
    name = getattr(user, 'full_name', '') or 'User'
    import urllib.parse
    # Standard UPI URI payload recognizable by any phone camera, Google Lens, or scanner
    return f"upi://pay?pa={upi}&pn={urllib.parse.quote(name)}&cu=INR"


def build_qr_user_url(user, req=None):
    return build_qr_wallet_url(user, req)


def build_qr_pocket_url(pocket, req=None):
    base = get_public_base_url(req)
    ref = getattr(pocket, 'id', '')
    return f"{base}/qr/pocket/{ref}"


def build_qr_tx_url(tx, req=None):
    base = get_public_base_url(req)
    tx_id = getattr(tx, 'transaction_id', None) or getattr(tx, 'uuid', '')
    return f"{base}/qr/tx/{tx_id}"


def generate_qr_code(data_string, size=300):
    """
    Generates a genuine, machine-readable black-and-white QR code with
    standard 4-module quiet zone margin and high contrast for camera scanning.
    """
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M
    import io
    import base64
    from PIL import Image
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=10,
            border=4,  # Standard 4-module quiet zone ensures phone camera recognition
        )
        qr.add_data(str(data_string).strip())
        qr.make(fit=True)
        # High contrast pure black modules on pure white background
        img = qr.make_image(fill_color="#000000", back_color="#ffffff")
        if hasattr(Image, 'Resampling'):
            img = img.resize((size, size), Image.Resampling.NEAREST)
        else:
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
