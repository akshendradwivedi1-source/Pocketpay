import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import func
from app.extensions import db
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.goal import SavingsGoal
from app.models.budget import Budget


class AssistantService:
    """
    PocketPay Conversational AI Engine (Phases 16, 17, 19).
    Context-aware financial intelligence supporting Web AI Assistant and Telegram NLP.
    Strictly enforces authorization guardrails: never directly executes financial transfers.
    """

    @classmethod
    def process_query(
        cls,
        user: Optional[User],
        query_text: str,
        route: str = 'dashboard',
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        q = (query_text or '').strip().lower()
        if not q:
            return cls._empty_response()

        # 1. Check for sensitive financial modification guardrails (Phase 17)
        guardrail_res = cls._check_guardrails(q, user)
        if guardrail_res:
            return guardrail_res

        # 2. Greetings & Salutations
        # 2. Greetings & Salutations
        if re.match(r'^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening)|namaste)\b', q):
            return cls._handle_greeting(user)

        # 3. Intent: PocketPay Wallet ID / UPI ID
        if any(w in q for w in ['wallet id', 'pocketpay id', 'my id', 'payment id', 'upi id', 'upi', 'virtual upi', 'vpa', 'scan qr', 'receive payment', 'my qr']):
            return cls._handle_wallet_id_inquiry(user)

        # 4. Intent: Phone / Mobile Verification
        if any(w in q for w in ['phone', 'mobile', 'verify phone', 'verify mobile', 'phone verification', 'mobile number', 'add phone', 'change phone']):
            return cls._handle_phone_verification_guide(user)

        # 5. Intent: Account Deletion
        if any(w in q for w in ['delete account', 'close account', 'delete my account', 'remove account', 'deactivate', 'permanent delete']):
            return cls._handle_account_deletion_guide(user)

        # 6. Intent: Password / Account Recovery
        if any(w in q for w in ['forgot password', 'reset password', 'change password', 'lost access', 'recover account']):
            return cls._handle_password_guide()

        # 7. Intent: Balance & Net Worth Inquiry
        if any(w in q for w in ['balance', 'how much money', 'net worth', 'total money', 'available funds', 'account balance', 'wallet balance']):
            return cls._handle_balance_inquiry(user)

        # 8. Intent: Pockets Inquiry & Highest Pocket
        if any(w in q for w in ['pocket', 'pockets', 'my pockets', 'list pockets', 'show pockets', 'which pocket', 'where is my money']):
            if 'most' in q or 'highest' in q or 'maximum' in q or 'largest' in q:
                return cls._handle_highest_pocket(user)
            elif 'least' in q or 'lowest' in q or 'empty' in q:
                return cls._handle_lowest_pocket(user)
            elif 'create' in q or 'make' in q or 'new' in q or 'add' in q:
                return cls._handle_create_pocket_guide()
            else:
                return cls._handle_pockets_overview(user)

        # 9. Intent: Spending & Monthly Expenses Analysis
        if any(w in q for w in ['spend', 'spent', 'expense', 'expenses', 'how much did i spend', 'cost', 'spending']):
            return cls._handle_spending_analysis(user, q)

        # 10. Intent: Recent Transactions & Activity
        if any(w in q for w in ['transaction', 'transactions', 'recent activity', 'last payment', 'latest transaction', 'history', 'statement']):
            return cls._handle_recent_transactions(user)

        # 11. Intent: Savings Goals & Targets
        if any(w in q for w in ['goal', 'goals', 'savings goal', 'target', 'targets', 'saving for']):
            return cls._handle_savings_goals(user)

        # 12. Intent: Budgeting & Alerts
        if any(w in q for w in ['budget', 'budgets', 'limit', 'limits', 'threshold']):
            return cls._handle_budgets(user)

        # 13. Intent: Security, 2FA, TOTP & PIN
        if any(w in q for w in ['totp', '2fa', 'authenticator', 'pin', 'security', 'two factor', 'otp']):
            return cls._handle_security_guide(user, q)

        # 14. Intent: Premium & Subscriptions
        if any(w in q for w in ['premium', 'pro', 'vip', 'subscription', 'plan', 'plans', 'upgrade']):
            return cls._handle_premium_info(user)

        # 15. Intent: Bank Transfer & UPI Sandbox
        if any(w in q for w in ['bank transfer', 'withdraw to bank', 'qr code', 'bank account', 'imps', 'neft']):
            return cls._handle_bank_transfer_guide(user)

        # 16. Intent: How-To Transfer / Send Money
        if any(w in q for w in ['transfer', 'send money', 'how to send', 'how to transfer', 'pay friend']):
            return cls._handle_transfer_guide()

        # 17. Graceful Domain-Aware Fallback with Suggested Actions
        return cls._handle_fallback(q, user, route)

    # =========================================================================
    # INTENT HANDLERS
    # =========================================================================

    @classmethod
    def _check_guardrails(cls, q: str, user: Optional[User]) -> Optional[Dict[str, Any]]:
        """Phase 17: Protects against unauthorized direct execution attempts while preparing transaction flow"""
        transfer_patterns = [
            r'(?:send|transfer|pay)\s+(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s+(?:to|for)\s+([a-zA-Z0-9_\s@\.]+)',
            r'(?:transfer|move)\s+(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s+(?:from|between)\s+([a-zA-Z0-9_\s]+)'
        ]

        for pat in transfer_patterns:
            m = re.search(pat, q)
            if m:
                amount_str = m.group(1)
                target = m.group(2).strip()
                return {
                    'type': 'transaction_prompt',
                    'title': '⚡ Transfer Preparation',
                    'message': (
                        f"I have prepared your transfer request for <b>₹{float(amount_str):,.2f}</b> to <b>{target}</b>.<br><br>"
                        f"🛡️ <i>For your financial safety, PocketPay requires you to review and confirm all transactions with your secure 4-digit PIN or Authenticator 2FA.</i>"
                    ),
                    'actions': [
                        {'label': f'Confirm ₹{amount_str} Transfer', 'icon': 'arrow-up-right', 'action': 'send_money', 'amount': amount_str, 'recipient': target},
                        {'label': 'Inter-Pocket Transfer', 'icon': 'refresh-ccw', 'action': 'transfer'}
                    ],
                    'suggested_prompts': ['What is my balance?', 'Show my pockets', 'How does PIN security work?']
                }

        # Block direct balance tampering or private credential requests
        forbidden_keywords = ['change my balance', 'give me money', 'set balance to', 'my password is', 'what is my password', 'what is my otp', 'show otp']
        if any(k in q for k in forbidden_keywords):
            return {
                'type': 'guardrail_notice',
                'title': '🛡️ Security Protected',
                'message': 'PocketPay AI Assistant cannot modify account balances or access private passwords/OTPs.',
                'actions': [
                    {'label': 'View My Balance', 'icon': 'wallet', 'action': 'balance'},
                    {'label': 'Security Settings', 'icon': 'shield-check', 'action': 'settings'}
                ],
                'suggested_prompts': ['What is my balance?', 'How do I change my PIN?']
            }

        return None

    @classmethod
    def _handle_greeting(cls, user: Optional[User]) -> Dict[str, Any]:
        name = user.full_name.split(' ')[0] if user and user.full_name else 'there'
        bal_text = f" Your current net worth is <b>₹{(user.wallet_balance or 0):,.2f}</b>." if user else ""
        return {
            'type': 'greeting',
            'title': f'👋 Hello {name}!',
            'message': f"Welcome to PocketPay!{bal_text} I'm your AI financial guide. Ask me about your balance, spending analysis, pockets, or how to use features.",
            'actions': [
                {'label': 'Check Balance', 'icon': 'wallet', 'action': 'balance'},
                {'label': 'Show My Pockets', 'icon': 'wallet-cards', 'action': 'pockets'},
                {'label': 'Monthly Spending', 'icon': 'pie-chart', 'action': 'spending'}
            ],
            'suggested_prompts': [
                'How much money do I have?',
                'Which pocket has the most money?',
                'What did I spend this month?',
                'Show my savings goals'
            ]
        }

    @classmethod
    def _handle_balance_inquiry(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        pockets = Pocket.query.filter_by(user_id=user.id, archived=False).all()
        pockets_total = sum(p.current_balance for p in pockets)
        wallet_bal = user.wallet_balance or 0.0
        total_assets = round(wallet_bal + pockets_total, 2)

        lines = [
            f"💰 <b>Total Net Worth:</b> ₹{total_assets:,.2f}",
            f"• <b>Available Balance:</b> ₹{wallet_bal:,.2f}",
            f"• <b>Allocated in Pockets ({len(pockets)}):</b> ₹{pockets_total:,.2f}"
        ]

        return {
            'type': 'financial_data',
            'title': '💵 Account Balances',
            'message': "<br>".join(lines),
            'actions': [
                {'label': 'View Pockets', 'icon': 'wallet-cards', 'action': 'pockets'},
                {'label': 'Add Income', 'icon': 'arrow-down-left', 'action': 'add_income'},
                {'label': 'Transfer Funds', 'icon': 'refresh-ccw', 'action': 'transfer'}
            ],
            'suggested_prompts': [
                'Which pocket has the most money?',
                'What did I spend this month?',
                'Show recent transactions'
            ]
        }

    @classmethod
    def _handle_pockets_overview(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        pockets = Pocket.query.filter_by(user_id=user.id, archived=False).order_by(Pocket.current_balance.desc()).all()
        if not pockets:
            return {
                'type': 'info',
                'title': 'Smart Pockets',
                'message': "You haven't created any custom pockets yet. Pockets let you separate money for rent, groceries, savings, and outings.",
                'actions': [{'label': 'Create First Pocket', 'icon': 'plus', 'action': 'create_pocket'}],
                'suggested_prompts': ['How do I create a pocket?', 'What is a smart split?']
            }

        top_pockets = pockets[:5]
        pocket_items = [f"• <b>{p.name}:</b> ₹{p.current_balance:,.2f}" for p in top_pockets]
        extra = f"<br><i>...and {len(pockets) - 5} more pockets</i>" if len(pockets) > 5 else ""

        return {
            'type': 'financial_data',
            'title': f'👛 Your Smart Pockets ({len(pockets)})',
            'message': f"Here is a summary of your active pockets:<br>" + "<br>".join(pocket_items) + extra,
            'actions': [
                {'label': 'Manage All Pockets', 'icon': 'wallet-cards', 'action': 'pockets'},
                {'label': '+ New Pocket', 'icon': 'plus', 'action': 'create_pocket'},
                {'label': 'Transfer Between Pockets', 'icon': 'refresh-ccw', 'action': 'transfer'}
            ],
            'suggested_prompts': [
                'Which pocket has the most money?',
                'How do I transfer between pockets?',
                'What is my total balance?'
            ]
        }

    @classmethod
    def _handle_highest_pocket(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        pockets = Pocket.query.filter_by(user_id=user.id, archived=False).order_by(Pocket.current_balance.desc()).all()
        if not pockets:
            return cls._handle_pockets_overview(user)

        top = pockets[0]
        return {
            'type': 'financial_data',
            'title': '🏆 Highest Balance Pocket',
            'message': f"Your <b>{top.name}</b> pocket currently has the highest balance at <b>₹{top.current_balance:,.2f}</b>.",
            'actions': [
                {'label': f'Open {top.name}', 'icon': 'folder', 'action': 'pocket_detail', 'pocket_id': top.id},
                {'label': 'View All Pockets', 'icon': 'wallet-cards', 'action': 'pockets'}
            ],
            'suggested_prompts': ['What did I spend this month?', 'Show my savings goals']
        }

    @classmethod
    def _handle_lowest_pocket(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        pockets = Pocket.query.filter_by(user_id=user.id, archived=False).order_by(Pocket.current_balance.asc()).all()
        if not pockets:
            return cls._handle_pockets_overview(user)

        low = pockets[0]
        return {
            'type': 'financial_data',
            'title': '⚠️ Lowest Balance Pocket',
            'message': f"Your lowest funded pocket is <b>{low.name}</b> with <b>₹{low.current_balance:,.2f}</b> remaining.",
            'actions': [
                {'label': f'Add Funds to {low.name}', 'icon': 'plus-circle', 'action': 'add_income'},
                {'label': 'Transfer Funds', 'icon': 'refresh-ccw', 'action': 'transfer'}
            ],
            'suggested_prompts': ['How do I transfer money between pockets?', 'What is my total balance?']
        }

    @classmethod
    def _handle_spending_analysis(cls, user: Optional[User], q: str) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        now = datetime.utcnow()
        month_start = datetime(now.year, now.month, 1)

        # Check for category-specific query
        category_match = None
        for cat in ['food', 'dining', 'shopping', 'entertainment', 'travel', 'rent', 'utilities', 'bills', 'groceries', 'investment']:
            if cat in q:
                category_match = cat
                break

        if category_match:
            cat_sum = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user.id,
                Transaction.type == 'expense',
                Transaction.created_at >= month_start,
                Transaction.category.ilike(f'%{category_match}%')
            ).scalar() or 0.0

            return {
                'type': 'financial_data',
                'title': f'📊 {category_match.capitalize()} Spending',
                'message': f"You have spent <b>₹{cat_sum:,.2f}</b> on <b>{category_match.capitalize()}</b> this month ({now.strftime('%B %Y')}).",
                'actions': [{'label': 'View Reports', 'icon': 'bar-chart-2', 'action': 'analytics'}],
                'suggested_prompts': ['What is my total spending this month?', 'Show my recent transactions']
            }

        total_expense = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user.id,
            Transaction.type == 'expense',
            Transaction.created_at >= month_start
        ).scalar() or 0.0

        total_income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user.id,
            Transaction.type.in_(['income', 'topup', 'refund']),
            Transaction.created_at >= month_start
        ).scalar() or 0.0

        net_savings = round(total_income - total_expense, 2)
        savings_rate = round((net_savings / total_income * 100) if total_income > 0 else 0, 1)

        msg = (
            f"📈 <b>Spending & Cash Flow for {now.strftime('%B %Y')}:</b><br>"
            f"• <b>Total Spent:</b> ₹{total_expense:,.2f}<br>"
            f"• <b>Total Income:</b> ₹{total_income:,.2f}<br>"
            f"• <b>Net Saved:</b> ₹{net_savings:,.2f} (Savings Rate: <b>{savings_rate}%</b>)"
        )

        return {
            'type': 'financial_data',
            'title': '📊 Monthly Spending Overview',
            'message': msg,
            'actions': [
                {'label': 'Open Analytics', 'icon': 'pie-chart', 'action': 'analytics'},
                {'label': 'Set Pocket Budget', 'icon': 'target', 'action': 'budgets'}
            ],
            'suggested_prompts': [
                'Which pocket has the most money?',
                'Show recent transactions',
                'Show my savings goals'
            ]
        }

    @classmethod
    def _handle_recent_transactions(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        txs = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).limit(4).all()
        if not txs:
            return {
                'type': 'info',
                'title': 'Recent Transactions',
                'message': "No transactions recorded yet. Make a transfer, add income, or record an expense to start your ledger.",
                'actions': [{'label': 'Add Income', 'icon': 'plus', 'action': 'add_income'}],
                'suggested_prompts': ['What is my balance?', 'How do I transfer money?']
            }

        lines = []
        for t in txs:
            prefix = '+' if t.type in ['income', 'topup', 'refund', 'peer_receive'] else '-'
            color = 'green' if prefix == '+' else 'var(--text)'
            lines.append(f"• <b>{t.description or t.type.capitalize()}</b>: <span style='color:{color}'>{prefix}₹{t.amount:,.2f}</span> ({t.status})")

        return {
            'type': 'financial_data',
            'title': '🧾 Recent Transactions',
            'message': "<br>".join(lines),
            'actions': [
                {'label': 'Full Transaction Ledger', 'icon': 'receipt', 'action': 'transactions'},
                {'label': 'Send Money', 'icon': 'arrow-up-right', 'action': 'send_money'}
            ],
            'suggested_prompts': [
                'What did I spend this month?',
                'What is my balance?',
                'Show my pockets'
            ]
        }

    @classmethod
    def _handle_savings_goals(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        goals = SavingsGoal.query.filter_by(user_id=user.id).all()
        if not goals:
            return {
                'type': 'info',
                'title': '🎯 Savings Goals',
                'message': "You don't have any savings goals yet. Set targets for items like a new laptop, emergency fund, or travel.",
                'actions': [{'label': '+ Create Savings Goal', 'icon': 'plus', 'action': 'create_goal'}],
                'suggested_prompts': ['How do savings goals work?', 'What is my balance?']
            }

        lines = [f"• <b>{g.name}:</b> ₹{g.current_amount:,.2f} / ₹{g.target_amount:,.2f} (<b>{g.get_progress_percentage()}%</b>)" for g in goals]
        return {
            'type': 'financial_data',
            'title': f'🎯 Your Savings Goals ({len(goals)})',
            'message': "<br>".join(lines),
            'actions': [
                {'label': '+ New Savings Goal', 'icon': 'plus', 'action': 'create_goal'},
                {'label': 'View Dashboard', 'icon': 'layout-dashboard', 'action': 'dashboard'}
            ],
            'suggested_prompts': [
                'What is my balance?',
                'Which pocket has the most money?'
            ]
        }

    @classmethod
    def _handle_budgets(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        budgets = Budget.query.filter_by(user_id=user.id, is_active=True).all()
        if not budgets:
            return {
                'type': 'info',
                'title': '🎯 Budgets & Spending Limits',
                'message': "You have not set any active budget thresholds. You can set monthly limits on pockets to receive automatic 75%, 90%, and 100% threshold alerts.",
                'actions': [{'label': 'Set a Budget', 'icon': 'plus', 'action': 'budgets'}],
                'suggested_prompts': ['Show my pockets', 'What did I spend this month?']
            }

        lines = [f"• <b>{b.name}:</b> Limit ₹{b.limit_amount:,.2f} ({b.get_percentage_used():.0f}% used)" for b in budgets]
        return {
            'type': 'financial_data',
            'title': f'🎯 Active Budgets ({len(budgets)})',
            'message': "<br>".join(lines),
            'actions': [{'label': 'Manage Budgets', 'icon': 'target', 'action': 'budgets'}],
            'suggested_prompts': ['What did I spend this month?', 'Show my pockets']
        }

    @classmethod
    def _handle_security_guide(cls, user: Optional[User], q: str) -> Dict[str, Any]:
        has_totp = user.totp_enabled if user else False
        has_pin = bool(user.transaction_pin_hash) if user else False

        msg = (
            "🔐 <b>PocketPay Multi-Layer Security:</b><br><br>"
            "1. <b>4-Digit Transaction PIN:</b> Protects every money transfer, payout, and pocket re-allocation.<br>"
            "2. <b>Authenticator 2FA (TOTP):</b> Hardware-backed time-based OTP via Google Authenticator or Microsoft Authenticator for high-value operations.<br>"
            "3. <b>Zero-Plaintext Storage:</b> Passwords and PINs are securely hashed using Argon2/PBKDF2.<br><br>"
            f"• <b>Your PIN Status:</b> {'✅ Configured' if has_pin else '⚠️ Not Set'}<br>"
            f"• <b>Your 2FA Status:</b> {'✅ Enabled' if has_totp else '⚪ Not Enabled'}"
        )

        return {
            'type': 'security_guide',
            'title': '🛡️ Account Security & TOTP',
            'message': msg,
            'actions': [
                {'label': 'Configure 2FA / TOTP', 'icon': 'shield-check', 'action': 'totp_setup'},
                {'label': 'Change Transaction PIN', 'icon': 'lock', 'action': 'change_pin'}
            ],
            'suggested_prompts': [
                'What is my balance?',
                'How do I transfer money?'
            ]
        }

    @classmethod
    def _handle_premium_info(cls, user: Optional[User]) -> Dict[str, Any]:
        is_prem = user.is_premium if user else False
        msg = (
            f"👑 <b>PocketPay Pro (Demo Tier):</b><br><br>"
            f"• <b>Your Tier:</b> {'✨ Premium Member' if is_prem else 'Standard Free'}<br>"
            f"• <b>Features:</b> Unlimited smart pockets, unlimited savings targets, pro AI assistant, interactive category charts, custom themes, and CSV export.<br><br>"
            f"<i>Note: You can activate PocketPay Pro completely free in this portfolio demonstration.</i>"
        )
        return {
            'type': 'premium_info',
            'title': '👑 PocketPay Premium',
            'message': msg,
            'actions': [
                {'label': 'View Premium Plans', 'icon': 'sparkles', 'action': 'view_premium'}
            ],
            'suggested_prompts': [
                'What is my balance?',
                'Show my pockets',
                'What did I spend this month?'
            ]
        }

    @classmethod
    def _handle_bank_transfer_guide(cls, user: Optional[User]) -> Dict[str, Any]:
        return {
            'type': 'guidance',
            'title': '🏦 Bank Transfer Sandbox',
            'message': (
                "PocketPay includes a realistic <b>Bank Transfer & UPI Sandbox</b> simulation:<br><br>"
                "• <b>Send to Bank:</b> Transfer funds to any registered bank account with instant IMPS/NEFT reference generation.<br>"
                "• <b>Virtual UPI & QR:</b> Every user receives a personal UPI ID (e.g. <code>username@pocketpay</code>) and scannable QR code.<br>"
                "• <b>Receipts:</b> Every transaction generates an official downloadable receipt with UTR and timestamp."
            ),
            'actions': [
                {'label': 'Open Bank Transfer', 'icon': 'landmark', 'action': 'bank_transfer'},
                {'label': 'My Wallet & QR', 'icon': 'qr-code', 'action': 'wallet'}
            ],
            'suggested_prompts': [
                'How do I send money?',
                'What is my balance?'
            ]
        }

    @classmethod
    def _handle_create_pocket_guide(cls) -> Dict[str, Any]:
        return {
            'type': 'how_to',
            'title': '➕ Creating a Smart Pocket',
            'message': (
                "To create a new pocket:<br>"
                "1. Click <b>Create Pocket</b> or go to the Pockets organizer.<br>"
                "2. Choose a name (e.g. 'Vacation Fund', 'Dining').<br>"
                "3. Select a color swatch and icon.<br>"
                "4. Optionally set a monthly spending budget or target limit."
            ),
            'actions': [{'label': 'Create Pocket Now', 'icon': 'plus', 'action': 'create_pocket'}],
            'suggested_prompts': ['How do I transfer between pockets?', 'What is my balance?']
        }

    @classmethod
    def _handle_transfer_guide(cls) -> Dict[str, Any]:
        return {
            'type': 'how_to',
            'title': '🔄 Money Transfers',
            'message': (
                "You can transfer funds in two ways:<br>"
                "1. <b>Between Your Pockets:</b> Reallocate funds instantly from one pocket to another using your PIN.<br>"
                "2. <b>P2P / Send Money:</b> Send funds to any PocketPay user by email or UPI ID."
            ),
            'actions': [
                {'label': 'Transfer Between Pockets', 'icon': 'refresh-ccw', 'action': 'transfer'},
                {'label': 'Send to Peer / Friend', 'icon': 'arrow-up-right', 'action': 'send_money'}
            ],
            'suggested_prompts': ['What is my balance?', 'Show my pockets']
        }

    @classmethod
    def _handle_fallback(cls, q: str, user: Optional[User], route: str) -> Dict[str, Any]:
        name = user.full_name.split(' ')[0] if user and user.full_name else ''
        return {
            'type': 'fallback',
            'title': '💡 How can I assist you?',
            'message': (
                f"I understood you asked about: <i>\"{q}\"</i>.<br><br>"
                "Here are key questions you can ask me anytime:<br>"
                "• <b>\"What is my balance?\"</b> — Live wallet and pocket net worth<br>"
                "• <b>\"Show my pockets\"</b> — Breakdown of all smart pockets<br>"
                "• <b>\"What did I spend this month?\"</b> — Monthly expenses and savings rate<br>"
                "• <b>\"Show my recent transactions\"</b> — Latest income and expenses<br>"
                "• <b>\"How does TOTP work?\"</b> — 2FA and transaction PIN security guide"
            ),
            'actions': [
                {'label': 'Check Balance', 'icon': 'wallet', 'action': 'balance'},
                {'label': 'View Pockets', 'icon': 'wallet-cards', 'action': 'pockets'},
                {'label': 'View Reports', 'icon': 'bar-chart-2', 'action': 'analytics'}
            ],
            'suggested_prompts': [
                'What is my balance?',
                'Show my pockets',
                'What did I spend this month?',
                'Which pocket has the most money?'
            ]
        }

    @classmethod
    def _auth_required_response(cls) -> Dict[str, Any]:
        return {
            'type': 'auth_required',
            'title': '🔒 Authentication Required',
            'message': 'Please log in to your PocketPay account to view personalized balances, pockets, and transaction reports.',
            'actions': [{'label': 'Log In', 'icon': 'log-in', 'action': 'login'}],
            'suggested_prompts': ['How does PocketPay work?', 'What is Premium?']
        }

    @classmethod
    def _empty_response(cls) -> Dict[str, Any]:
        return {
            'type': 'empty',
            'title': 'AI Financial Assistant',
            'message': 'Ask me anything about your PocketPay balances, spending, smart pockets, or security settings.',
            'actions': [],
            'suggested_prompts': ['What is my balance?', 'Show my pockets', 'What did I spend this month?']
        }

    @classmethod
    def _handle_wallet_id_inquiry(cls, user: Optional[User]) -> Dict[str, Any]:
        """Returns the user's own PocketPay Wallet ID and Virtual UPI ID."""
        if not user:
            return cls._auth_required_response()
        wallet_id = user.virtual_wallet_id or '(not yet assigned — visit Wallet page)'
        upi_id = user.virtual_upi_id or '(not yet assigned — visit Wallet page)'
        return {
            'type': 'wallet_id',
            'title': '🆔 Your PocketPay Identity',
            'message': (
                f'Here are your unique PocketPay identifiers:<br><br>'
                f'<b>Wallet ID:</b> <code>{wallet_id}</code><br>'
                f'<b>Virtual UPI ID:</b> <code>{upi_id}</code><br><br>'
                f'Share your <b>Wallet ID</b> or <b>UPI ID</b> with anyone to receive instant payments. '
                f'You can also show your QR code from the Wallet page for contactless payment.'
            ),
            'actions': [
                {'label': 'Open Wallet Page', 'icon': 'wallet', 'action': 'wallet'},
                {'label': 'Show QR Code', 'icon': 'qr-code', 'action': 'wallet'},
            ],
            'suggested_prompts': ['How do I receive money?', 'What is my balance?', 'How does UPI work?']
        }

    @classmethod
    def _handle_phone_verification_guide(cls, user: Optional[User]) -> Dict[str, Any]:
        """Guides user through phone number verification."""
        if not user:
            return cls._auth_required_response()
        if user.phone_verified:
            msg = (
                f'✅ Your mobile number <b>{user.phone}</b> is already verified!<br><br>'
                f'Phone verification adds an extra layer of trust to your PocketPay account and enables SMS notifications.'
            )
        else:
            phone_hint = f'<br><br>Your current number on file: <b>{user.phone}</b>.' if user.phone else ''
            msg = (
                f'📱 To verify your mobile number:{phone_hint}<br><br>'
                f'<ol><li>Go to <b>Wallet → Virtual Identifiers</b></li>'
                f'<li>Tap <b>Verify</b> next to "Mobile Number"</li>'
                f'<li>Enter or confirm your phone number</li>'
                f'<li>Tap <b>Send Verification OTP</b></li>'
                f'<li>Your 6-digit code appears <b>right here in the app</b></li>'
                f'<li>Tap the code to auto-fill it, then tap <b>Verify Phone</b></li></ol>'
            )
        return {
            'type': 'phone_verification',
            'title': '📱 Mobile Number Verification',
            'message': msg,
            'actions': [{'label': 'Go to Wallet', 'icon': 'smartphone', 'action': 'wallet'}],
            'suggested_prompts': ['What is my UPI ID?', 'How do I enable 2FA?', 'Show my balance']
        }

    @classmethod
    def _handle_account_deletion_guide(cls, user: Optional[User]) -> Dict[str, Any]:
        """Explains account deletion — never executes it directly."""
        return {
            'type': 'account_deletion_info',
            'title': '⚠️ Account Deletion',
            'message': (
                '<b>Important:</b> Account deletion is permanent and cannot be undone.<br><br>'
                'Before you can delete your account:<br>'
                '<ul>'
                '<li>Your wallet balance must be <b>₹0.00</b></li>'
                '<li>All pockets must be <b>empty</b></li>'
                '<li>You must enter your <b>account password</b> to confirm</li>'
                '<li>You must type <code>DELETE</code> as final confirmation</li>'
                '</ul>'
                'After deletion, your email and phone number become free for re-registration as a new account.<br><br>'
                '🛡️ <i>The AI assistant cannot delete your account. This action must be completed manually through Security Settings.</i>'
            ),
            'actions': [
                {'label': 'Security Settings', 'icon': 'alert-triangle', 'action': 'wallet'},
            ],
            'suggested_prompts': ['How do I withdraw money?', 'How do I empty my pockets?', 'What is my balance?']
        }

    @classmethod
    def _handle_password_guide(cls) -> Dict[str, Any]:
        """Guides user through password reset/change — never reveals passwords."""
        return {
            'type': 'password_guide',
            'title': '🔑 Password Help',
            'message': (
                '<b>Change Password:</b><br>'
                'Go to <b>Wallet → Security Settings → Change Password</b> and enter your current and new password.<br><br>'
                '<b>Forgot Password?</b><br>'
                '<ol><li>On the Login screen, tap <b>Forgot Password</b></li>'
                '<li>Enter your registered email address</li>'
                '<li>Check your email for a 6-digit reset code</li>'
                '<li>Enter the code and set your new password</li></ol>'
                '🛡️ <i>PocketPay never stores or displays your password. The AI assistant cannot see or reveal it.</i>'
            ),
            'actions': [
                {'label': 'Security Settings', 'icon': 'key-round', 'action': 'wallet'},
            ],
            'suggested_prompts': ['How do I enable 2FA?', 'How do I change my PIN?', 'Show my balance']
        }

