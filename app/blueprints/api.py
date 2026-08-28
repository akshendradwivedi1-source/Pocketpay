from flask import Blueprint, request, current_app
from flask_login import current_user
from app.extensions import db
from app.utils.helpers import (
    json_response, error_response, validate_required_fields,
    api_login_required, generate_qr_code
)

bp = Blueprint('api', __name__)


@bp.route('/health', methods=['GET'])
def health_check():
    return json_response({
        'status': 'healthy',
        'app': 'PocketPay Smart Pocket System',
        'version': '1.0.0',
        'debug': current_app.config.get('DEBUG', False),
        'features': [
            'Dynamic Pocket Management',
            'Smart Income Distribution',
            'Smart Expense Flow',
            'Transaction PIN Security',
            'Analytics & Reports',
            'Budget Alerts',
            'QR Code Generation'
        ]
    })


@bp.route('/icon-options', methods=['GET'])
def get_icon_options():
    icons = [
        {'name': 'wallet', 'category': 'finance'},
        {'name': 'credit-card', 'category': 'finance'},
        {'name': 'banknote', 'category': 'finance'},
        {'name': 'coins', 'category': 'finance'},
        {'name': 'piggy-bank', 'category': 'finance'},
        {'name': 'landmark', 'category': 'finance'},
        {'name': 'euro', 'category': 'finance'},
        {'name': 'dollar-sign', 'category': 'finance'},
        {'name': 'rupee', 'category': 'finance'},
        {'name': 'pound-sterling', 'category': 'finance'},
        {'name': 'home', 'category': 'lifestyle'},
        {'name': 'utensils', 'category': 'food'},
        {'name': 'utensils-crossed', 'category': 'food'},
        {'name': 'coffee', 'category': 'food'},
        {'name': 'shopping-bag', 'category': 'shopping'},
        {'name': 'shopping-cart', 'category': 'shopping'},
        {'name': 'shirt', 'category': 'shopping'},
        {'name': 'gem', 'category': 'shopping'},
        {'name': 'car', 'category': 'transport'},
        {'name': 'bus', 'category': 'transport'},
        {'name': 'train', 'category': 'transport'},
        {'name': 'plane', 'category': 'transport'},
        {'name': 'bicycle', 'category': 'transport'},
        {'name': 'fuel', 'category': 'transport'},
        {'name': 'ticket', 'category': 'transport'},
        {'name': 'building-2', 'category': 'housing'},
        {'name': 'home', 'category': 'housing'},
        {'name': 'key', 'category': 'housing'},
        {'name': 'wrench', 'category': 'housing'},
        {'name': 'heart', 'category': 'health'},
        {'name': 'stethoscope', 'category': 'health'},
        {'name': 'pill', 'category': 'health'},
        {'name': 'dumbbell', 'category': 'fitness'},
        {'name': 'activity', 'category': 'fitness'},
        {'name': 'trophy', 'category': 'fitness'},
        {'name': 'graduation-cap', 'category': 'education'},
        {'name': 'book-open', 'category': 'education'},
        {'name': 'bookmark', 'category': 'education'},
        {'name': 'briefcase', 'category': 'work'},
        {'name': 'building', 'category': 'work'},
        {'name': 'laptop', 'category': 'work'},
        {'name': 'rocket', 'category': 'savings'},
        {'name': 'target', 'category': 'savings'},
        {'name': 'trending-up', 'category': 'savings'},
        {'name': 'trending-down', 'category': 'savings'},
        {'name': 'line-chart', 'category': 'investments'},
        {'name': 'bar-chart-3', 'category': 'investments'},
        {'name': 'pie-chart', 'category': 'investments'},
        {'name': 'briefcase-business', 'category': 'investments'},
        {'name': 'video', 'category': 'entertainment'},
        {'name': 'music', 'category': 'entertainment'},
        {'name': 'gamepad-2', 'category': 'entertainment'},
        {'name': 'film', 'category': 'entertainment'},
        {'name': 'party-popper', 'category': 'entertainment'},
        {'name': 'gift', 'category': 'gifts'},
        {'name': 'heart-handshake', 'category': 'gifts'},
        {'name': 'airplane', 'category': 'travel'},
        {'name': 'hotel', 'category': 'travel'},
        {'name': 'compass', 'category': 'travel'},
        {'name': 'map', 'category': 'travel'},
        {'name': 'camera', 'category': 'travel'},
        {'name': 'phone', 'category': 'tech'},
        {'name': 'smartphone', 'category': 'tech'},
        {'name': 'monitor', 'category': 'tech'},
        {'name': 'headphones', 'category': 'tech'},
        {'name': 'wifi', 'category': 'bills'},
        {'name': 'zap', 'category': 'bills'},
        {'name': 'droplets', 'category': 'bills'},
        {'name': 'flame', 'category': 'bills'},
        {'name': 'shield-alert', 'category': 'insurance'},
        {'name': 'shield-check', 'category': 'insurance'},
        {'name': 'users', 'category': 'family'},
        {'name': 'user-plus', 'category': 'family'},
        {'name': 'baby', 'category': 'family'},
        {'name': 'dog', 'category': 'pets'},
        {'name': 'cat', 'category': 'pets'},
        {'name': 'sparkles', 'category': 'beauty'},
        {'name': 'scissors', 'category': 'beauty'},
        {'name': 'flower-2', 'category': 'lifestyle'},
        {'name': 'leaf', 'category': 'lifestyle'},
        {'name': 'sun', 'category': 'lifestyle'},
        {'name': 'custom', 'category': 'other'},
        {'name': 'star', 'category': 'other'},
        {'name': 'flag', 'category': 'other'},
        {'name': 'archive', 'category': 'other'},
    ]
    return json_response({'icons': icons, 'count': len(icons)})


@bp.route('/color-options', methods=['GET'])
def get_color_options():
    colors = [
        {'name': 'Indigo', 'value': '#6366f1', 'gradient': ['#6366f1', '#8b5cf6']},
        {'name': 'Violet', 'value': '#8b5cf6', 'gradient': ['#8b5cf6', '#a855f7']},
        {'name': 'Purple', 'value': '#a855f7', 'gradient': ['#a855f7', '#d946ef']},
        {'name': 'Fuchsia', 'value': '#d946ef', 'gradient': ['#d946ef', '#ec4899']},
        {'name': 'Pink', 'value': '#ec4899', 'gradient': ['#ec4899', '#f43f5e']},
        {'name': 'Rose', 'value': '#f43f5e', 'gradient': ['#f43f5e', '#ef4444']},
        {'name': 'Red', 'value': '#ef4444', 'gradient': ['#ef4444', '#f97316']},
        {'name': 'Orange', 'value': '#f97316', 'gradient': ['#f97316', '#fb923c']},
        {'name': 'Amber', 'value': '#f59e0b', 'gradient': ['#f59e0b', '#eab308']},
        {'name': 'Yellow', 'value': '#eab308', 'gradient': ['#eab308', '#acc26a']},
        {'name': 'Lime', 'value': '#84cc16', 'gradient': ['#84cc16', '#22c55e']},
        {'name': 'Green', 'value': '#22c55e', 'gradient': ['#22c55e', '#10b981']},
        {'name': 'Emerald', 'value': '#10b981', 'gradient': ['#10b981', '#14b8a6']},
        {'name': 'Teal', 'value': '#14b8a6', 'gradient': ['#14b8a6', '#06b6d4']},
        {'name': 'Cyan', 'value': '#06b6d4', 'gradient': ['#06b6d4', '#0ea5e9']},
        {'name': 'Sky', 'value': '#0ea5e9', 'gradient': ['#0ea5e9', '#3b82f6']},
        {'name': 'Blue', 'value': '#3b82f6', 'gradient': ['#3b82f6', '#6366f1']},
        {'name': 'Navy', 'value': '#1e3a8a', 'gradient': ['#1e3a8a', '#312e81']},
        {'name': 'Slate', 'value': '#475569', 'gradient': ['#475569', '#334155']},
        {'name': 'Graphite', 'value': '#52525b', 'gradient': ['#52525b', '#3f3f46']},
        {'name': 'Charcoal', 'value': '#3f3f46', 'gradient': ['#3f3f46', '#27272a']},
        {'name': 'Midnight', 'value': '#1e293b', 'gradient': ['#1e293b', '#0f172a']},
        {'name': 'Bronze', 'value': '#92400e', 'gradient': ['#92400e', '#78350f']},
        {'name': 'Sage', 'value': '#65a30d', 'gradient': ['#65a30d', '#4d7c0f']},
    ]
    return json_response({'colors': colors, 'count': len(colors)})


@bp.route('/qr', methods=['GET'])
def get_qr_image():
    import base64
    from flask import Response
    from app.utils.helpers import build_qr_wallet_url, get_public_base_url
    default_url = build_qr_wallet_url(current_user) if (current_user and current_user.is_authenticated) else get_public_base_url()
    content = request.args.get('content') or request.args.get('data') or default_url
    size = request.args.get('size', 300, type=int)
    data_uri = generate_qr_code(content, size)
    if not data_uri or ',' not in data_uri:
        return error_response('Failed to generate QR code', 500)
    raw_b64 = data_uri.split(',', 1)[1]
    raw_png = base64.b64decode(raw_b64)
    return Response(raw_png, mimetype='image/png')


@bp.route('/qr/generate', methods=['POST'])
@api_login_required
def generate_custom_qr():
    from app.utils.helpers import build_qr_wallet_url
    data = request.get_json() or {}
    content = data.get('content') or build_qr_wallet_url(current_user)
    size = int(data.get('size', 300))
    
    qr = generate_qr_code(content, size)
    return json_response({
        'qr_code_url': qr,
        'content': content,
        'size': size
    })


@bp.route('/summary/dashboard', methods=['GET'])
@api_login_required
def dashboard_summary():
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from app.models.transaction import Transaction
    from app.models.pocket import Pocket
    
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    pockets = Pocket.query.filter_by(user_id=current_user.id, archived=False)\
        .order_by(Pocket.sort_order.asc(), Pocket.current_balance.desc()).all()
    
    total_pocket_balance = sum(p.current_balance for p in pockets)
    
    week_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.type.in_(['income', 'topup', 'refund']),
        Transaction.created_at >= week_ago
    ).scalar() or 0
    
    week_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        Transaction.created_at >= week_ago
    ).scalar() or 0
    
    month_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.type.in_(['income', 'topup', 'refund']),
        Transaction.created_at >= month_ago
    ).scalar() or 0
    
    month_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        Transaction.created_at >= month_ago
    ).scalar() or 0
    
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.created_at.desc()).limit(10).all()
    
    unread_count = current_user.notifications.filter_by(is_read=False).count()
    
    budget_pockets = [p for p in pockets if p.budget_usage_percent() >= 75]
    
    return json_response({
        'user': current_user.to_dict(),
        'balances': {
            'wallet': current_user.wallet_balance,
            'pockets': total_pocket_balance,
            'total': current_user.wallet_balance + total_pocket_balance,
            'pockets_count': len(pockets)
        },
        'weekly': {
            'income': round(week_income, 2),
            'expense': round(week_expense, 2),
            'net': round(week_income - week_expense, 2)
        },
        'monthly': {
            'income': round(month_income, 2),
            'expense': round(month_expense, 2),
            'net': round(month_income - month_expense, 2),
            'savings_rate': round(((month_income - month_expense) / month_income * 100) if month_income > 0 else 0, 1)
        },
        'pockets': [p.to_dict(True) for p in pockets],
        'recent_transactions': [t.to_dict(True) for t in recent_transactions],
        'alerts': {
            'unread_notifications': unread_count,
            'budget_warnings': len(budget_pockets),
            'needs_pin': current_user.transaction_pin_hash is None,
            'needs_email_verification': not current_user.email_verified
        }
    })


@bp.route('/assistant/ask', methods=['POST'])
def assistant_ask():
    from app.services.assistant_service import AssistantService
    data = request.get_json() or {}
    query = str(data.get('query', '')).strip()
    route = str(data.get('route', 'dashboard')).strip()
    history = data.get('history', [])
    
    user = current_user if current_user.is_authenticated else None
    result = AssistantService.process_query(user, query, route=route, chat_history=history)
    return json_response(result)

