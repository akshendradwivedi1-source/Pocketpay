from datetime import datetime, timedelta
import random
from faker import Faker
from app.extensions import db
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction, EXPENSE_CATEGORIES
from app.models.distribution_rule import DistributionRule
from app.models.notification import Notification
from app.models.budget import Budget

fake = Faker('en_IN')


def seed_database_if_empty():
    if User.query.count() > 0:
        return
    
    print('[Seed] Seeding PocketPay database with demo data...')
    
    demo_user = User(
        email='demo@pocketpay.app',
        phone='+91 98765 43210',
        full_name='Arjun Sharma',
        password='Demo@123',
        wallet_balance=25000.00,
        email_verified=True,
        phone_verified=True,
        theme_preference='dark',
        is_premium=True
    )
    demo_user.set_transaction_pin('1234')
    demo_user.generate_virtual_ids()
    db.session.add(demo_user)
    db.session.flush()
    
    pockets_config = [
        {'name': 'Savings', 'icon': 'piggy-bank', 'color': '#22c55e',
         'budget': 50000, 'monthly': 10000, 'priority': 5, 'balance': 35000},
        {'name': 'Food', 'icon': 'utensils', 'color': '#f97316',
         'budget': 12000, 'monthly': 12000, 'priority': 3, 'balance': 5720},
        {'name': 'Rent', 'icon': 'home', 'color': '#6366f1',
         'budget': 0, 'monthly': 25000, 'priority': 5, 'balance': 0},
        {'name': 'Investments', 'icon': 'line-chart', 'color': '#8b5cf6',
         'budget': 200000, 'monthly': 15000, 'priority': 4, 'balance': 125000},
        {'name': 'Entertainment', 'icon': 'gamepad-2', 'color': '#ec4899',
         'budget': 5000, 'monthly': 5000, 'priority': 1, 'balance': 3250},
        {'name': 'Shopping', 'icon': 'shopping-bag', 'color': '#f43f5e',
         'budget': 8000, 'monthly': 8000, 'priority': 2, 'balance': 1450},
        {'name': 'Transport', 'icon': 'car', 'color': '#0ea5e9',
         'budget': 6000, 'monthly': 6000, 'priority': 3, 'balance': 2890},
        {'name': 'Emergency Fund', 'icon': 'shield-alert', 'color': '#ef4444',
         'budget': 500000, 'monthly': 10000, 'priority': 5, 'balance': 150000},
        {'name': 'Europe Trip', 'icon': 'plane', 'color': '#06b6d4',
         'budget': 250000, 'monthly': 0, 'priority': 4, 'balance': 85000},
        {'name': 'Gym & Fitness', 'icon': 'dumbbell', 'color': '#14b8a6',
         'budget': 3000, 'monthly': 3000, 'priority': 2, 'balance': 1500},
        {'name': 'Netflix & Subscriptions', 'icon': 'video', 'color': '#e11d48',
         'budget': 2000, 'monthly': 2000, 'priority': 1, 'balance': 650},
        {'name': 'Bills & Utilities', 'icon': 'zap', 'color': '#eab308',
         'budget': 0, 'monthly': 8000, 'priority': 4, 'balance': 1200},
    ]
    
    created_pockets = {}
    for i, pc in enumerate(pockets_config):
        p = Pocket(
            user_id=demo_user.id,
            name=pc['name'],
            description=f'Monthly budget for {pc["name"].lower()} expenses',
            color=pc['color'],
            icon=pc['icon'],
            budget_amount=pc['budget'],
            monthly_limit=pc['monthly'],
            priority=pc['priority'],
            sort_order=i,
            current_balance=pc['balance'],
            total_received=pc['balance'] * 1.5 if random.random() > 0.5 else pc['balance'],
            total_spent=pc['balance'] * 0.8 if random.random() > 0.5 else pc['budget'] * 0.3,
        )
        p.total_received = max(pc['balance'], p.total_received)
        p.total_spent = max(0, p.total_received - pc['balance'])
        db.session.add(p)
        created_pockets[pc['name']] = p
    db.session.flush()
    
    rule_configs = [
        {'name': 'Salary Default', 'type': 'percentage', 'default': True,
         'allocations': [
             {'pocket_id': created_pockets['Savings'].id, 'pocket_name': 'Savings', 'percentage': 40},
             {'pocket_id': created_pockets['Rent'].id, 'pocket_name': 'Rent', 'percentage': 25},
             {'pocket_id': created_pockets['Food'].id, 'pocket_name': 'Food', 'percentage': 15},
             {'pocket_id': created_pockets['Investments'].id, 'pocket_name': 'Investments', 'percentage': 10},
             {'pocket_id': created_pockets['Entertainment'].id, 'pocket_name': 'Entertainment', 'percentage': 10},
         ]},
        {'name': 'Bonus Split', 'type': 'percentage',
         'allocations': [
             {'pocket_id': created_pockets['Investments'].id, 'pocket_name': 'Investments', 'percentage': 50},
             {'pocket_id': created_pockets['Emergency Fund'].id, 'pocket_name': 'Emergency Fund', 'percentage': 25},
             {'pocket_id': created_pockets['Europe Trip'].id, 'pocket_name': 'Europe Trip', 'percentage': 25},
         ]},
    ]
    for rc in rule_configs:
        rule = DistributionRule(
            user_id=demo_user.id,
            name=rc['name'],
            rule_type=rc['type'],
            is_default=rc.get('default', False),
            description=f'Auto-split rule for {rc["name"].lower()}',
            allocations=rc['allocations'],
            usage_count=random.randint(1, 8)
        )
        rule.last_used_at = datetime.utcnow() - timedelta(days=random.randint(1, 30))
        db.session.add(rule)
    db.session.flush()
    
    merchants_by_category = {
        'Food & Dining': ['Swiggy', 'Zomato', 'Domino\'s', 'McDonald\'s', 'Starbucks', 'Cafe Coffee Day',
                          'Burger King', 'Pizza Hut', 'Subway', 'KFC', 'Barbeque Nation', 'BigBasket Fresh'],
        'Shopping': ['Amazon', 'Flipkart', 'Myntra', 'Ajio', 'Nykaa', 'Meesho', 'Reliance Trends',
                     'Shoppers Stop', ' Lifestyle', 'Westside', 'Decathlon', 'Nike Store'],
        'Transportation': ['Uber', 'Ola', 'Rapido', 'Metro Card', 'Indian Railways', 'IndiGo',
                           'Air India', 'Vistara', 'Grab', 'Zoomcar', 'Ather Energy', 'BPCL Petrol'],
        'Entertainment': ['Netflix', 'Hotstar', 'Prime Video', 'Spotify', 'Sony LIV', 'PVR Cinemas',
                          'BookMyShow', 'Steam', 'Epic Games', 'Apple Music', 'YouTube Premium', 'JioSaavn'],
        'Bills & Utilities': ['Electricity Bill', 'Water Bill', 'Gas Bill', 'Jio Fiber', 'Airtel Postpaid',
                              'Vi Postpaid', 'DTH Recharge', 'Municipal Tax', 'Clubhouse', 'Gym Membership'],
        'Healthcare': ['Apollo Pharmacy', '1mg', 'Netmeds', 'Cult.fit', 'HealthifyMe', 'Aster Hospitals',
                       'Medanta', 'Fortis', 'Manipal Hospital', 'Tata 1mg'],
        'Education': ['Udemy', 'Coursera', 'upGrad', 'Unacademy', 'BYJU\'S', 'Khan Academy',
                      'LinkedIn Learning', 'MasterClass', 'Simplilearn', 'NIIT'],
        'Groceries': ['BigBasket', 'Grofers', 'DMart Ready', 'Amazon Fresh', 'Reliance Smart',
                      'More Store', 'Star Bazaar', 'HyperCity', 'Nature\'s Basket'],
        'Rent': ['Landlord', 'Housing Society', 'Maintenance', 'Security Deposit', 'Broker Fee'],
        'Insurance': ['Life Insurance', 'Health Insurance', 'Car Insurance', 'Bike Insurance',
                      'Travel Insurance', 'LIC Premium'],
        'Investments': ['Zerodha', 'Upstox', 'Groww', 'SIP Mutual Fund', 'Stock Market',
                        'PPF', 'NPS', 'FD Deposit', 'RD Deposit', 'Gold ETF'],
        'Subscriptions': ['iCloud+', 'Google One', 'Adobe Creative Cloud', 'Figma', 'Canva Pro',
                          'Notion', 'Slack', 'GitHub Pro', 'AWS Free Tier', 'ChatGPT Plus'],
        'Gifts & Donations': ['Wedding Gift', 'Birthday Gift', 'Festival Gift', 'NGO Donation',
                              'Temple Donation', 'Charity Event'],
        'Sports & Fitness': ['Cult Pass', 'Gold\'s Gym', 'Fitness First', 'Yoga Class', 'Marathon Fee',
                             'Cricket Club', 'Swimming Pool', 'Tennis Academy'],
        'Gaming': ['PlayStation Store', 'Xbox Game Pass', 'Nintendo eShop', 'Steam Gift Card',
                   'Mobile Game Purchase', 'Genshin Impact'],
    }
    
    pockets_list = [p for p in created_pockets.values()]
    tx_types_pockets = {
        'Food': 'Food & Dining',
        'Shopping': 'Shopping',
        'Transport': 'Transportation',
        'Entertainment': 'Entertainment',
        'Netflix & Subscriptions': 'Subscriptions',
        'Bills & Utilities': 'Bills & Utilities',
        'Gym & Fitness': 'Sports & Fitness',
        'Investments': 'Investments',
    }
    
    for d in range(90):
        day = datetime.utcnow() - timedelta(days=d)
        num_tx = random.randint(0, 6) if d < 30 else (random.randint(0, 3) if d < 60 else random.randint(0, 1))
        
        for _ in range(num_tx):
            pocket_name = random.choice(list(tx_types_pockets.keys()))
            pocket = created_pockets[pocket_name]
            category = tx_types_pockets[pocket_name]
            merchants = merchants_by_category.get(category, ['Other'])
            merchant = random.choice(merchants)
            
            if pocket_name == 'Investments':
                amount = round(random.uniform(2000, 25000), 0)
            elif pocket_name == 'Rent':
                continue
            elif pocket_name in ('Bills & Utilities', 'Food'):
                amount = round(random.uniform(200, 3500), 0)
            else:
                amount = round(random.uniform(99, 4500), 0)
            
            hour = random.randint(8, 23)
            minute = random.randint(0, 59)
            tx_time = day.replace(hour=hour, minute=minute, second=0)
            
            tx = Transaction(
                transaction_id=Transaction.generate_transaction_id(),
                user_id=demo_user.id,
                type='expense',
                status='completed',
                amount=amount,
                from_pocket_id=pocket.id,
                category=category,
                merchant=merchant,
                description=f'{merchant} - {category.lower()}',
                payment_method=random.choice(['upi', 'card', 'wallet']),
                tags=random.sample(['fast', 'local', 'premium', 'weekly', 'monthly'],
                                  k=random.randint(0, 2)),
                created_at=tx_time,
                completed_at=tx_time
            )
            tx.updated_at = tx_time
            db.session.add(tx)
    
    incomes = [
        (250000, 'Salary - TechCorp India', 'Salary Credit', 30),
        (120000, 'Freelance Project', 'Income from Design Project', 15),
        (45000, 'Performance Bonus', 'Q1 Performance Bonus', 45),
        (8000, 'Rental Income', 'Tenant Rent Payment', 10),
        (35000, 'Investment Dividend', 'Mutual Fund Dividend', 60),
        (5000, 'Referral Bonus', 'Friend Referral', 2),
        (22000, 'Refund - Tax', 'IT Department Refund', 5),
    ]
    
    for amt, desc, cat, days_ago in incomes:
        tx_time = datetime.utcnow() - timedelta(days=days_ago)
        rule = random.choice(list(created_pockets.keys()))
        to_pocket = created_pockets[rule if rule in created_pockets else 'Savings']
        
        tx = Transaction(
            transaction_id=Transaction.generate_transaction_id(),
            user_id=demo_user.id,
            type='income',
            status='completed',
            amount=amt,
            to_pocket_id=random.choice([to_pocket.id, created_pockets['Savings'].id, None]),
            category=cat,
            description=desc,
            payment_method='bank_transfer',
            upi_reference=f'NEFT{random.randint(100000,999999)}',
            created_at=tx_time,
            completed_at=tx_time
        )
        tx.updated_at = tx_time
        db.session.add(tx)
    
    transfer_pairs = [
        ('Savings', 'Food', 15000, 20),
        ('Savings', 'Shopping', 8000, 18),
        ('Food', 'Entertainment', 2000, 25),
        ('Savings', 'Rent', 25000, 28),
        ('Emergency Fund', 'Investments', 20000, 12),
        ('Investments', 'Europe Trip', 15000, 7),
    ]
    
    for from_name, to_name, amt, days_ago in transfer_pairs:
        tx_time = datetime.utcnow() - timedelta(days=days_ago)
        tx = Transaction(
            transaction_id=Transaction.generate_transaction_id(),
            user_id=demo_user.id,
            type='transfer',
            status='completed',
            amount=amt,
            from_pocket_id=created_pockets[from_name].id,
            to_pocket_id=created_pockets[to_name].id,
            description=f'Transfer: {from_name} → {to_name}',
            payment_method='internal',
            created_at=tx_time,
            completed_at=tx_time
        )
        tx.updated_at = tx_time
        db.session.add(tx)
    
    budget_names = list(tx_types_pockets.keys())[:5]
    for bname in budget_names:
        pocket = created_pockets.get(bname)
        if pocket and pocket.monthly_limit > 0:
            today = datetime.utcnow().date()
            b = Budget(
                user_id=demo_user.id,
                pocket_id=pocket.id,
                name=f'{pocket.name} Monthly',
                description=f'Monthly spending limit for {pocket.name}',
                category=tx_types_pockets[bname],
                period='monthly',
                start_date=today.replace(day=1),
                end_date=(today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
                limit_amount=pocket.monthly_limit,
                alert_threshold=80.0,
                is_active=True,
                repeat=True
            )
            db.session.add(b)
    
    notifications = [
        ('Budget Alert: Food', 'You have used 82% of your Food budget this month.', 'warning', 'high'),
        ('Salary Credited', '₹250,000 salary received and distributed across 5 pockets.', 'success', 'high'),
        ('Low Balance: Shopping', 'Your Shopping pocket has only ₹1,450 remaining.', 'warning', 'normal'),
        ('PIN Set Successfully', 'Transaction PIN protection is now active.', 'success', 'normal'),
        ('Welcome to PocketPay', 'Start by creating your first pocket to organize your money!', 'info', 'high'),
        ('Goal Progress: Europe Trip', 'You are 34% toward your €3,000 Europe trip goal!', 'info', 'normal'),
        ('Savings Milestone', 'Amazing! Your Savings pocket crossed ₹35,000.', 'success', 'high'),
        ('Recurring Payment: Netflix', 'Auto-deduct ₹649 scheduled in 2 days from Subscriptions pocket.', 'info', 'normal'),
    ]
    for title, msg, ntype, priority in notifications:
        notif = Notification(
            user_id=demo_user.id,
            title=title,
            message=msg,
            type=ntype,
            priority=priority,
            is_read=random.random() > 0.6,
            created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 200))
        )
        if notif.is_read:
            notif.read_at = notif.created_at + timedelta(minutes=random.randint(5, 180))
        db.session.add(notif)
    
    db.session.commit()
    
    total_pockets = Pocket.query.count()
    total_transactions = Transaction.query.count()
    total_balance = demo_user.wallet_balance + sum(p.current_balance for p in pockets_list)
    
    print('[Seed] Demo account created:')
    print('   Email:    demo@pocketpay.app')
    print('   Password: Demo@123')
    print('   PIN:      1234')
    print(f'   Pockets:  {total_pockets} custom pockets created')
    print(f'   Transactions: {total_transactions} entries')
    print(f'   Total Balance: Rs{total_balance:,.2f}')
    print('[Seed] PocketPay Smart Pocket System is ready!')
