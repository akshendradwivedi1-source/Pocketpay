from flask import Blueprint, render_template, jsonify, Response, request

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/favicon.ico')
def favicon():
    import os
    from flask import current_app, send_from_directory
    return send_from_directory(
        os.path.join(current_app.root_path, 'static', 'img'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon',
        max_age=86400
    )


@bp.route('/health', methods=['GET'])
def health():
    """Production health check probe for load balancers and uptime monitoring"""
    from datetime import datetime
    from app.extensions import db
    from sqlalchemy import text
    
    db_status = 'ok'
    try:
        db.session.execute(text('SELECT 1'))
    except Exception as e:
        db_status = f'error: {str(e)}'
        
    return jsonify({
        'status': 'healthy' if db_status == 'ok' else 'degraded',
        'app': 'PocketPay',
        'database': db_status,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }), 200 if db_status == 'ok' else 503


@bp.route('/admin-approve-otp', methods=['GET', 'POST'])
def root_admin_approve_otp():
    from app.blueprints.auth import admin_approve_otp
    return admin_approve_otp()


@bp.route('/<path:path>')
def catch_all(path):
    if path.startswith(('api/', 'auth/')):
        return jsonify({
            'success': False,
            'message': f'Endpoint /{path} not found',
            'code': 'NOT_FOUND'
        }), 404
    return render_template('index.html')
