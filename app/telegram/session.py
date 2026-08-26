from datetime import datetime
from typing import Optional
from app.extensions import db
from app.models.telegram_user import TelegramUser
from app.models.user import User


class SessionManager:
    """
    Manages persistent per-user Telegram conversation sessions using the database.
    Prevents race conditions and guarantees isolated states for concurrent Telegram users.
    """

    @classmethod
    def get_or_create(cls, telegram_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> TelegramUser:
        """Retrieves or creates a TelegramUser entity in the database"""
        session = TelegramUser.query.filter_by(telegram_id=telegram_id).first()
        if not session:
            session = TelegramUser(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                state='START',
                state_data={}
            )
            db.session.add(session)
            db.session.commit()
        else:
            # Update username/first_name if changed
            updated = False
            if username and session.username != username:
                session.username = username
                updated = True
            if first_name and session.first_name != first_name:
                session.first_name = first_name
                updated = True
            if updated:
                session.last_active_at = datetime.utcnow()
                db.session.commit()

        return session

    @classmethod
    def get_user(cls, telegram_id: int) -> Optional[User]:
        """Returns the linked PocketPay User if authenticated"""
        session = cls.get_or_create(telegram_id)
        if session.is_authenticated:
            return session.user
        return None

    @classmethod
    def set_state(cls, telegram_id: int, state: str, data: Optional[dict] = None) -> TelegramUser:
        """Sets the current conversation state and optional state data"""
        session = cls.get_or_create(telegram_id)
        session.set_state(state, data)
        return session

    @classmethod
    def update_data(cls, telegram_id: int, **kwargs) -> TelegramUser:
        """Updates dictionary fields inside session state_data"""
        session = cls.get_or_create(telegram_id)
        session.update_state_data(**kwargs)
        return session

    @classmethod
    def clear_state(cls, telegram_id: int) -> TelegramUser:
        """Resets conversation state back to LOGGED_IN or START"""
        session = cls.get_or_create(telegram_id)
        session.clear_state()
        return session

    @classmethod
    def link_account(cls, telegram_id: int, user: User) -> TelegramUser:
        """Binds a Telegram user ID to a PocketPay User account"""
        session = cls.get_or_create(telegram_id)
        session.link_user(user)
        return session

    @classmethod
    def unlink_account(cls, telegram_id: int) -> TelegramUser:
        """Unlinks the Telegram session (Logout)"""
        session = cls.get_or_create(telegram_id)
        session.unlink_user()
        return session
