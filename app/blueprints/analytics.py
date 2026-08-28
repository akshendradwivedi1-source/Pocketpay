from flask import Blueprint, request
from flask_login import current_user
from datetime import datetime, timedelta, date
from sqlalchemy import func, and_, or_, extract
from app.extensions import db
from app.models.pocket import Pocket
from app.models.transaction import Transaction, EXPENSE_CATEGORIES
from app.models.budget import Budget
from app.models.notification import Notification
from app.models.goal import SavingsGoal
from app.utils.helpers import (
    json_response, error_response, validate_required_fields,
    api_login_required, paginated_response, get_paginated_query
)

bp = Blueprint('analytics', __name__)


@bp.route('/overview', methods=['GET'])
@api_login_required
def get_overview():
    now = datetime.utcnow()
    current_month_start = datetime(now.year, now.month, 1)
    if now.month == 12:
        next_month_start = datetime(now.year + 1, 1, 1)
    else:
        next_month_start = datetime(now.year, now.month + 1, 1)
    last_month_end = current_month_start
    if now.month == 1:
        last_month_start = datetime(now.year - 1, 12, 1)
    else:
        last_month_start = datetime(now.year, now.month - 1, 1)
    
    def get_period_totals(start, end):
        income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type.in_(['income', 'topup', 'refund']),
            Transaction.created_at >= start,
            Transaction.created_at < end,
            Transaction.status == 'completed'
        ).scalar() or 0
        expense = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'expense',
            Transaction.created_at >= start,
            Transaction.created_at < end,
            Transaction.status == 'completed'
        ).scalar() or 0
        return round(income, 2), round(expense, 2)
    
    curr_income, curr_expense = get_period_totals(current_month_start, next_month_start)
    prev_income, prev_expense = get_period_totals(last_month_start, last_month_end)
    
    def calc_change(curr, prev):
        if prev == 0:
            return 100.0 if curr > 0 else 0.0
        return round(((curr - prev) / prev) * 100, 1)
    
    income_change = calc_change(curr_income, prev_income)
    expense_change = calc_change(curr_expense, prev_expense)
    savings_change = calc_change(
        curr_income - curr_expense, prev_income - prev_expense
    )
    
    pockets = Pocket.query.filter_by(user_id=current_user.id, archived=False).all()
    pocket_balance = sum(p.current_balance for p in pockets)
    total_assets = pocket_balance + current_user.wallet_balance
    
    active_budgets = Budget.query.filter_by(user_id=current_user.id, is_active=True).count()
    over_budget = Budget.query.filter_by(user_id=current_user.id, is_active=True).all()
    ob_count = sum(1 for b in over_budget if b.get_percentage_used() >= 100)
    at_risk_count = sum(1 for b in over_budget if 75 <= b.get_percentage_used() < 100)
    
    avg_daily_spend = curr_expense / max(1, now.day)
    projected_monthly = round(avg_daily_spend * 30, 2)
    
    return json_response({
        'current_month': {
            'income': curr_income,
            'expense': curr_expense,
            'net_savings': round(curr_income - curr_expense, 2),
            'savings_rate': round(((curr_income - curr_expense) / curr_income * 100) if curr_income > 0 else 0, 1)
        },
        'month_over_month': {
            'income_change_pct': income_change,
            'expense_change_pct': expense_change,
            'savings_change_pct': savings_change,
            'income_increased': income_change >= 0,
            'expense_increased': expense_change >= 0,
            'savings_increased': savings_change >= 0
        },
        'balances': {
            'pocket_balance': pocket_balance,
            'wallet_balance': current_user.wallet_balance,
            'total_assets': total_assets,
            'total_pockets': len(pockets)
        },
        'budgets': {
            'active': active_budgets,
            'over_budget': ob_count,
            'at_risk': at_risk_count,
            'healthy': active_budgets - ob_count - at_risk_count
        },
        'projections': {
            'average_daily_spend': round(avg_daily_spend, 2),
            'projected_monthly_expense': projected_monthly,
            'days_left_in_month': (next_month_start - now).days
        }
    })


@bp.route('/spending-by-category', methods=['GET'])
@api_login_required
def spending_by_category():
    now = datetime.utcnow()
    months = int(request.args.get('months', 1))
    
    start = now - timedelta(days=months * 30)
    
    txs = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        Transaction.status == 'completed',
        Transaction.created_at >= start
    ).all()
    
    category_data = {}
    for tx in txs:
        cat = tx.category or 'Other'
        if cat not in category_data:
            category_data[cat] = 0
        category_data[cat] += tx.amount
    
    total = sum(category_data.values())
    
    categories = []
    for cat, amount in sorted(category_data.items(), key=lambda x: -x[1]):
        pct = round((amount / total * 100) if total > 0 else 0, 1)
        categories.append({
            'category': cat,
            'amount': round(amount, 2),
            'percentage': pct,
            'count': sum(1 for t in txs if (t.category or 'Other') == cat)
        })
    
    return json_response({
        'categories': categories,
        'total_spent': round(total, 2),
        'period_months': months,
        'start_date': start.isoformat()
    })


@bp.route('/spending-by-pocket', methods=['GET'])
@api_login_required
def spending_by_pocket():
    now = datetime.utcnow()
    months = int(request.args.get('months', 1))
    start = now - timedelta(days=months * 30)
    
    pockets = Pocket.query.filter_by(user_id=current_user.id).all()
    
    pocket_data = []
    total_spent = 0
    
    for pocket in pockets:
        spent = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.from_pocket_id == pocket.id,
            Transaction.type == 'expense',
            Transaction.status == 'completed',
            Transaction.created_at >= start
        ).scalar() or 0
        
        received = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.to_pocket_id == pocket.id,
            Transaction.type.in_(['income', 'topup', 'refund', 'transfer']),
            Transaction.status == 'completed',
            Transaction.created_at >= start
        ).scalar() or 0
        
        total_spent += spent
        
        pocket_data.append({
            'pocket_id': pocket.id,
            'name': pocket.name,
            'color': pocket.color,
            'icon': pocket.icon,
            'current_balance': pocket.current_balance,
            'budget_amount': pocket.budget_amount,
            'monthly_limit': pocket.monthly_limit,
            'spent': round(spent, 2),
            'received': round(received, 2),
            'net': round(received - spent, 2),
            'archived': pocket.archived
        })
    
    for p in pocket_data:
        p['spend_percentage'] = round((p['spent'] / total_spent * 100) if total_spent > 0 else 0, 1)
    
    pocket_data.sort(key=lambda x: -x['spent'])
    
    return json_response({
        'pockets': pocket_data,
        'total_spent': round(total_spent, 2),
        'period_months': months
    })


@bp.route('/daily-trend', methods=['GET'])
@api_login_required
def daily_trend():
    days = int(request.args.get('days', 30))
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = now - timedelta(days=days - 1)
    
    daily_data = []
    for i in range(days):
        day_start = start + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        date_key = day_start.strftime('%Y-%m-%d')
        
        income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type.in_(['income', 'topup', 'refund']),
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
            Transaction.status == 'completed'
        ).scalar() or 0
        
        expense = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'expense',
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
            Transaction.status == 'completed'
        ).scalar() or 0
        
        daily_data.append({
            'date': date_key,
            'day_name': day_start.strftime('%a'),
            'day_num': day_start.day,
            'income': round(income, 2),
            'expense': round(expense, 2),
            'net': round(income - expense, 2)
        })
    
    total_income = sum(d['income'] for d in daily_data)
    total_expense = sum(d['expense'] for d in daily_data)
    
    return json_response({
        'daily': daily_data,
        'summary': {
            'total_income': round(total_income, 2),
            'total_expense': round(total_expense, 2),
            'net': round(total_income - total_expense, 2),
            'avg_income': round(total_income / days, 2),
            'avg_expense': round(total_expense / days, 2),
            'highest_spend_day': max(daily_data, key=lambda d: d['expense'])['date'],
            'highest_income_day': max(daily_data, key=lambda d: d['income'])['date']
        },
        'days': days
    })


@bp.route('/budget-performance', methods=['GET'])
@api_login_required
def budget_performance():
    budgets = Budget.query.filter_by(user_id=current_user.id, is_active=True)\
        .order_by(Budget.created_at.desc()).all()
    
    budget_performance = []
    for b in budgets:
        spent = b.get_spent()
        pct = min(100, (spent / b.limit_amount * 100) if b.limit_amount > 0 else 0)
        status = 'over' if pct >= 100 else ('at_risk' if pct >= 75 else ('warning' if pct >= 50 else 'healthy'))
        budget_performance.append({
            'budget': b.to_dict(),
            'status': status,
            'days_remaining': max(0, (b.end_date - datetime.utcnow().date()).days),
            'projected_spend': round((spent / max(1, (datetime.utcnow().date() - b.start_date).days + 1)) * max(1, (b.end_date - b.start_date).days + 1), 2)
        })
    
    return json_response({
        'budgets': budget_performance,
        'total_budgets': len(budget_performance),
        'healthy': sum(1 for b in budget_performance if b['status'] == 'healthy'),
        'warnings': sum(1 for b in budget_performance if b['status'] == 'warning'),
        'at_risk': sum(1 for b in budget_performance if b['status'] == 'at_risk'),
        'over_budget': sum(1 for b in budget_performance if b['status'] == 'over')
    })


@bp.route('/insights', methods=['GET'])
@api_login_required
def spending_insights():
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1)
    else:
        next_month = datetime(now.year, now.month + 1, 1)
    if now.month == 1:
        prev_month_start = datetime(now.year - 1, 12, 1)
    else:
        prev_month_start = datetime(now.year, now.month - 1, 1)
    
    def month_category_spending(start, end):
        txs = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'expense',
            Transaction.status == 'completed',
            Transaction.created_at >= start,
            Transaction.created_at < end
        ).all()
        cats = {}
        for t in txs:
            c = t.category or 'Other'
            cats[c] = cats.get(c, 0) + t.amount
        return cats
    
    curr_cats = month_category_spending(month_start, next_month)
    prev_cats = month_category_spending(prev_month_start, month_start)
    
    insights = []
    
    top_category = max(curr_cats, key=curr_cats.get) if curr_cats else None
    if top_category:
        insights.append({
            'type': 'top_category',
            'priority': 'high',
            'title': 'Top Spending Category',
            'message': f'{top_category} is your highest expense this month at ₹{curr_cats[top_category]:,.0f}.',
            'category': top_category,
            'amount': round(curr_cats[top_category], 2)
        })
    
    for cat in list(set(list(curr_cats.keys()) + list(prev_cats.keys()))):
        curr = curr_cats.get(cat, 0)
        prev = prev_cats.get(cat, 0)
        if prev > 0:
            change_pct = ((curr - prev) / prev) * 100
            if change_pct > 30:
                insights.append({
                    'type': 'category_spike',
                    'priority': 'warning',
                    'title': f'{cat} Spending Up',
                    'message': f'{cat} spending increased by {change_pct:.0f}% compared to last month.',
                    'category': cat,
                    'change_pct': round(change_pct, 1),
                    'prev_amount': round(prev, 2),
                    'curr_amount': round(curr, 2)
                })
            elif change_pct < -20:
                insights.append({
                    'type': 'category_drop',
                    'priority': 'success',
                    'title': f'{cat} Spending Down',
                    'message': f'Great! {cat} spending decreased by {abs(change_pct):.0f}% this month.',
                    'category': cat,
                    'change_pct': round(change_pct, 1),
                    'prev_amount': round(prev, 2),
                    'curr_amount': round(curr, 2)
                })
    
    pockets = Pocket.query.filter_by(user_id=current_user.id, archived=False).all()
    for p in pockets:
        usage = p.budget_usage_percent()
        if usage >= 90 and p.monthly_limit > 0:
            insights.append({
                'type': 'budget_nearly_full',
                'priority': 'high',
                'title': f'{p.name} Budget Alert',
                'message': f'You have used {usage:.0f}% of your {p.name} monthly budget.',
                'pocket_id': p.id,
                'pocket_name': p.name,
                'usage_percent': round(usage, 1),
                'limit': p.monthly_limit,
                'remaining': max(0, round(p.monthly_limit - p.monthly_spending(), 2))
            })
        elif usage >= 100 and p.budget_amount > 0:
            insights.append({
                'type': 'budget_exceeded',
                'priority': 'danger',
                'title': f'{p.name} Budget Exceeded',
                'message': f'You have exceeded your {p.name} budget by ₹{max(0, p.total_spent - p.budget_amount):,.0f}.',
                'pocket_id': p.id,
                'pocket_name': p.name,
                'usage_percent': round(usage, 1),
                'overage': round(max(0, p.total_spent - p.budget_amount), 2)
            })
    
    curr_income = sum(curr_cats.values()) * 0 + (db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.type.in_(['income', 'topup', 'refund']),
        Transaction.created_at >= month_start,
        Transaction.created_at < next_month,
        Transaction.status == 'completed'
    ).scalar() or 0)
    curr_expense = sum(curr_cats.values())
    if curr_income > 0:
        savings_rate = ((curr_income - curr_expense) / curr_income) * 100
        if savings_rate < 10 and curr_income > curr_expense:
            insights.append({
                'type': 'low_savings',
                'priority': 'warning',
                'title': 'Low Savings Rate',
                'message': f'Your savings rate is {savings_rate:.0f}%. Aim for at least 20%.',
                'savings_rate': round(savings_rate, 1),
                'recommended_rate': 20
            })
        elif savings_rate >= 30:
            insights.append({
                'type': 'high_savings',
                'priority': 'success',
                'title': 'Excellent Savings!',
                'message': f'Your {savings_rate:.0f}% savings rate is fantastic! Keep it up.',
                'savings_rate': round(savings_rate, 1)
            })
    
    insights.sort(key=lambda x: {'danger': 0, 'high': 1, 'warning': 2, 'success': 3, 'info': 4}.get(x['priority'], 5))
    
    return json_response({
        'insights': insights[:15],
        'total_insights': len(insights)
    })


@bp.route('/notifications', methods=['GET'])
@api_login_required
def list_notifications():
    query = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())
    
    only_unread = request.args.get('unread_only', 'false').lower() == 'true'
    if only_unread:
        query = query.filter_by(is_read=False)
    
    pagination = get_paginated_query(query)
    
    unread_count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    
    return json_response({
        **paginated_response(pagination, lambda n: n.to_dict()),
        'unread_count': unread_count
    })


@bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@api_login_required
def mark_notification_read(notif_id):
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
    if not notif:
        return json_response(message='Already read or not found')
    notif.mark_read()
    return json_response(message='Marked as read')


@bp.route('/notifications/read-all', methods=['POST'])
@api_login_required
def mark_all_notifications_read():
    updated = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    return json_response({'updated_count': updated}, f'Marked {updated} notifications as read')


@bp.route('/budgets', methods=['GET'])
@api_login_required
def list_budgets():
    query = Budget.query.filter_by(user_id=current_user.id)\
        .order_by(Budget.is_active.desc(), Budget.created_at.desc())
    budgets = [b.to_dict() for b in query.all()]
    return json_response({'budgets': budgets, 'total': len(budgets)})


@bp.route('/budgets', methods=['POST'])
@api_login_required
def create_budget():
    from datetime import date
    data = request.get_json() or {}
    required = ['name', 'limit_amount', 'period']
    for f in required:
        if not data.get(f):
            return json_response(f'Missing: {f}', 400) if False else error_response(f'Missing required: {f}', 400)
    
    name = data.get('name', '').strip()
    period = data.get('period', 'monthly')
    limit = float(data.get('limit_amount', 0))
    today = date.today()
    
    if period == 'weekly':
        start, end = today, today + timedelta(days=7)
    elif period == 'quarterly':
        end_month = today.month + 3 - (today.month - 1) % 3
        end_year = today.year
        if end_month > 12:
            end_month -= 12
            end_year += 1
        start, end = date(today.year, today.month, 1), date(end_year, end_month, 1)
    else:
        if today.month == 12:
            end = date(today.year + 1, 1, 1)
        else:
            end = date(today.year, today.month + 1, 1)
        start = date(today.year, today.month, 1)
    
    start_val = data.get('start_date')
    if isinstance(start_val, str):
        try:
            start_val = datetime.strptime(start_val, '%Y-%m-%d').date()
        except ValueError:
            start_val = start
    else:
        start_val = start_val or start

    end_val = data.get('end_date')
    if isinstance(end_val, str):
        try:
            end_val = datetime.strptime(end_val, '%Y-%m-%d').date()
        except ValueError:
            end_val = (end - timedelta(days=1)) if hasattr(end, 'day') else end
    else:
        end_val = end_val or ((end - timedelta(days=1)) if hasattr(end, 'day') else end)
    
    budget = Budget(
        user_id=current_user.id,
        pocket_id=data.get('pocket_id'),
        name=name,
        description=data.get('description', '').strip() or None,
        category=data.get('category'),
        period=period,
        start_date=start_val,
        end_date=end_val,
        limit_amount=limit,
        alert_threshold=float(data.get('alert_threshold', 80)),
        repeat=bool(data.get('repeat', True))
    )
    db.session.add(budget)
    db.session.commit()
    
    return json_response({'budget': budget.to_dict()}, 'Budget created', 201)


@bp.route('/budgets/<int:budget_id>', methods=['PUT'])
@api_login_required
def update_budget(budget_id):
    from datetime import date
    b = Budget.query.filter_by(id=budget_id, user_id=current_user.id).first()
    if not b:
        return error_response('Budget not found', 404)
    data = request.get_json() or {}

    if 'name' in data and data['name']:
        b.name = str(data['name']).strip()
    if 'description' in data:
        val = data.get('description')
        b.description = (str(val).strip() or None) if val else None
    if 'limit_amount' in data:
        val = data.get('limit_amount')
        try:
            fval = float(val)
            if fval > 0:
                b.limit_amount = fval
        except (TypeError, ValueError):
            pass
    if 'period' in data:
        period = str(data['period'])
        if period in ('weekly', 'monthly', 'quarterly', 'yearly'):
            b.period = period
            today = date.today()
            if period == 'weekly':
                b.start_date = data.get('start_date') or today
                b.end_date = data.get('end_date') or today + timedelta(days=7)
            elif period == 'quarterly':
                end_month = today.month + 3 - (today.month - 1) % 3
                end_year = today.year
                if end_month > 12:
                    end_month -= 12
                    end_year += 1
                b.start_date = data.get('start_date') or date(today.year, today.month, 1)
                b.end_date = data.get('end_date') or (date(end_year, end_month, 1) - timedelta(days=1))
            elif period == 'yearly':
                b.start_date = data.get('start_date') or date(today.year, today.month, 1)
                b.end_date = data.get('end_date') or date(today.year + 1, today.month, 1) - timedelta(days=1)
            else:
                if today.month == 12:
                    end = date(today.year + 1, 1, 1)
                else:
                    end = date(today.year, today.month + 1, 1)
                b.start_date = data.get('start_date') or date(today.year, today.month, 1)
                b.end_date = data.get('end_date') or (end - timedelta(days=1))
    if 'start_date' in data and 'period' not in data:
        b.start_date = data['start_date']
    if 'end_date' in data and 'period' not in data:
        b.end_date = data['end_date']
    if 'category' in data:
        b.category = data.get('category') or None
    if 'pocket_id' in data:
        val = data.get('pocket_id')
        b.pocket_id = int(val) if val not in (None, '', 'null') else None
    if 'is_active' in data:
        b.is_active = bool(data.get('is_active'))
    if 'repeat' in data:
        b.repeat = bool(data.get('repeat'))
    if 'alert_threshold' in data:
        try:
            v = float(data.get('alert_threshold'))
            if 0 <= v <= 100:
                b.alert_threshold = v
        except (TypeError, ValueError):
            pass

    db.session.commit()
    return json_response({'budget': b.to_dict()}, 'Budget updated')


@bp.route('/budgets/<int:budget_id>', methods=['DELETE'])
@api_login_required
def delete_budget(budget_id):
    b = Budget.query.filter_by(id=budget_id, user_id=current_user.id).first()
    if not b:
        return error_response('Budget not found', 404)
    db.session.delete(b)
    db.session.commit()
    return json_response(message='Budget deleted')


# =============================================================================
# SAVINGS GOALS ENDPOINTS (Phase 11)
# =============================================================================

@bp.route('/goals', methods=['GET'])
@api_login_required
def get_goals():
    """Lists all savings goals for the authenticated user"""
    goals = SavingsGoal.query.filter_by(user_id=current_user.id).order_by(SavingsGoal.created_at.desc()).all()
    total_target = sum(g.target_amount for g in goals)
    total_saved = sum(g.current_amount for g in goals)
    overall_progress = round((total_saved / total_target * 100) if total_target > 0 else 0, 1)

    return json_response({
        'items': [g.to_dict() for g in goals],
        'total_count': len(goals),
        'summary': {
            'total_target': total_target,
            'total_saved': total_saved,
            'total_remaining': max(0.0, total_target - total_saved),
            'overall_progress': overall_progress,
            'completed_count': sum(1 for g in goals if g.is_completed)
        }
    })


@bp.route('/goals', methods=['POST'])
@api_login_required
def create_goal():
    """Creates a new savings target goal"""
    data = request.get_json() or {}
    valid, msg = validate_required_fields(data, ['name', 'target_amount'])
    if not valid:
        return error_response(msg, 400)

    name = str(data.get('name', '')).strip()
    try:
        target = float(data.get('target_amount', 0))
        if target <= 0:
            return error_response('Target amount must be greater than ₹0', 400)
    except (TypeError, ValueError):
        return error_response('Invalid target amount', 400)

    initial_amount = 0.0
    if 'initial_amount' in data:
        try:
            initial_amount = max(0.0, float(data.get('initial_amount', 0)))
        except (TypeError, ValueError):
            initial_amount = 0.0

    target_date = None
    if data.get('target_date'):
        try:
            target_date = datetime.strptime(str(data['target_date']).split('T')[0], '%Y-%m-%d').date()
        except ValueError:
            target_date = None

    goal = SavingsGoal(
        user_id=current_user.id,
        name=name,
        description=str(data.get('description', '')).strip() or None,
        target_amount=target,
        current_amount=initial_amount,
        target_date=target_date,
        category=str(data.get('category', 'General')),
        icon=str(data.get('icon', 'target')),
        color=str(data.get('color', '#6366f1')),
        is_completed=initial_amount >= target
    )
    db.session.add(goal)
    db.session.commit()

    Notification.create(
        current_user.id,
        'Savings Goal Created',
        f'Goal "{name}" with target ₹{target:,.2f} has been created!',
        'success'
    )

    return json_response({'goal': goal.to_dict()}, 'Savings goal created successfully', 201)


@bp.route('/goals/<int:goal_id>', methods=['PUT'])
@api_login_required
def update_goal(goal_id):
    """Updates savings goal parameters"""
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=current_user.id).first()
    if not goal:
        return error_response('Savings goal not found', 404)

    data = request.get_json() or {}
    if 'name' in data and data['name']:
        goal.name = str(data['name']).strip()
    if 'description' in data:
        goal.description = str(data['description']).strip() or None
    if 'target_amount' in data:
        try:
            t = float(data['target_amount'])
            if t > 0:
                goal.target_amount = t
                goal.is_completed = goal.current_amount >= goal.target_amount
        except (TypeError, ValueError):
            pass
    if 'category' in data:
        goal.category = str(data['category'])
    if 'icon' in data:
        goal.icon = str(data['icon'])
    if 'color' in data:
        goal.color = str(data['color'])
    if 'target_date' in data:
        if data['target_date']:
            try:
                goal.target_date = datetime.strptime(str(data['target_date']).split('T')[0], '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            goal.target_date = None

    db.session.commit()
    return json_response({'goal': goal.to_dict()}, 'Savings goal updated')


@bp.route('/goals/<int:goal_id>/deposit', methods=['POST'])
@api_login_required
def deposit_to_goal(goal_id):
    """Adds funds toward a savings goal from available balance or a pocket"""
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=current_user.id).first()
    if not goal:
        return error_response('Savings goal not found', 404)

    data = request.get_json() or {}
    try:
        amount = float(data.get('amount', 0))
        if amount <= 0:
            return error_response('Deposit amount must be greater than ₹0', 400)
    except (TypeError, ValueError):
        return error_response('Invalid deposit amount', 400)

    source = data.get('source', 'wallet')
    if source == 'wallet':
        if (current_user.wallet_balance or 0.0) < amount:
            return error_response(f'Insufficient available balance (₹{current_user.wallet_balance:,.2f})', 400)
        current_user.wallet_balance = round(current_user.wallet_balance - amount, 2)
    else:
        pocket = Pocket.query.filter_by(id=int(source), user_id=current_user.id, archived=False).first()
        if not pocket:
            return error_response('Funding pocket not found', 404)
        if pocket.current_balance < amount:
            return error_response(f'Insufficient balance in {pocket.name} (₹{pocket.current_balance:,.2f})', 400)
        pocket.deduct_money(amount)

    goal.deposit(amount)
    db.session.commit()

    if goal.is_completed:
        Notification.create(
            current_user.id,
            '🎉 Savings Goal Achieved!',
            f'Congratulations! You reached your ₹{goal.target_amount:,.2f} target for "{goal.name}"!',
            'success',
            'high'
        )

    return json_response({
        'goal': goal.to_dict(),
        'wallet_balance': current_user.wallet_balance
    }, f'₹{amount:,.2f} deposited to "{goal.name}"')


@bp.route('/goals/<int:goal_id>/withdraw', methods=['POST'])
@api_login_required
def withdraw_from_goal(goal_id):
    """Withdraws funds from a savings goal back to available wallet balance"""
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=current_user.id).first()
    if not goal:
        return error_response('Savings goal not found', 404)

    data = request.get_json() or {}
    try:
        amount = float(data.get('amount', 0))
        if amount <= 0:
            return error_response('Withdraw amount must be greater than ₹0', 400)
    except (TypeError, ValueError):
        return error_response('Invalid withdraw amount', 400)

    try:
        goal.withdraw(amount)
        current_user.wallet_balance = round((current_user.wallet_balance or 0.0) + amount, 2)
        db.session.commit()
    except ValueError as ve:
        return error_response(str(ve), 400)

    return json_response({
        'goal': goal.to_dict(),
        'wallet_balance': current_user.wallet_balance
    }, f'₹{amount:,.2f} withdrawn from "{goal.name}" to wallet')


@bp.route('/goals/<int:goal_id>', methods=['DELETE'])
@api_login_required
def delete_goal(goal_id):
    """Deletes savings goal, refunding any saved amount back to wallet"""
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=current_user.id).first()
    if not goal:
        return error_response('Savings goal not found', 404)

    saved = goal.current_amount or 0.0
    if saved > 0:
        current_user.wallet_balance = round((current_user.wallet_balance or 0.0) + saved, 2)

    db.session.delete(goal)
    db.session.commit()

    return json_response({
        'refunded_amount': saved,
        'wallet_balance': current_user.wallet_balance
    }, f'Goal "{goal.name}" deleted' + (f' and ₹{saved:,.2f} refunded to wallet' if saved > 0 else ''))

