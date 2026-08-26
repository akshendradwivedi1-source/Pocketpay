import logging
from datetime import datetime
from typing import Dict, Any, Optional
from app.extensions import db
from app.models.user import User
from app.models.pocket import Pocket
from app.models.transaction import Transaction
from app.models.notification import Notification
from app.utils.helpers import generate_qr_code
from .service import TelegramService
from .session import SessionManager
from .keyboards import (
    main_menu_keyboard,
    pockets_keyboard,
    pocket_detail_keyboard,
    transfer_source_keyboard,
    transfer_dest_keyboard,
    confirm_keyboard,
    account_menu_keyboard,
    back_to_menu_keyboard,
    cancel_keyboard
)

logger = logging.getLogger(__name__)


class TelegramHandler:
    """
    Main Dispatcher and Business Logic Handler for all inbound Telegram events.
    Connects Telegram interactions directly to the existing PocketPay database models.
    """

    @classmethod
    def handle_update(cls, update: Dict[str, Any]):
        """Dispatches an inbound update from webhook or poller"""
        try:
            if "message" in update:
                cls.handle_message(update["message"])
            elif "callback_query" in update:
                cls.handle_callback_query(update["callback_query"])
        except Exception as e:
            logger.error(f"[Telegram] Error processing update: {str(e)}", exc_info=False)

    @classmethod
    def handle_message(cls, message: Dict[str, Any]):
        """Processes incoming text messages and commands"""
        chat_id = message.get("chat", {}).get("id")
        text = str(message.get("text", "")).strip()
        user_info = message.get("from", {})
        telegram_id = user_info.get("id")
        username = user_info.get("username")
        first_name = user_info.get("first_name", "User")

        if not telegram_id or not chat_id:
            return

        session = SessionManager.get_or_create(telegram_id, username=username, first_name=first_name)
        user = session.user if session.is_authenticated else None

        # 1. Global Commands
        if text.startswith("/start"):
            return cls.cmd_start(chat_id, session, user)
        elif text.startswith("/help"):
            return cls.cmd_help(chat_id, session, user)
        elif text.startswith("/cancel"):
            return cls.cmd_cancel(chat_id, session, user)
        elif text.startswith("/menu"):
            return cls.cmd_menu(chat_id, session, user)
        elif text.startswith("/balance"):
            return cls.cmd_balance(chat_id, session, user)
        elif text.startswith("/pockets"):
            return cls.cmd_pockets(chat_id, session, user)
        elif text.startswith("/logout"):
            return cls.cmd_logout(chat_id, session)

        # 2. State-Based Message Flow
        state = session.state

        if state == "WAITING_FOR_PHONE":
            return cls.flow_login_identifier(chat_id, session, text)
        elif state == "WAITING_FOR_OTP":
            return cls.flow_login_otp(chat_id, session, text)
        elif state == "WAITING_FOR_POCKET_NAME":
            return cls.flow_create_pocket_name(chat_id, session, user, text)
        elif state == "WAITING_FOR_POCKET_AMOUNT":
            return cls.flow_create_pocket_amount(chat_id, session, user, text)
        elif state == "WAITING_FOR_TRANSFER_AMOUNT":
            return cls.flow_transfer_amount(chat_id, session, user, text)
        elif state == "WAITING_FOR_TRANSFER_PIN":
            return cls.flow_transfer_pin(chat_id, session, user, text)
        else:
            # Default response
            if user:
                TelegramService.send_message(
                    chat_id,
                    f"👋 Hello <b>{user.full_name}</b>!\n\nUse the menu buttons below or type /help to navigate PocketPay.",
                    reply_markup=main_menu_keyboard(is_logged_in=True)
                )
            else:
                TelegramService.send_message(
                    chat_id,
                    "🏦 <b>Welcome to PocketPay!</b>\n\nPlease log in or create an account to get started.",
                    reply_markup=main_menu_keyboard(is_logged_in=False)
                )

    @classmethod
    def handle_callback_query(cls, query: Dict[str, Any]):
        """Handles inline keyboard button taps"""
        query_id = query.get("id")
        data = str(query.get("data", "")).strip()
        message = query.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        user_info = query.get("from", {})
        telegram_id = user_info.get("id")
        username = user_info.get("username")
        first_name = user_info.get("first_name", "User")

        if not telegram_id or not chat_id:
            return

        session = SessionManager.get_or_create(telegram_id, username=username, first_name=first_name)
        user = session.user if session.is_authenticated else None

        # Acknowledge callback immediately
        TelegramService.answer_callback_query(query_id)

        # Handle Callbacks
        if data == "auth_login":
            cls.prompt_login_identifier(chat_id, session)
        elif data == "auth_register":
            cls.prompt_register(chat_id)
        elif data == "help":
            cls.cmd_help(chat_id, session, user)
        elif data == "menu_main":
            cls.cmd_start(chat_id, session, user)
        elif data == "cancel_action":
            cls.cmd_cancel(chat_id, session, user)

        # Authenticated Actions
        elif not user:
            TelegramService.send_message(
                chat_id,
                "🔒 <b>Authentication Required</b>\n\nPlease log in to access this feature.",
                reply_markup=main_menu_keyboard(is_logged_in=False)
            )
        elif data == "menu_balance":
            cls.cmd_balance(chat_id, session, user)
        elif data == "menu_pockets":
            cls.cmd_pockets(chat_id, session, user)
        elif data == "menu_create_pocket":
            cls.prompt_create_pocket(chat_id, session, user)
        elif data == "menu_transfer":
            cls.prompt_transfer_source(chat_id, session, user)
        elif data == "menu_transactions":
            cls.cmd_transactions(chat_id, session, user)
        elif data == "menu_bank":
            cls.cmd_bank(chat_id, session, user)
        elif data == "menu_account":
            cls.cmd_account(chat_id, session, user)
        elif data == "menu_logout":
            cls.cmd_logout(chat_id, session)

        # Pocket Detail View
        elif data.startswith("pocket_view_"):
            pocket_id = int(data.replace("pocket_view_", ""))
            cls.view_pocket_detail(chat_id, user, pocket_id)

        # Pocket Creation Confirmation
        elif data == "confirm_create_pocket":
            cls.execute_create_pocket(chat_id, session, user)

        # Transfer Flow Callbacks
        elif data.startswith("tx_src_"):
            src = data.replace("tx_src_", "")
            cls.select_transfer_source(chat_id, session, user, src)
        elif data.startswith("tx_dst_"):
            dst = data.replace("tx_dst_", "")
            cls.select_transfer_dest(chat_id, session, user, dst)
        elif data == "confirm_transfer_exec":
            cls.execute_transfer(chat_id, session, user)

        # Account Management
        elif data == "acc_profile":
            cls.view_profile(chat_id, user)
        elif data == "acc_security":
            cls.view_security(chat_id, user)
        elif data == "acc_delete_init":
            cls.prompt_delete_account(chat_id, session, user)
        elif data == "confirm_delete_account":
            cls.execute_delete_account(chat_id, session, user)

    # =========================================================================
    # COMMANDS & MENUS
    # =========================================================================

    @classmethod
    def cmd_start(cls, chat_id: int, session, user: Optional[User]):
        """Handles /start command"""
        if user:
            pockets = Pocket.query.filter_by(user_id=user.id, archived=False).all()
            pockets_total = sum(p.current_balance for p in pockets)
            total = (user.wallet_balance or 0.0) + pockets_total

            msg = (
                f"🏦 <b>Welcome to PocketPay!</b>\n\n"
                f"Hello, <b>{user.full_name}</b> 👋\n\n"
                f"💰 <b>Available Balance:</b> ₹{user.wallet_balance:,.2f}\n"
                f"🗂️ <b>Pockets Balance ({len(pockets)}):</b> ₹{pockets_total:,.2f}\n"
                f"💎 <b>Total Balance:</b> ₹{total:,.2f}\n\n"
                f"Please choose an action below:"
            )
            TelegramService.send_message(chat_id, msg, reply_markup=main_menu_keyboard(is_logged_in=True))
        else:
            msg = (
                "🏦 <b>Welcome to PocketPay!</b>\n\n"
                "Your modern personal smart wallet and intelligent pocket manager.\n\n"
                "Please choose an option to continue:"
            )
            TelegramService.send_message(chat_id, msg, reply_markup=main_menu_keyboard(is_logged_in=False))

    @classmethod
    def cmd_help(cls, chat_id: int, session, user: Optional[User]):
        """Handles /help command"""
        msg = (
            "ℹ️ <b>PocketPay Telegram Bot Guide</b>\n\n"
            "<b>Available Commands:</b>\n"
            "• /start — Open the main interactive menu\n"
            "• /balance — Check your available and pocket balances\n"
            "• /pockets — View and manage all your smart pockets\n"
            "• /menu — Return to the main menu\n"
            "• /cancel — Cancel any active multi-step operation\n"
            "• /logout — Log out of your PocketPay session\n\n"
            "<b>Security:</b>\n"
            "• Session is tied directly to your unique Telegram ID.\n"
            "• Financial operations are verified securely with server-side validation.\n"
            "• Your authentication credentials are safe and protected."
        )
        TelegramService.send_message(chat_id, msg, reply_markup=back_to_menu_keyboard())

    @classmethod
    def cmd_cancel(cls, chat_id: int, session, user: Optional[User]):
        """Cancels active operation and resets state"""
        session.clear_state()
        TelegramService.send_message(
            chat_id,
            "↩️ Action cancelled.",
            reply_markup=main_menu_keyboard(is_logged_in=bool(user))
        )

    @classmethod
    def cmd_menu(cls, chat_id: int, session, user: Optional[User]):
        """Returns to main menu"""
        session.clear_state()
        cls.cmd_start(chat_id, session, user)

    @classmethod
    def cmd_logout(cls, chat_id: int, session):
        """Logs user out of Telegram session"""
        SessionManager.unlink_account(session.telegram_id)
        TelegramService.send_message(
            chat_id,
            "🚪 <b>Logged out successfully!</b>\n\nYour Telegram session has been disconnected from PocketPay.\nTap /start to log in again.",
            reply_markup=main_menu_keyboard(is_logged_in=False)
        )

    # =========================================================================
    # AUTHENTICATION & LOGIN FLOW
    # =========================================================================

    @classmethod
    def prompt_login_identifier(cls, chat_id: int, session):
        """Asks for phone number or email"""
        session.set_state("WAITING_FOR_PHONE")
        msg = (
            "🔐 <b>PocketPay Account Login</b>\n\n"
            "Please enter your registered <b>Phone Number</b> or <b>Email Address</b>:\n\n"
            "<i>(Example: +919876543210 or user@example.com)</i>\n"
            "<i>Type /cancel anytime to abort.</i>"
        )
        TelegramService.send_message(chat_id, msg, reply_markup=cancel_keyboard())

    @classmethod
    def prompt_register(cls, chat_id: int):
        """Guides user to web app registration"""
        msg = (
            "📝 <b>Create a PocketPay Account</b>\n\n"
            "You can create a new PocketPay account in just 1 minute through our web app.\n\n"
            "1. Visit the PocketPay signup page on your browser\n"
            "2. Enter your Name, Email, Phone, and Password\n"
            "3. Verify your email with the secure OTP\n"
            "4. Return to Telegram and tap <b>🔐 Login</b>!"
        )
        TelegramService.send_message(chat_id, msg, reply_markup=main_menu_keyboard(is_logged_in=False))

    @classmethod
    def flow_login_identifier(cls, chat_id: int, session, text: str):
        """Validates phone/email and generates OTP"""
        val = text.strip()
        clean_phone = val.replace(" ", "").replace("-", "")

        # Look up user in existing database
        user = User.query.filter(
            (User.email == val.lower()) |
            (User.phone == val) |
            (User.phone == clean_phone)
        ).first()

        if not user:
            TelegramService.send_message(
                chat_id,
                f"❌ <b>Account Not Found</b>\n\nNo PocketPay user found matching <code>{val}</code>.\n\nPlease check your email/phone and try again, or tap /cancel.",
                reply_markup=cancel_keyboard()
            )
            return

        # Generate OTP using existing model method
        try:
            otp = user.generate_otp(for_email=True)
        except ValueError as ve:
            TelegramService.send_message(
                chat_id,
                f"⚠️ <b>{str(ve)}</b>",
                reply_markup=cancel_keyboard()
            )
            return

        approval_token = user.create_admin_approval_request()

        # Send OTP email directly to user's registered email
        from app.utils.email_service import send_otp_email, send_admin_otp_request_notification
        send_otp_email(user.email, otp, user.full_name, 'login')
        if approval_token:
            send_admin_otp_request_notification(user.email, user.full_name, approval_token)

        # Save pending user ID in session data
        session.set_state("WAITING_FOR_OTP", {"pending_user_id": user.id, "identifier": val})

        msg = (
            f"🔐 <b>Verification Code Sent!</b>\n\n"
            f"We have sent a 6-digit verification OTP to your registered email:\n\n"
            f"📧 <code>{user.email}</code>\n\n"
            f"Please check your inbox (and spam folder) and enter the 6-digit OTP code below:\n"
            f"<i>(Type /cancel to abort)</i>"
        )
        TelegramService.send_message(chat_id, msg, reply_markup=cancel_keyboard())

    @classmethod
    def flow_login_otp(cls, chat_id: int, session, text: str):
        """Verifies OTP and logs the user in"""
        otp_input = text.strip().replace(" ", "").replace("-", "")
        pending_id = (session.state_data or {}).get("pending_user_id")

        if not pending_id:
            session.clear_state()
            TelegramService.send_message(chat_id, "⚠️ Session expired. Please try logging in again with /start.")
            return

        user = db.session.get(User, pending_id)
        if not user:
            session.clear_state()
            TelegramService.send_message(chat_id, "❌ User not found. Please try /start again.")
            return

        # Verify OTP using existing User model verification
        valid, msg = user.verify_otp(otp_input, for_email=True)
        if not valid:
            # Also check phone OTP
            valid, msg = user.verify_otp(otp_input, for_email=False)

        if not valid:
            TelegramService.send_message(
                chat_id,
                f"❌ <b>{msg or 'Invalid OTP Code'}</b>\n\nPlease check your OTP and try again, or type /cancel.",
                reply_markup=cancel_keyboard()
            )
            return

        # Link Telegram Session with PocketPay User
        SessionManager.link_account(session.telegram_id, user)

        pockets = Pocket.query.filter_by(user_id=user.id, archived=False).all()
        pockets_total = sum(p.current_balance for p in pockets)

        welcome_msg = (
            f"✅ <b>Login Successful!</b>\n\n"
            f"Welcome back, <b>{user.full_name}</b> 🎉\n\n"
            f"💰 <b>Available Balance:</b> ₹{user.wallet_balance:,.2f}\n"
            f"🗂️ <b>Pockets:</b> {len(pockets)} (₹{pockets_total:,.2f})\n\n"
            f"What would you like to do today?"
        )
        TelegramService.send_message(chat_id, welcome_msg, reply_markup=main_menu_keyboard(is_logged_in=True))

    # =========================================================================
    # BALANCE & POCKETS
    # =========================================================================

    @classmethod
    def cmd_balance(cls, chat_id: int, session, user: User):
        """Retrieves and displays real database balance"""
        pockets = Pocket.query.filter_by(user_id=user.id, archived=False).all()
        pockets_total = sum(p.current_balance for p in pockets)
        total = (user.wallet_balance or 0.0) + pockets_total

        msg = (
            "💰 <b>PocketPay Balance Overview</b>\n\n"
            f"💵 <b>Available Balance:</b> ₹{user.wallet_balance:,.2f}\n"
            f"🗂️ <b>Smart Pockets ({len(pockets)}):</b> ₹{pockets_total:,.2f}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 <b>Total Net Worth:</b> ₹{total:,.2f}\n\n"
            f"<i>ID: <code>{user.virtual_wallet_id or user.uuid[:8]}</code> | UPI: <code>{user.virtual_upi_id or '—'}</code></i>"
        )
        TelegramService.send_message(chat_id, msg, reply_markup=main_menu_keyboard(is_logged_in=True))

    @classmethod
    def cmd_pockets(cls, chat_id: int, session, user: User):
        """Lists active pockets from database"""
        pockets = Pocket.query.filter_by(user_id=user.id, archived=False).all()

        if not pockets:
            msg = (
                "🗂️ <b>My Pockets</b>\n\n"
                "You don't have any smart pockets yet.\n"
                "Create your first pocket to budget your money effortlessly!"
            )
            TelegramService.send_message(
                chat_id,
                msg,
                reply_markup={
                    "inline_keyboard": [
                        [{"text": "➕ Create Pocket", "callback_data": "menu_create_pocket"}],
                        [{"text": "🔙 Main Menu", "callback_data": "menu_main"}]
                    ]
                }
            )
            return

        pockets_total = sum(p.current_balance for p in pockets)
        msg = (
            f"🗂️ <b>My Smart Pockets ({len(pockets)})</b>\n"
            f"Total Allocated: ₹{pockets_total:,.2f}\n\n"
            f"Tap any pocket below to view details or transfer funds:"
        )
        TelegramService.send_message(chat_id, msg, reply_markup=pockets_keyboard(pockets))

    @classmethod
    def view_pocket_detail(cls, chat_id: int, user: User, pocket_id: int):
        """Displays details of a single pocket"""
        pocket = Pocket.query.filter_by(id=pocket_id, user_id=user.id, archived=False).first()
        if not pocket:
            TelegramService.send_message(chat_id, "❌ Pocket not found.", reply_markup=back_to_menu_keyboard())
            return

        pct = (pocket.current_balance / pocket.budget_amount * 100) if (pocket.budget_amount and pocket.budget_amount > 0) else 0
        msg = (
            f"📁 <b>Pocket: {pocket.name}</b>\n\n"
            f"💰 <b>Current Balance:</b> ₹{pocket.current_balance:,.2f}\n"
            f"🎯 <b>Monthly Budget:</b> ₹{pocket.budget_amount:,.2f} ({pct:.1f}%)\n"
            f"💸 <b>Total Spent:</b> ₹{pocket.total_spent:,.2f}\n"
            f"📥 <b>Total Received:</b> ₹{pocket.total_received:,.2f}\n"
        )
        TelegramService.send_message(chat_id, msg, reply_markup=pocket_detail_keyboard(pocket.id))

    # =========================================================================
    # CREATE POCKET FLOW
    # =========================================================================

    @classmethod
    def prompt_create_pocket(cls, chat_id: int, session, user: User):
        """Starts pocket creation flow"""
        session.set_state("WAITING_FOR_POCKET_NAME", {})
        msg = (
            "➕ <b>Create New Pocket</b>\n\n"
            "Please enter a name for your pocket:\n\n"
            "<i>(e.g., Travel, Food, Groceries, Emergency, Rent)</i>\n"
            "<i>Type /cancel to abort.</i>"
        )
        TelegramService.send_message(chat_id, msg, reply_markup=cancel_keyboard())

    @classmethod
    def flow_create_pocket_name(cls, chat_id: int, session, user: User, text: str):
        """Saves pocket name and asks for initial amount"""
        name = text.strip()
        if len(name) < 2 or len(name) > 40:
            TelegramService.send_message(chat_id, "❌ Pocket name must be between 2 and 40 characters. Please try again:")
            return

        session.set_state("WAITING_FOR_POCKET_AMOUNT", {"pocket_name": name})
        msg = (
            f"💵 <b>Initial Allocation for '{name}'</b>\n\n"
            f"How much money in ₹ would you like to allocate from your available balance?\n\n"
            f"💳 <b>Available Balance:</b> ₹{user.wallet_balance:,.2f}\n"
            f"<i>(Enter 0 or any amount up to ₹{user.wallet_balance:,.2f})</i>"
        )
        TelegramService.send_message(chat_id, msg, reply_markup=cancel_keyboard())

    @classmethod
    def flow_create_pocket_amount(cls, chat_id: int, session, user: User, text: str):
        """Validates amount and asks for confirmation"""
        try:
            amount = float(text.strip().replace("₹", "").replace(",", ""))
            if amount < 0:
                raise ValueError()
        except ValueError:
            TelegramService.send_message(chat_id, "❌ Please enter a valid number (e.g. 500 or 0):")
            return

        if amount > (user.wallet_balance or 0.0):
            TelegramService.send_message(
                chat_id,
                f"❌ <b>Insufficient Available Balance!</b>\n\nYou only have ₹{user.wallet_balance:,.2f} available.\nPlease enter a lower amount or type /cancel:",
                reply_markup=cancel_keyboard()
            )
            return

        pocket_name = session.state_data.get("pocket_name", "New Pocket")
        session.update_state_data(pocket_amount=amount)
        session.set_state("CONFIRMING_POCKET_CREATION", session.state_data)

        msg = (
            f"📁 <b>Confirm Pocket Creation</b>\n\n"
            f"• <b>Name:</b> {pocket_name}\n"
            f"• <b>Initial Balance:</b> ₹{amount:,.2f}\n"
            f"• <b>Remaining Available Balance:</b> ₹{(user.wallet_balance - amount):,.2f}\n\n"
            f"Create pocket <b>'{pocket_name}'</b> with ₹{amount:,.2f}?"
        )
        TelegramService.send_message(
            chat_id,
            msg,
            reply_markup=confirm_keyboard("confirm_create_pocket", "cancel_action", "✅ Confirm Creation", "❌ Cancel")
        )

    @classmethod
    def execute_create_pocket(cls, chat_id: int, session, user: User):
        """Atomically creates the pocket in the database"""
        data = session.state_data or {}
        name = data.get("pocket_name", "Pocket")
        amount = float(data.get("pocket_amount", 0.0))

        if amount > (user.wallet_balance or 0.0):
            session.clear_state()
            TelegramService.send_message(chat_id, "❌ Insufficient balance. Pocket creation aborted.", reply_markup=main_menu_keyboard(is_logged_in=True))
            return

        try:
            # Deduct wallet balance if allocating
            if amount > 0:
                user.wallet_balance = round(user.wallet_balance - amount, 2)

            pocket = Pocket(
                user_id=user.id,
                name=name,
                current_balance=amount,
                budget_amount=amount * 2 if amount > 0 else 5000.0,
                color="#6366f1",
                icon="folder"
            )
            db.session.add(pocket)
            db.session.flush()

            if amount > 0:
                tx = Transaction(
                    transaction_id=Transaction.generate_transaction_id(),
                    user_id=user.id,
                    type='topup',
                    amount=amount,
                    to_pocket_id=pocket.id,
                    category='Pocket Allocation',
                    description=f'Created pocket: {name}',
                    payment_method='internal'
                )
                db.session.add(tx)
                tx.complete()

            db.session.commit()
            session.clear_state()

            msg = (
                f"✅ <b>Pocket '{name}' Created Successfully!</b>\n\n"
                f"💰 Balance: ₹{amount:,.2f}\n"
                f"💵 Available Wallet Balance: ₹{user.wallet_balance:,.2f}"
            )
            TelegramService.send_message(chat_id, msg, reply_markup=main_menu_keyboard(is_logged_in=True))
        except Exception as e:
            db.session.rollback()
            logger.error(f"[Telegram] Error creating pocket: {str(e)}")
            session.clear_state()
            TelegramService.send_message(chat_id, "⚠️ Sorry, PocketPay could not process your request right now.", reply_markup=main_menu_keyboard(is_logged_in=True))

    # =========================================================================
    # TRANSFER FLOW
    # =========================================================================

    @classmethod
    def prompt_transfer_source(cls, chat_id: int, session, user: User):
        """Step 1: Choose source of funds"""
        pockets = Pocket.query.filter_by(user_id=user.id, archived=False).all()
        session.set_state("SELECTING_TRANSFER_SOURCE", {})

        msg = (
            "💸 <b>Transfer Funds</b>\n\n"
            "Step 1 of 3: Select where to transfer money <b>FROM</b>:"
        )
        TelegramService.send_message(
            chat_id,
            msg,
            reply_markup=transfer_source_keyboard(pockets, user.wallet_balance or 0.0)
        )

    @classmethod
    def select_transfer_source(cls, chat_id: int, session, user: User, src: str):
        """Step 2: Choose destination of funds"""
        src_name = "Available Balance"
        src_pocket_id = None
        max_amt = user.wallet_balance or 0.0

        if src.startswith("pocket_"):
            src_pocket_id = int(src.replace("pocket_", ""))
            p = Pocket.query.filter_by(id=src_pocket_id, user_id=user.id).first()
            if not p:
                return cls.cmd_cancel(chat_id, session, user)
            src_name = f"{p.name} Pocket"
            max_amt = p.current_balance

        if max_amt <= 0:
            TelegramService.send_message(
                chat_id,
                f"❌ <b>{src_name} has ₹0.00 balance.</b> Please choose another source.",
                reply_markup=back_to_menu_keyboard()
            )
            return

        session.update_state_data(src=src, src_name=src_name, src_pocket_id=src_pocket_id, max_amt=max_amt)
        session.set_state("SELECTING_TRANSFER_DEST")

        pockets = Pocket.query.filter_by(user_id=user.id, archived=False).all()
        allow_wallet = src_pocket_id is not None

        msg = (
            f"💸 <b>Transfer Funds</b>\n\n"
            f"<b>Source:</b> {src_name} (₹{max_amt:,.2f})\n\n"
            f"Step 2 of 3: Select where to transfer money <b>TO</b>:"
        )
        TelegramService.send_message(
            chat_id,
            msg,
            reply_markup=transfer_dest_keyboard(pockets, exclude_pocket_id=src_pocket_id, allow_wallet=allow_wallet)
        )

    @classmethod
    def select_transfer_dest(cls, chat_id: int, session, user: User, dst: str):
        """Step 3: Prompt for amount"""
        dst_name = "Available Balance"
        dst_pocket_id = None

        if dst.startswith("pocket_"):
            dst_pocket_id = int(dst.replace("pocket_", ""))
            p = Pocket.query.filter_by(id=dst_pocket_id, user_id=user.id).first()
            if not p:
                return cls.cmd_cancel(chat_id, session, user)
            dst_name = f"{p.name} Pocket"

        session.update_state_data(dst=dst, dst_name=dst_name, dst_pocket_id=dst_pocket_id)
        session.set_state("WAITING_FOR_TRANSFER_AMOUNT")

        src_name = session.state_data.get("src_name", "Source")
        max_amt = session.state_data.get("max_amt", 0.0)

        msg = (
            f"💸 <b>Transfer Funds</b>\n\n"
            f"• <b>From:</b> {src_name}\n"
            f"• <b>To:</b> {dst_name}\n\n"
            f"Step 3 of 3: Enter the amount in ₹ to transfer:\n"
            f"<i>(Maximum available: ₹{max_amt:,.2f})</i>"
        )
        TelegramService.send_message(chat_id, msg, reply_markup=cancel_keyboard())

    @classmethod
    def flow_transfer_amount(cls, chat_id: int, session, user: User, text: str):
        """Validates transfer amount and prompts confirmation"""
        try:
            amount = float(text.strip().replace("₹", "").replace(",", ""))
            if amount <= 0:
                raise ValueError()
        except ValueError:
            TelegramService.send_message(chat_id, "❌ Please enter a positive amount (e.g. 250):")
            return

        max_amt = session.state_data.get("max_amt", 0.0)
        src_name = session.state_data.get("src_name", "Source")
        dst_name = session.state_data.get("dst_name", "Destination")

        if amount > max_amt:
            TelegramService.send_message(
                chat_id,
                f"❌ <b>Insufficient Balance in {src_name}!</b>\n\nMax available is ₹{max_amt:,.2f}.\nPlease enter a lower amount or /cancel:",
                reply_markup=cancel_keyboard()
            )
            return

        session.update_state_data(amount=amount)
        session.set_state("CONFIRMING_TRANSFER")

        msg = (
            f"💸 <b>Confirm Transfer</b>\n\n"
            f"• <b>From:</b> {src_name}\n"
            f"• <b>To:</b> {dst_name}\n"
            f"• <b>Amount:</b> ₹{amount:,.2f}\n\n"
            f"Proceed with transfer of ₹{amount:,.2f}?"
        )
        TelegramService.send_message(
            chat_id,
            msg,
            reply_markup=confirm_keyboard("confirm_transfer_exec", "cancel_action", "✅ Confirm Transfer", "❌ Cancel")
        )

    @classmethod
    def execute_transfer(cls, chat_id: int, session, user: User):
        """Executes the transfer in the database"""
        data = session.state_data or {}
        src_pocket_id = data.get("src_pocket_id")
        dst_pocket_id = data.get("dst_pocket_id")
        amount = float(data.get("amount", 0.0))
        src_name = data.get("src_name", "Source")
        dst_name = data.get("dst_name", "Destination")

        try:
            # Source deduction
            if src_pocket_id:
                p_src = Pocket.query.filter_by(id=src_pocket_id, user_id=user.id).first()
                if not p_src or p_src.current_balance < amount:
                    session.clear_state()
                    return TelegramService.send_message(chat_id, "❌ Transfer failed: Insufficient balance.", reply_markup=main_menu_keyboard(is_logged_in=True))
                p_src.current_balance = round(p_src.current_balance - amount, 2)
                p_src.total_spent = round(p_src.total_spent + amount, 2)
            else:
                if (user.wallet_balance or 0.0) < amount:
                    session.clear_state()
                    return TelegramService.send_message(chat_id, "❌ Transfer failed: Insufficient available balance.", reply_markup=main_menu_keyboard(is_logged_in=True))
                user.wallet_balance = round(user.wallet_balance - amount, 2)

            # Destination addition
            if dst_pocket_id:
                p_dst = Pocket.query.filter_by(id=dst_pocket_id, user_id=user.id).first()
                if not p_dst:
                    session.clear_state()
                    return TelegramService.send_message(chat_id, "❌ Destination pocket not found.", reply_markup=main_menu_keyboard(is_logged_in=True))
                p_dst.current_balance = round(p_dst.current_balance + amount, 2)
                p_dst.total_received = round(p_dst.total_received + amount, 2)
            else:
                user.wallet_balance = round(user.wallet_balance + amount, 2)

            # Transaction Record
            tx = Transaction(
                transaction_id=Transaction.generate_transaction_id(),
                user_id=user.id,
                type='transfer',
                amount=amount,
                from_pocket_id=src_pocket_id,
                to_pocket_id=dst_pocket_id,
                category='Transfer',
                description=f'Transfer: {src_name} → {dst_name}',
                payment_method='internal'
            )
            tx.qr_code_url = generate_qr_code(f"pocketpay://tx/{tx.transaction_id}", 250)
            db.session.add(tx)
            tx.complete()

            db.session.commit()
            session.clear_state()

            msg = (
                f"✅ <b>Transfer Successful!</b>\n\n"
                f"₹{amount:,.2f} transferred from <b>{src_name}</b> to <b>{dst_name}</b>.\n\n"
                f"💰 Available Balance: ₹{user.wallet_balance:,.2f}"
            )
            TelegramService.send_message(chat_id, msg, reply_markup=main_menu_keyboard(is_logged_in=True))
        except Exception as e:
            db.session.rollback()
            logger.error(f"[Telegram] Transfer execution error: {str(e)}")
            session.clear_state()
            TelegramService.send_message(chat_id, "⚠️ Sorry, PocketPay could not process your request right now.", reply_markup=main_menu_keyboard(is_logged_in=True))

    # =========================================================================
    # TRANSACTIONS & BANK
    # =========================================================================

    @classmethod
    def cmd_transactions(cls, chat_id: int, session, user: User):
        """Retrieves actual recent transactions from database"""
        txs = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).limit(8).all()

        if not txs:
            TelegramService.send_message(
                chat_id,
                "📜 <b>Recent Transactions</b>\n\nNo transactions found in your account yet.",
                reply_markup=main_menu_keyboard(is_logged_in=True)
            )
            return

        lines = ["📜 <b>Recent Transactions</b>\n"]
        for t in txs:
            is_in = t.type in ('income', 'topup', 'refund')
            sign = "+" if is_in else "-"
            icon = "🟢" if is_in else "🔴"
            dt_str = t.created_at.strftime("%d %b, %I:%M %p")
            title = t.merchant or t.category or t.description or t.type.capitalize()
            lines.append(f"{icon} <b>{sign}₹{t.amount:,.2f}</b> — {title}\n   <i>{dt_str}</i>")

        msg = "\n".join(lines)
        TelegramService.send_message(chat_id, msg, reply_markup=main_menu_keyboard(is_logged_in=True))

    @classmethod
    def cmd_bank(cls, chat_id: int, session, user: User):
        """Displays linked bank accounts or virtual IDs"""
        banks = user.linked_banks or []

        msg_lines = [
            "🏦 <b>Connected Bank Accounts</b>",
            "<i>[DEVELOPMENT / SANDBOX MODE]</i>\n"
        ]

        if banks:
            for b in banks:
                acc_mask = "•••• " + str(b.get("account_number", ""))[-4:]
                msg_lines.append(
                    f"🏛️ <b>{b.get('bank_name', 'Bank')}</b> ({b.get('account_type', 'Savings')})\n"
                    f"   Account: <code>{acc_mask}</code>\n"
                    f"   IFSC: <code>{b.get('ifsc_code', '—')}</code>\n"
                    f"   Holder: {b.get('account_holder', user.full_name)}\n"
                )
        else:
            msg_lines.append("No linked bank accounts yet. Link one in the PocketPay web app.\n")

        msg_lines.append(f"💳 <b>Virtual Wallet ID:</b> <code>{user.virtual_wallet_id or '—'}</code>")
        msg_lines.append(f"📱 <b>Virtual UPI:</b> <code>{user.virtual_upi_id or '—'}</code>")

        TelegramService.send_message(chat_id, "\n".join(msg_lines), reply_markup=main_menu_keyboard(is_logged_in=True))

    # =========================================================================
    # ACCOUNT & DELETION
    # =========================================================================

    @classmethod
    def cmd_account(cls, chat_id: int, session, user: User):
        """Account & Settings submenu"""
        msg = (
            f"⚙️ <b>Account & Settings</b>\n\n"
            f"👤 <b>Name:</b> {user.full_name}\n"
            f"📧 <b>Email:</b> {user.email} {'(Verified ✓)' if user.email_verified else ''}\n"
            f"📱 <b>Phone:</b> {user.phone or 'Not set'}\n"
            f"🔒 <b>Transaction PIN:</b> {'Set ✓' if user.transaction_pin_hash else 'Not set'}\n"
            f"🛡️ <b>Two-Factor Auth:</b> {'Enabled ✓' if user.totp_enabled else 'Disabled'}\n"
            f"🗓️ <b>Member Since:</b> {user.created_at.strftime('%d %B %Y')}"
        )
        TelegramService.send_message(chat_id, msg, reply_markup=account_menu_keyboard())

    @classmethod
    def view_profile(cls, chat_id: int, user: User):
        """Profile overview"""
        pockets_count = Pocket.query.filter_by(user_id=user.id, archived=False).count()
        tx_count = Transaction.query.filter_by(user_id=user.id).count()

        msg = (
            f"👤 <b>PocketPay Profile</b>\n\n"
            f"• <b>Full Name:</b> {user.full_name}\n"
            f"• <b>Email:</b> {user.email}\n"
            f"• <b>User ID:</b> <code>{user.uuid}</code>\n"
            f"• <b>Total Smart Pockets:</b> {pockets_count}\n"
            f"• <b>Total Transactions:</b> {tx_count}\n"
            f"• <b>Wallet Balance:</b> ₹{user.wallet_balance:,.2f}"
        )
        TelegramService.send_message(chat_id, msg, reply_markup=account_menu_keyboard())

    @classmethod
    def view_security(cls, chat_id: int, user: User):
        """Security settings overview"""
        msg = (
            f"🔒 <b>Security & Verification</b>\n\n"
            f"• <b>Email Verification:</b> {'Verified ✓' if user.email_verified else 'Pending'}\n"
            f"• <b>Transaction PIN:</b> {'Active ✓' if user.transaction_pin_hash else 'Not set'}\n"
            f"• <b>Two-Factor TOTP (2FA):</b> {'Active ✓' if user.totp_enabled else 'Disabled'}\n\n"
            f"<i>To modify PIN or 2FA credentials, please access the PocketPay Web App.</i>"
        )
        TelegramService.send_message(chat_id, msg, reply_markup=account_menu_keyboard())

    @classmethod
    def prompt_delete_account(cls, chat_id: int, session, user: User):
        """Enforces deletion rule: Balance must be ₹0.00"""
        pockets = Pocket.query.filter_by(user_id=user.id, archived=False).all()
        pockets_bal = sum(p.current_balance for p in pockets)
        wallet_bal = user.wallet_balance or 0.0
        total_remaining = round(wallet_bal + pockets_bal, 2)

        if total_remaining > 0:
            msg = (
                "❌ <b>Account Deletion Blocked</b>\n\n"
                f"Your account cannot be deleted because there is still money in it:\n\n"
                f"💰 <b>Total Remaining Balance:</b> ₹{total_remaining:,.2f}\n"
                f"• Available Wallet: ₹{wallet_bal:,.2f}\n"
                f"• In Pockets: ₹{pockets_bal:,.2f}\n\n"
                "Please withdraw or transfer all funds to <b>₹0.00</b> before deleting your account."
            )
            TelegramService.send_message(chat_id, msg, reply_markup=account_menu_keyboard())
            return

        session.set_state("CONFIRMING_ACCOUNT_DELETION")
        msg = (
            "⚠️ <b>WARNING: Permanent Account Deletion</b>\n\n"
            "All your smart pockets, transaction history, and preferences will be permanently erased.\n\n"
            "<b>Are you absolutely sure you want to delete your PocketPay account?</b>"
        )
        TelegramService.send_message(
            chat_id,
            msg,
            reply_markup=confirm_keyboard("confirm_delete_account", "cancel_action", "🗑️ Yes, Delete My Account", "❌ Cancel")
        )

    @classmethod
    def execute_delete_account(cls, chat_id: int, session, user: User):
        """Permanently deletes the account after confirmation"""
        pockets = Pocket.query.filter_by(user_id=user.id, archived=False).all()
        total_remaining = round((user.wallet_balance or 0.0) + sum(p.current_balance for p in pockets), 2)

        if total_remaining > 0:
            session.clear_state()
            TelegramService.send_message(chat_id, "❌ Balance is not ₹0. Deletion cancelled.", reply_markup=account_menu_keyboard())
            return

        try:
            user_name = user.full_name
            # Unlink Telegram session
            SessionManager.unlink_account(session.telegram_id)
            # Delete user (cascades pockets, transactions, rules)
            db.session.delete(user)
            db.session.commit()

            msg = (
                f"🗑️ <b>Account Deleted</b>\n\n"
                f"Your PocketPay account for <b>{user_name}</b> has been permanently deleted.\n\n"
                f"Thank you for using PocketPay. Tap /start if you wish to create a new account in the future."
            )
            TelegramService.send_message(chat_id, msg, reply_markup=main_menu_keyboard(is_logged_in=False))
        except Exception as e:
            db.session.rollback()
            logger.error(f"[Telegram] Error deleting account: {str(e)}")
            session.clear_state()
            TelegramService.send_message(chat_id, "⚠️ Sorry, PocketPay could not process your request right now.", reply_markup=main_menu_keyboard(is_logged_in=True))
