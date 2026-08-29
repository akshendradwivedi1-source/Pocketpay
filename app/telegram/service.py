import os
import logging
from datetime import datetime
import requests
from typing import Optional, Dict, Any, List, Union


logger = logging.getLogger(__name__)


class TelegramService:
    """
    Official Telegram Bot API Client.
    Communicates directly with https://api.telegram.org using HTTP requests.
    Tokens are strictly retrieved from the environment (TELEGRAM_BOT_TOKEN).
    """

    API_BASE = "https://api.telegram.org"

    @classmethod
    def get_token(cls) -> str:
        token = (os.environ.get('TELEGRAM_BOT_TOKEN') or '').strip()
        return token

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.get_token())

    @classmethod
    def _url(cls, method: str) -> str:
        token = cls.get_token()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not configured in environment")
        return f"{cls.API_BASE}/bot{token}/{method}"

    @classmethod
    def get_me(cls) -> Dict[str, Any]:
        """Gets bot profile info from Telegram API"""
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}
        try:
            res = requests.get(cls._url("getMe"), timeout=10)
            return res.json()
        except Exception as e:
            logger.error(f"[Telegram API] getMe failed: {str(e)}")
            return {"ok": False, "error": "Connection error"}

    @classmethod
    def send_message(
        cls,
        chat_id: Union[int, str],
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True
    ) -> Dict[str, Any]:
        """Sends a text message with optional inline keyboard"""
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            res = requests.post(cls._url("sendMessage"), json=payload, timeout=10)
            return res.json()
        except Exception as e:
            logger.error(f"[Telegram API] sendMessage error: {str(e)}")
            return {"ok": False, "error": "Failed to send message"}

    @classmethod
    def edit_message_text(
        cls,
        chat_id: Union[int, str],
        message_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True
    ) -> Dict[str, Any]:
        """Edits an existing text message inline"""
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            res = requests.post(cls._url("editMessageText"), json=payload, timeout=10)
            return res.json()
        except Exception as e:
            logger.error(f"[Telegram API] editMessageText error: {str(e)}")
            return {"ok": False, "error": "Failed to edit message"}

    @classmethod
    def answer_callback_query(
        cls,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False
    ) -> Dict[str, Any]:
        """Answers an inline button callback query"""
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

        payload = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert
        }
        if text:
            payload["text"] = text

        try:
            res = requests.post(cls._url("answerCallbackQuery"), json=payload, timeout=10)
            return res.json()
        except Exception as e:
            logger.error(f"[Telegram API] answerCallbackQuery error: {str(e)}")
            return {"ok": False, "error": "Failed to answer callback query"}

    @classmethod
    def send_photo(
        cls,
        chat_id: Union[int, str],
        photo: Union[str, bytes],
        caption: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        """Sends a photo/QR image to the chat"""
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

        try:
            if isinstance(photo, bytes):
                files = {"photo": ("qrcode.png", photo, "image/png")}
                data = {"chat_id": chat_id, "parse_mode": parse_mode}
                if caption:
                    data["caption"] = caption
                if reply_markup:
                    import json
                    data["reply_markup"] = json.dumps(reply_markup)
                res = requests.post(cls._url("sendPhoto"), data=data, files=files, timeout=15)
                return res.json()
            else:
                payload = {
                    "chat_id": chat_id,
                    "photo": photo,
                    "parse_mode": parse_mode
                }
                if caption:
                    payload["caption"] = caption
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                res = requests.post(cls._url("sendPhoto"), json=payload, timeout=15)
                return res.json()
        except Exception as e:
            logger.error(f"[Telegram API] sendPhoto error: {str(e)}")
            return {"ok": False, "error": "Failed to send photo"}

    @classmethod
    def get_updates(
        cls,
        offset: Optional[int] = None,
        limit: int = 100,
        timeout: int = 25
    ) -> Dict[str, Any]:
        """Long-polling update retrieval for local development"""
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

        payload = {"limit": limit, "timeout": timeout}
        if offset is not None:
            payload["offset"] = offset

        try:
            res = requests.post(cls._url("getUpdates"), json=payload, timeout=timeout + 10)
            return res.json()
        except Exception as e:
            logger.error(f"[Telegram API] getUpdates error: {str(e)}")
            return {"ok": False, "error": "Polling connection failed"}

    @classmethod
    def set_webhook(cls, url: str) -> Dict[str, Any]:
        """Sets the webhook endpoint for production"""
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

        try:
            res = requests.post(cls._url("setWebhook"), json={"url": url}, timeout=10)
            return res.json()
        except Exception as e:
            logger.error(f"[Telegram API] setWebhook error: {str(e)}")
            return {"ok": False, "error": "Failed to set webhook"}

    @classmethod
    def delete_webhook(cls, drop_pending_updates: bool = False) -> Dict[str, Any]:
        """Deletes the current webhook (enables long polling)"""
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

        try:
            res = requests.post(cls._url("deleteWebhook"), json={"drop_pending_updates": drop_pending_updates}, timeout=10)
            return res.json()
        except Exception as e:
            logger.error(f"[Telegram API] deleteWebhook error: {str(e)}")
            return {"ok": False, "error": "Failed to delete webhook"}

    @classmethod
    def get_webhook_info(cls) -> Dict[str, Any]:
        """Retrieves the current webhook status and pending updates from Telegram servers"""
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

        try:
            res = requests.get(cls._url("getWebhookInfo"), timeout=10)
            return res.json()
        except Exception as e:
            logger.error(f"[Telegram API] getWebhookInfo error: {str(e)}")
            return {"ok": False, "error": "Failed to get webhook info"}

    @classmethod
    def send_event_notification(cls, user, title: str, message: str, event_type: str = 'info') -> bool:
        """
        Sends an account event notification directly to user's linked Telegram chat.
        Checks if Telegram is configured, user has Telegram linked, and notifications are enabled.
        """
        if not cls.is_configured() or not user:
            return False

        if not getattr(user, 'telegram_notifications_enabled', True):
            return False

        try:
            from app.models.telegram_user import TelegramUser
            tg_user = TelegramUser.query.filter_by(user_id=user.id).first()
            if not tg_user or not getattr(tg_user, 'notifications_enabled', True):
                return False

            chat_id = tg_user.telegram_id
            if not chat_id:
                return False

            icons = {
                'login': '🔐',
                'security': '🛡️',
                'password': '🔑',
                'transfer': '💸',
                'income': '💰',
                'pocket': '👛',
                'warning': '⚠️',
                'success': '✅',
                'info': '🔔'
            }
            icon = icons.get(event_type, '🔔')
            formatted_text = f"{icon} <b>{title}</b>\n\n{message}\n\n<i>PocketPay Security Alert • {datetime.utcnow().strftime('%H:%M:%S UTC')}</i>"

            res = cls.send_message(chat_id, formatted_text)
            return bool(res.get('ok'))
        except Exception as e:
            logger.error(f"[Telegram Notification] Failed to dispatch event notification: {str(e)}")
            return False


