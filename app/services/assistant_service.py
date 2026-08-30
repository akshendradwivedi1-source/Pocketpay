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
from app.utils.email_service import SUPPORT_CONTACT_EMAILS, SUPPORT_HELPLINES


class AssistantService:
    """
    PocketPay Hard-Coded Conversational Assistant Engine.
    100% local, rule-based, deterministic intent matching system.
    Zero external AI / LLM APIs (No OpenAI, Gemini, Claude, Groq, OpenRouter).
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

        # Check for local conversational follow-up context (e.g. "what about my transactions?", "show them")
        resolved_q = cls._resolve_context(q, chat_history)

        # 1. Check for sensitive financial modification guardrails
        guardrail_res = cls._check_guardrails(resolved_q, user)
        if guardrail_res:
            return guardrail_res

        # 2. Support, Helplines & Complaints (Prioritized)
        if any(w in resolved_q for w in [
            'support', 'helpline', 'help line', 'customer care', 'customer support',
            'complaint', 'problem', 'issue', 'contact', 'ticket', 'contact pocketpay',
            'give me the helpline number', 'helpline number', 'support number',
            'customer care number', 'support email', 'give me support email',
            'call pocketpay', 'reach support', 'representative', 'agent', 'toll free', 'call'
        ]):
            return cls._handle_support_guide(user)

        # 3. Greetings & Salutations
        if re.match(r'^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening)|namaste|hola|yo)\b', resolved_q):
            return cls._handle_greeting(user)

        # 4. Politeness & Pleasantries (Thanks / Goodbye)
        if any(w in resolved_q for w in ['thanks', 'thank you', 'thx', 'ty', 'appreciate it', 'great thanks']):
            return cls._handle_thanks()
        if any(w in resolved_q for w in ['bye', 'goodbye', 'see you', 'cya', 'exit', 'quit']):
            return cls._handle_goodbye()

        # 5. Help & Capabilities
        if any(w in resolved_q for w in ['help', 'what can you do', 'how can you help', 'capabilities', 'commands', 'menu', 'features']):
            return cls._handle_help_menu(user)

        # 6. Intent: Account & Profile
        if any(w in resolved_q for w in ['my account', 'profile', 'account details', 'account settings', 'my info', 'user details', 'who am i']):
            return cls._handle_account_info(user)

        # 7. Intent: PocketPay Wallet ID & UPI ID
        if any(w in resolved_q for w in [
            'wallet id', 'pocketpay id', 'my id', 'payment id', 'upi id', 'my upi',
            'virtual upi', 'vpa', 'receive payment', 'my qr', 'show my id', 'my payment id'
        ]):
            return cls._handle_wallet_id_inquiry(user)

        # 8. Intent: Phone / Mobile Verification
        if any(w in resolved_q for w in ['phone', 'mobile', 'verify phone', 'verify mobile', 'phone verification', 'mobile number', 'add phone', 'change phone']):
            return cls._handle_phone_verification_guide(user)

        # 9. Intent: Account Deletion
        if any(w in resolved_q for w in ['delete account', 'close account', 'delete my account', 'remove account', 'deactivate', 'permanent delete']):
            return cls._handle_account_deletion_guide(user)

        # 10. Intent: Password & Recovery
        if any(w in resolved_q for w in ['forgot password', 'reset password', 'change password', 'lost access', 'recover account', 'password']):
            return cls._handle_password_guide()

        # 11. Intent: Balance & Net Worth Inquiry
        if any(w in resolved_q for w in [
            'balance', 'how much money', 'net worth', 'total money',
            'available funds', 'account balance', 'wallet balance', 'my balance', 'show my balance', 'how much do i have'
        ]):
            return cls._handle_balance_inquiry(user)

        # 12. Intent: Add Money / Deposit Funds
        if any(w in resolved_q for w in ['add money', 'add funds', 'deposit', 'fund wallet', 'top up', 'topup', 'recharge', 'load money']):
            return cls._handle_add_money_guide(user)

        # 13. Intent: QR Codes & Scanner
        if any(w in resolved_q for w in ['scan qr', 'qr code', 'qr payment', 'create qr', 'my qr code', 'show qr', 'qr']):
            return cls._handle_qr_guide(user)

        # 14. Intent: UPI Payments & Verification
        if any(w in resolved_q for w in ['verify upi', 'upi verification', 'upi payment', 'upi transfer', 'upi setup', 'upi']):
            return cls._handle_upi_guide(user)

        # 15. Intent: Wallet Verification (is this ID valid?)
        if any(w in resolved_q for w in ['verify wallet', 'verify pocketpay id', 'wallet verification', 'is this pocketpay id valid', 'check wallet id', 'validate wallet']):
            return cls._handle_wallet_verification_guide()

        # 16. Intent: Pockets Inquiry & Highest/Lowest Pocket
        if any(w in resolved_q for w in ['pocket', 'pockets', 'my pockets', 'list pockets', 'show pockets', 'which pocket', 'where is my money', 'manage pockets', 'what is a pocket']):
            if 'most' in resolved_q or 'highest' in resolved_q or 'maximum' in resolved_q or 'largest' in resolved_q:
                return cls._handle_highest_pocket(user)
            elif 'least' in resolved_q or 'lowest' in resolved_q or 'empty' in resolved_q:
                return cls._handle_lowest_pocket(user)
            elif 'create' in resolved_q or 'make' in resolved_q or 'new' in resolved_q or 'add' in resolved_q:
                return cls._handle_create_pocket_guide()
            else:
                return cls._handle_pockets_overview(user)

        # 17. Intent: Spending & Monthly Expenses Analysis
        if any(w in resolved_q for w in ['spend', 'spent', 'expense', 'expenses', 'how much did i spend', 'cost', 'spending']):
            return cls._handle_spending_analysis(user, resolved_q)

        # 18. Intent: Recent Transactions & Activity
        if any(w in resolved_q for w in ['transaction', 'transactions', 'recent activity', 'last payment', 'latest transaction', 'history', 'statement', 'recent payments', 'payment history']):
            return cls._handle_recent_transactions(user)

        # 19. Intent: Savings Goals & Targets
        if any(w in resolved_q for w in ['goal', 'goals', 'savings goal', 'target', 'targets', 'saving for']):
            return cls._handle_savings_goals(user)

        # 20. Intent: Budgeting & Alerts
        if any(w in resolved_q for w in ['budget', 'budgets', 'limit', 'limits', 'threshold']):
            return cls._handle_budgets(user)

        # 21. Intent: Security, 2FA, TOTP & PIN
        if any(w in resolved_q for w in ['totp', '2fa', 'authenticator', 'pin', 'security', 'two factor', 'otp']):
            return cls._handle_security_guide(user, resolved_q)

        # 22. Intent: Premium & Subscriptions
        if any(w in resolved_q for w in ['premium', 'pro', 'vip', 'subscription', 'plan', 'plans', 'upgrade']):
            return cls._handle_premium_info(user)

        # 23. Intent: Bank Transfer & Net Banking
        if any(w in resolved_q for w in ['bank transfer', 'withdraw to bank', 'bank account', 'imps', 'neft', 'rtgs', 'withdraw']):
            return cls._handle_bank_transfer_guide(user)

        # 24. Intent: How-To Transfer / Send Money
        if any(w in resolved_q for w in ['transfer', 'send money', 'how to send', 'how to transfer', 'pay someone', 'make payment', 'payment help', 'pay friend']):
            return cls._handle_transfer_guide()

        # 25. Deterministic Domain-Aware Fallback (Predefined template, zero AI)
        return cls._handle_fallback(resolved_q, user, route)

    # =========================================================================
    # CONVERSATIONAL CONTEXT RESOLUTION (LOCAL ONLY)
    # =========================================================================

    @classmethod
    def _resolve_context(cls, q: str, history: Optional[List[Dict[str, str]]]) -> str:
        """Resolves basic conversational follow-up references using recent chat context"""
        if not history:
            return q

        last_user_msg = ''
        for msg in reversed(history):
            if msg.get('sender') == 'user':
                last_user_msg = (msg.get('text') or '').lower()
                break

        # Context: "what about my transactions?" / "show them" / "recent ones"
        if q in ['what about transactions', 'what about my transactions', 'show them', 'show recent ones', 'transactions then', 'and transactions']:
            return 'recent transactions'
        if q in ['what about balance', 'what about my balance', 'and balance', 'balance then']:
            return 'wallet balance'
        if q in ['what about pockets', 'what about my pockets', 'show my pockets', 'pockets then']:
            return 'show pockets'
        if q in ['last transaction', 'my last transaction', 'latest one']:
            return 'recent transactions'

        return q

    # =========================================================================
    # INTENT HANDLERS (ALL PREDEFINED TEMPLATES)
    # =========================================================================

    @classmethod
    def _check_guardrails(cls, q: str, user: Optional[User]) -> Optional[Dict[str, Any]]:
        """Protects against direct execution attempts while preparing transaction flow"""
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
                        f"I can help you start a payment of <b>₹{float(amount_str):,.2f}</b> to <b>{target}</b>.<br><br>"
                        f"🛡️ <i>For your financial safety, PocketPay requires you to verify the recipient and confirm the transfer using your secure 4-digit PIN or Authenticator 2FA on the Send Money screen.</i>"
                    ),
                    'actions': [
                        {'label': f'Open Send Money (₹{amount_str})', 'icon': 'arrow-up-right', 'action': 'send_money', 'amount': amount_str, 'recipient': target},
                        {'label': 'Pocket Transfer', 'icon': 'refresh-ccw', 'action': 'transfer'}
                    ],
                    'suggested_prompts': ['What is my balance?', 'Show my pockets', 'How does PIN security work?']
                }

        # Block direct balance tampering or private credential requests
        forbidden_keywords = ['change my balance', 'give me money', 'set balance to', 'my password is', 'what is my password', 'what is my otp', 'show otp', 'show pin', 'what is my pin']
        if any(k in q for k in forbidden_keywords):
            return {
                'type': 'guardrail_notice',
                'title': '🛡️ Security Protected',
                'message': 'PocketPay Assistant cannot modify balances or access private passwords, PINs, or OTPs.',
                'actions': [
                    {'label': 'View My Balance', 'icon': 'wallet', 'action': 'balance'},
                    {'label': 'Security Settings', 'icon': 'shield-check', 'action': 'settings'}
                ],
                'suggested_prompts': ['What is my balance?', 'How do I change my PIN?']
            }

        return None

    @classmethod
    def _handle_support_guide(cls, user: Optional[User]) -> Dict[str, Any]:
        """Returns the official hard-coded PocketPay helplines, support emails, and ticket action."""
        lines = [
            "<b>PocketPay Official Customer Support</b><br><br>",
            "📞 <b>Helpline Numbers:</b><br>",
            "• +91 85278 70864<br>",
            "• 8010906123<br>",
            "• +91 92679 32341<br><br>",
            "📧 <b>Support Emails:</b><br>",
            "• agarwal.anirudh2006@gmail.com<br>",
            "• akshendra.dwivedi1@gmail.com<br>",
            "• ankitlawaniya2005@gmail.com<br><br>",
            "🛡️ <i>PocketPay Support will never ask for your password, OTP or UPI PIN.</i><br><br>",
            "You can also submit an official support ticket directly through PocketPay for fast resolution."
        ]
        return {
            'type': 'support_info',
            'title': '🆘 PocketPay Support & Help Desk',
            'message': "".join(lines),
            'actions': [
                {'label': 'Submit Support Request', 'icon': 'headphones', 'action': 'support_modal'},
                {'label': 'Security Settings', 'icon': 'shield-check', 'action': 'settings'}
            ],
            'suggested_prompts': [
                'How to report a failed transaction?',
                'What is my PocketPay ID?',
                'How do I change my PIN?'
            ]
        }

    @classmethod
    def _handle_greeting(cls, user: Optional[User]) -> Dict[str, Any]:
        name = user.full_name.split(' ')[0] if user and user.full_name else 'there'
        bal_text = f" Your current net worth is <b>₹{(user.wallet_balance or 0):,.2f}</b>." if user else ""
        return {
            'type': 'greeting',
            'title': f'👋 Hello {name}!',
            'message': f"Welcome to PocketPay!{bal_text} I'm your hard-coded financial guide. Ask me about your balance, smart pockets, recent payments, or official support.",
            'actions': [
                {'label': 'Check Balance', 'icon': 'wallet', 'action': 'balance'},
                {'label': 'Show My Pockets', 'icon': 'wallet-cards', 'action': 'pockets'},
                {'label': 'Customer Support', 'icon': 'headphones', 'action': 'support_modal'}
            ],
            'suggested_prompts': [
                'What is my balance?',
                'Show my PocketPay ID',
                'What did I spend this month?',
                'Give me the helpline number'
            ]
        }

    @classmethod
    def _handle_thanks(cls) -> Dict[str, Any]:
        return {
            'type': 'polite',
            'title': '😊 You are welcome!',
            'message': 'Happy to help! Let me know if you need anything else regarding your PocketPay account or smart pockets.',
            'actions': [
                {'label': 'Check Balance', 'icon': 'wallet', 'action': 'balance'},
                {'label': 'View Pockets', 'icon': 'wallet-cards', 'action': 'pockets'}
            ],
            'suggested_prompts': ['What is my balance?', 'Show my transactions']
        }

    @classmethod
    def _handle_goodbye(cls) -> Dict[str, Any]:
        return {
            'type': 'polite',
            'title': '👋 Goodbye!',
            'message': 'Have a great day ahead! Remember to organize every rupee across your smart pockets.',
            'actions': [
                {'label': 'Dashboard', 'icon': 'layout-dashboard', 'action': 'dashboard'}
            ],
            'suggested_prompts': ['What is my balance?']
        }

    @classmethod
    def _handle_help_menu(cls, user: Optional[User]) -> Dict[str, Any]:
        return {
            'type': 'help_menu',
            'title': '💡 PocketPay Assistant Capabilities',
            'message': (
                "Here is everything I can help you with:<br><br>"
                "• <b>Balance & Net Worth:</b> Ask <i>\"What is my balance?\"</i><br>"
                "• <b>PocketPay ID:</b> Ask <i>\"What is my PocketPay ID?\"</i><br>"
                "• <b>Transactions:</b> Ask <i>\"Show recent transactions\"</i><br>"
                "• <b>Smart Pockets:</b> Ask <i>\"Show my pockets\"</i> or <i>\"How to create a pocket?\"</i><br>"
                "• <b>Payments & Transfers:</b> Ask <i>\"How to send money?\"</i> or <i>\"How to add money?\"</i><br>"
                "• <b>UPI & QR:</b> Ask <i>\"What is my UPI ID?\"</i> or <i>\"How to scan QR?\"</i><br>"
                "• <b>Security & 2FA:</b> Ask <i>\"How to enable 2FA?\"</i> or <i>\"How to change PIN?\"</i><br>"
                "• <b>Official Support:</b> Ask <i>\"Give me the helpline number\"</i> or submit a ticket."
            ),
            'actions': [
                {'label': 'View Balance', 'icon': 'wallet', 'action': 'balance'},
                {'label': 'Manage Pockets', 'icon': 'wallet-cards', 'action': 'pockets'},
                {'label': 'Contact Support', 'icon': 'headphones', 'action': 'support_modal'}
            ],
            'suggested_prompts': [
                'What is my balance?',
                'Show my PocketPay ID',
                'Give me the helpline number'
            ]
        }

    @classmethod
    def _handle_account_info(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()
        
        status_badges = []
        if user.email_verified: status_badges.append("Email Verified ✓")
        if user.phone_verified: status_badges.append("Phone Verified ✓")
        if user.totp_enabled: status_badges.append("2FA Active 🛡️")
        if user.is_premium: status_badges.append("Premium Member ⭐")

        badges_str = " • ".join(status_badges) if status_badges else "Active"

        return {
            'type': 'account_info',
            'title': '👤 Your PocketPay Profile',
            'message': (
                f"<b>Name:</b> {user.full_name}<br>"
                f"<b>Email:</b> {user.email}<br>"
                f"<b>Phone:</b> {user.phone or 'Not set'}<br>"
                f"<b>Wallet ID:</b> <code>{user.virtual_wallet_id or 'Auto-assigned on wallet visit'}</code><br>"
                f"<b>Virtual UPI ID:</b> <code>{user.virtual_upi_id or 'Auto-assigned'}</code><br>"
                f"<b>Account Status:</b> {badges_str}"
            ),
            'actions': [
                {'label': 'Account Settings', 'icon': 'settings', 'action': 'wallet'},
                {'label': 'Security Settings', 'icon': 'shield-check', 'action': 'settings'}
            ],
            'suggested_prompts': ['What is my balance?', 'How do I change my password?', 'Give me the helpline number']
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
    def _handle_add_money_guide(cls, user: Optional[User]) -> Dict[str, Any]:
        return {
            'type': 'add_money_guide',
            'title': '💳 Adding Funds to PocketPay',
            'message': (
                "To add funds to your account:<br><br>"
                "<ol><li>Go to <b>Dashboard → Add Income</b> or <b>Wallet → Top Up</b></li>"
                "<li>Enter the amount you wish to deposit</li>"
                "<li>Select your deposit method (Instant Top-up, UPI, or Bank Transfer)</li>"
                "<li>Choose how to distribute funds across your smart pockets or keep in available balance</li></ol>"
            ),
            'actions': [
                {'label': 'Add Income Now', 'icon': 'arrow-down-left', 'action': 'add_income'},
                {'label': 'Top Up Wallet', 'icon': 'wallet', 'action': 'wallet'}
            ],
            'suggested_prompts': ['What is my balance?', 'How do pockets work?']
        }

    @classmethod
    def _handle_qr_guide(cls, user: Optional[User]) -> Dict[str, Any]:
        return {
            'type': 'qr_guide',
            'title': '📱 QR Code & Contactless Payments',
            'message': (
                "PocketPay provides instant QR capabilities:<br><br>"
                "• <b>Receive Payments:</b> Open your Wallet or any Pocket to show your unique receiving QR code.<br>"
                "• <b>Scan & Pay:</b> Tap <b>Scan & Pay</b> in the top navigation or Wallet page to scan any UPI or PocketPay QR code.<br>"
                "• <b>Receipt QR:</b> Every transaction generates a verifiable digital receipt QR."
            ),
            'actions': [
                {'label': 'Scan & Pay', 'icon': 'qr-code', 'action': 'wallet'},
                {'label': 'View My QR Code', 'icon': 'user', 'action': 'wallet'}
            ],
            'suggested_prompts': ['What is my UPI ID?', 'How to send money?']
        }

    @classmethod
    def _handle_upi_guide(cls, user: Optional[User]) -> Dict[str, Any]:
        upi_id = user.virtual_upi_id if user and user.virtual_upi_id else "username@pocketpay"
        return {
            'type': 'upi_guide',
            'title': '⚡ UPI Payments on PocketPay',
            'message': (
                f"Your registered virtual UPI ID is: <code>{upi_id}</code><br><br>"
                "• <b>Send to UPI:</b> Enter any recipient VPA (e.g. <code>friend@okhdfcbank</code>) in Send Money.<br>"
                "• <b>Custom UPI ID:</b> Update your personal UPI ID in <b>Wallet → Virtual Identifiers</b>.<br>"
                "• <b>Verification:</b> Every UPI ID is verified on NPCI standards before payment confirmation."
            ),
            'actions': [
                {'label': 'Send via UPI', 'icon': 'send', 'action': 'send_money'},
                {'label': 'Manage UPI ID', 'icon': 'scan-line', 'action': 'wallet'}
            ],
            'suggested_prompts': ['What is my PocketPay ID?', 'How do I verify a wallet?']
        }

    @classmethod
    def _handle_wallet_verification_guide(cls) -> Dict[str, Any]:
        return {
            'type': 'wallet_verification_guide',
            'title': '🛡️ PocketPay Wallet ID Verification',
            'message': (
                "When sending money, PocketPay verifies recipient IDs in real time:<br><br>"
                "1. Open <b>Send Money</b> and enter the recipient's Wallet ID (e.g. <code>PPW...</code>) or Virtual UPI ID.<br>"
                "2. Our server verifies the account exists and is active.<br>"
                "3. A verified green card displays the recipient's registered name before you confirm with your PIN."
            ),
            'actions': [
                {'label': 'Open Send Money', 'icon': 'arrow-up-right', 'action': 'send_money'}
            ],
            'suggested_prompts': ['What is my PocketPay ID?', 'What is my balance?']
        }

    @classmethod
    def _handle_pockets_overview(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        pockets = Pocket.query.filter_by(user_id=user.id, archived=False).order_by(Pocket.current_balance.desc()).all()
        if not pockets:
            return {
                'type': 'info',
                'title': '📂 Smart Pockets',
                'message': "You don't have any active pockets yet. Create your first pocket (e.g., 'Groceries', 'Rent', 'Savings') to start organizing your money!",
                'actions': [{'label': 'Create First Pocket', 'icon': 'folder-plus', 'action': 'create_pocket'}],
                'suggested_prompts': ['How to create a pocket?']
            }

        items = [f"• <b>{p.name}:</b> ₹{p.current_balance:,.2f}" for p in pockets]
        return {
            'type': 'pockets_list',
            'title': f'📂 Your Pockets ({len(pockets)})',
            'message': "<br>".join(items),
            'actions': [
                {'label': 'View All Pockets', 'icon': 'wallet-cards', 'action': 'pockets'},
                {'label': 'Create New Pocket', 'icon': 'folder-plus', 'action': 'create_pocket'},
                {'label': 'Transfer Between Pockets', 'icon': 'refresh-ccw', 'action': 'transfer'}
            ],
            'suggested_prompts': [
                'Which pocket has the most money?',
                'How to transfer between pockets?',
                'What did I spend this month?'
            ]
        }

    @classmethod
    def _handle_highest_pocket(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        pocket = Pocket.query.filter_by(user_id=user.id, archived=False).order_by(Pocket.current_balance.desc()).first()
        if not pocket:
            return cls._handle_pockets_overview(user)

        return {
            'type': 'financial_insight',
            'title': '🏆 Highest Balance Pocket',
            'message': f"Your <b>{pocket.name}</b> pocket currently holds the most funds with <b>₹{pocket.current_balance:,.2f}</b>.",
            'actions': [
                {'label': f'Open {pocket.name}', 'icon': 'wallet-cards', 'action': 'pockets'},
                {'label': 'Inter-Pocket Transfer', 'icon': 'refresh-ccw', 'action': 'transfer'}
            ],
            'suggested_prompts': ['Which pocket has the least money?', 'Show all pockets']
        }

    @classmethod
    def _handle_lowest_pocket(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        pocket = Pocket.query.filter_by(user_id=user.id, archived=False).order_by(Pocket.current_balance.asc()).first()
        if not pocket:
            return cls._handle_pockets_overview(user)

        return {
            'type': 'financial_insight',
            'title': '📉 Lowest Balance Pocket',
            'message': f"Your <b>{pocket.name}</b> pocket currently has the lowest balance at <b>₹{pocket.current_balance:,.2f}</b>.",
            'actions': [
                {'label': 'Deposit Funds', 'icon': 'plus-circle', 'action': 'add_income'},
                {'label': 'View All Pockets', 'icon': 'wallet-cards', 'action': 'pockets'}
            ],
            'suggested_prompts': ['Show all pockets', 'What is my balance?']
        }

    @classmethod
    def _handle_spending_analysis(cls, user: Optional[User], q: str) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        now = datetime.utcnow()
        start_of_month = datetime(now.year, now.month, 1)

        total_expense = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user.id,
            Transaction.type == 'expense',
            Transaction.created_at >= start_of_month
        ).scalar() or 0.0

        total_income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user.id,
            Transaction.type.in_(['income', 'topup']),
            Transaction.created_at >= start_of_month
        ).scalar() or 0.0

        savings_rate = round(((total_income - total_expense) / total_income * 100) if total_income > 0 else 0, 1)

        msg = (
            f"📊 <b>Monthly Financial Overview ({now.strftime('%B %Y')}):</b><br>"
            f"• <b>Total Spent:</b> ₹{total_expense:,.2f}<br>"
            f"• <b>Total Income Received:</b> ₹{total_income:,.2f}<br>"
            f"• <b>Net Savings:</b> ₹{(total_income - total_expense):,.2f}<br>"
            f"• <b>Savings Rate:</b> {savings_rate}%"
        )

        return {
            'type': 'spending_report',
            'title': '📊 Spending & Savings Analytics',
            'message': msg,
            'actions': [
                {'label': 'Detailed Analytics', 'icon': 'pie-chart', 'action': 'analytics'},
                {'label': 'Transactions History', 'icon': 'list', 'action': 'transactions'}
            ],
            'suggested_prompts': ['Show recent transactions', 'What is my balance?']
        }

    @classmethod
    def _handle_recent_transactions(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        txs = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).limit(5).all()
        if not txs:
            return {
                'type': 'info',
                'title': '📜 Recent Transactions',
                'message': "You don't have any recorded transactions yet.",
                'actions': [{'label': 'Add Income', 'icon': 'plus', 'action': 'add_income'}],
                'suggested_prompts': ['What is my balance?']
            }

        items = []
        for t in txs:
            icon = '🟢' if t.type in ['income', 'topup', 'transfer_in'] else '🔴'
            items.append(f"{icon} <b>{t.title or t.type.capitalize()}:</b> ₹{t.amount:,.2f} ({t.created_at.strftime('%d %b')})")

        return {
            'type': 'transactions_list',
            'title': '📜 Recent Activity (Last 5)',
            'message': "<br>".join(items),
            'actions': [
                {'label': 'View All Transactions', 'icon': 'list', 'action': 'transactions'},
                {'label': 'Analytics', 'icon': 'bar-chart-2', 'action': 'analytics'}
            ],
            'suggested_prompts': ['What did I spend this month?', 'What is my balance?']
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
                'message': "You have not set any active savings goals yet. Creating goals helps you stay on track for vacations, emergency funds, or big purchases.",
                'actions': [{'label': 'Create Savings Goal', 'icon': 'target', 'action': 'create_goal'}],
                'suggested_prompts': ['How do pockets work?', 'What is my balance?']
            }

        items = []
        for g in goals:
            pct = round((g.current_amount / g.target_amount * 100) if g.target_amount > 0 else 0, 1)
            items.append(f"• <b>{g.name}:</b> ₹{g.current_amount:,.2f} / ₹{g.target_amount:,.2f} ({pct}%)")

        return {
            'type': 'savings_goals',
            'title': f'🎯 Savings Goals ({len(goals)})',
            'message': "<br>".join(items),
            'actions': [
                {'label': 'Open Goals Center', 'icon': 'target', 'action': 'analytics'},
                {'label': 'Create New Goal', 'icon': 'plus-circle', 'action': 'create_goal'}
            ],
            'suggested_prompts': ['What is my balance?', 'Show my pockets']
        }

    @classmethod
    def _handle_budgets(cls, user: Optional[User]) -> Dict[str, Any]:
        if not user:
            return cls._auth_required_response()

        budgets = Budget.query.filter_by(user_id=user.id).all()
        if not budgets:
            return {
                'type': 'info',
                'title': '📉 Budget Limits',
                'message': "No monthly budgets are currently configured. Set limits on pockets to receive automatic notifications at 75%, 90%, and 100% capacity.",
                'actions': [{'label': 'Configure Budgets', 'icon': 'sliders', 'action': 'budgets'}],
                'suggested_prompts': ['Show my pockets', 'What did I spend this month?']
            }

        items = [f"• <b>{b.category_or_pocket}:</b> Limit ₹{b.amount:,.2f}" for b in budgets]
        return {
            'type': 'budgets_overview',
            'title': f'📉 Active Budgets ({len(budgets)})',
            'message': "<br>".join(items),
            'actions': [{'label': 'Manage Budgets', 'icon': 'sliders', 'action': 'budgets'}],
            'suggested_prompts': ['What did I spend this month?', 'Show my pockets']
        }

    @classmethod
    def _handle_security_guide(cls, user: Optional[User], q: str) -> Dict[str, Any]:
        has_pin = bool(user.transaction_pin_hash) if user else False
        totp_active = bool(user.totp_enabled) if user else False

        status_lines = [
            f"• <b>4-Digit Transaction PIN:</b> {'Configured ✓' if has_pin else 'Not Set ⚠️'}",
            f"• <b>Authenticator 2FA (TOTP):</b> {'Active 🛡️' if totp_active else 'Disabled — Tap to Enable'}"
        ]

        return {
            'type': 'security_info',
            'title': '🔐 Multi-Layer Security & Two-Factor Authentication',
            'message': (
                "PocketPay protects your account with Multi-Layer Security and authentication protocols:<br><br>"
                + "<br>".join(status_lines) + "<br><br>"
                "Every financial transaction requires your 4-digit PIN, and Authenticator 2FA protects sensitive withdrawals and profile modifications."
            ),
            'actions': [
                {'label': 'Setup Authenticator 2FA', 'icon': 'shield', 'action': 'totp_setup'},
                {'label': 'Change Transaction PIN', 'icon': 'key', 'action': 'change_pin'},
                {'label': 'Security Settings', 'icon': 'settings', 'action': 'settings'}
            ],
            'suggested_prompts': ['How do I change my password?', 'What is my balance?']
        }

    @classmethod
    def _handle_create_pocket_guide(cls) -> Dict[str, Any]:
        return {
            'type': 'create_pocket_guide',
            'title': '✨ Creating a Smart Pocket',
            'message': (
                "Creating a Smart Pocket is simple:<br><br>"
                "1. Go to <b>Pockets</b> from the navigation menu.<br>"
                "2. Tap the <b>+ Create Pocket</b> button.<br>"
                "3. Enter a name (e.g., 'Groceries', 'Rent', 'Emergency Fund').<br>"
                "4. Choose an icon, color, and optional monthly target or budget.<br>"
                "5. Save to start organizing your funds instantly!"
            ),
            'actions': [
                {'label': 'Create New Pocket', 'icon': 'folder-plus', 'action': 'create_pocket'},
                {'label': 'View All Pockets', 'icon': 'wallet-cards', 'action': 'pockets'}
            ],
            'suggested_prompts': ['What is my balance?', 'Show my pockets', 'How does income distribution work?']
        }

    @classmethod
    def _handle_premium_info(cls, user: Optional[User]) -> Dict[str, Any]:
        is_prem = bool(user.is_premium) if user else False
        return {
            'type': 'premium_info',
            'title': '⭐ PocketPay Premium (PocketPay Pro)',
            'message': (
                f"<b>Status:</b> {'You are an active PocketPay Pro member ⭐' if is_prem else 'Free Plan'}<br><br>"
                "PocketPay Pro unlocks unlimited smart pockets, advanced category analytics, automated income distribution rules, and priority support desk access."
            ),
            'actions': [{'label': 'View Premium Features', 'icon': 'sparkles', 'action': 'view_premium'}],
            'suggested_prompts': ['What is my balance?', 'Show my pockets']
        }

    @classmethod
    def _handle_bank_transfer_guide(cls, user: Optional[User]) -> Dict[str, Any]:
        return {
            'type': 'bank_transfer_guide',
            'title': '🏦 Bank Transfers & Payouts',
            'message': (
                "To transfer funds to a registered bank account:<br><br>"
                "1. Go to <b>Wallet → Transfer to Bank</b>.<br>"
                "2. Select your recipient bank or add a new beneficiary.<br>"
                "3. Enter the amount and your secure 4-digit transaction PIN.<br>"
                "4. Instant settlement via IMPS / NEFT partner integration."
            ),
            'actions': [
                {'label': 'Transfer to Bank', 'icon': 'landmark', 'action': 'wallet'},
                {'label': 'Link Bank Account', 'icon': 'plus-circle', 'action': 'wallet'}
            ],
            'suggested_prompts': ['What is my balance?', 'How to send money?']
        }

    @classmethod
    def _handle_create_pocket_guide(cls) -> Dict[str, Any]:
        return {
            'type': 'guide',
            'title': '✨ Creating a Smart Pocket',
            'message': (
                "To create a smart pocket:<br>"
                "1. Tap <b>Create Pocket</b> or navigate to <b>Pockets</b>.<br>"
                "2. Choose a clear name (e.g., 'Groceries', 'Vacation Fund', 'Dining').<br>"
                "3. Pick a custom gradient color and icon.<br>"
                "4. (Optional) Set a budget target or monthly limit.<br>"
                "5. Save and start depositing or splitting incoming funds!"
            ),
            'actions': [{'label': 'Create Pocket Now', 'icon': 'folder-plus', 'action': 'create_pocket'}],
            'suggested_prompts': ['Show all pockets', 'What is my balance?']
        }

    @classmethod
    def _handle_transfer_guide(cls) -> Dict[str, Any]:
        return {
            'type': 'guide',
            'title': '💸 Sending Money',
            'message': (
                "You have two simple ways to transfer funds in PocketPay:<br><br>"
                "• <b>Between Pockets:</b> Reallocate money between your own pockets (e.g. from 'General' to 'Savings').<br>"
                "• <b>To Peer / Friend:</b> Send money instantly to any PocketPay Wallet ID, Virtual UPI ID, or phone number.<br><br>"
                "🛡️ <i>All transfers require your 4-digit transaction PIN confirmation.</i>"
            ),
            'actions': [
                {'label': 'Inter-Pocket Transfer', 'icon': 'refresh-ccw', 'action': 'transfer'},
                {'label': 'Send to Peer / Friend', 'icon': 'arrow-up-right', 'action': 'send_money'}
            ],
            'suggested_prompts': ['What is my balance?', 'Show my pockets']
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
                'After deletion, your email and phone number become free for re-registration as a fresh account.<br><br>'
                '🛡️ <i>The assistant cannot delete your account. This action must be completed manually through Security Settings.</i>'
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
                '🛡️ <i>PocketPay never stores or displays your password. The assistant cannot see or reveal it.</i>'
            ),
            'actions': [
                {'label': 'Security Settings', 'icon': 'key-round', 'action': 'wallet'},
            ],
            'suggested_prompts': ['How do I enable 2FA?', 'How do I change my PIN?', 'Show my balance']
        }

    @classmethod
    def _handle_fallback(cls, q: str, user: Optional[User], route: str) -> Dict[str, Any]:
        return {
            'type': 'fallback',
            'title': '💡 How can I assist you?',
            'message': (
                f"I can help with PocketPay features such as balance, transactions, pockets, payments, UPI, QR codes, account settings, and support.<br><br>"
                "Here are popular topics you can ask anytime:<br>"
                "• <b>\"What is my balance?\"</b> — Live wallet and pocket net worth<br>"
                "• <b>\"Show my PocketPay ID\"</b> — Your unique wallet & UPI ID<br>"
                "• <b>\"Show my pockets\"</b> — Breakdown of all smart pockets<br>"
                "• <b>\"Give me the helpline number\"</b> — Official support helplines & emails<br>"
                "• <b>\"Show recent transactions\"</b> — Latest income and expenses"
            ),
            'actions': [
                {'label': 'Check Balance', 'icon': 'wallet', 'action': 'balance'},
                {'label': 'View Pockets', 'icon': 'wallet-cards', 'action': 'pockets'},
                {'label': 'Contact Support', 'icon': 'headphones', 'action': 'support_modal'}
            ],
            'suggested_prompts': [
                'What is my balance?',
                'Show my PocketPay ID',
                'Give me the helpline number',
                'Show my recent transactions'
            ]
        }

    @classmethod
    def _auth_required_response(cls) -> Dict[str, Any]:
        return {
            'type': 'auth_required',
            'title': '🔒 Authentication Required',
            'message': 'Please log in to your PocketPay account to view personalized balances, pockets, and transaction reports.',
            'actions': [{'label': 'Log In', 'icon': 'log-in', 'action': 'login'}],
            'suggested_prompts': ['Give me the helpline number', 'How does PocketPay work?']
        }

    @classmethod
    def _empty_response(cls) -> Dict[str, Any]:
        return {
            'type': 'empty',
            'title': 'PocketPay Assistant',
            'message': 'Ask me anything about your PocketPay balances, spending, smart pockets, or customer support.',
            'actions': [],
            'suggested_prompts': ['What is my balance?', 'Show my PocketPay ID', 'Give me the helpline number']
        }
