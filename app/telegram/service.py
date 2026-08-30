import os
import re
import logging
from datetime import datetime
import requests
from typing import Optional, Dict, Any, List, Union


logger = logging.getLogger(__name__)


class TelegramService:
    """
    Official Telegram Bot API Client for PocketPay.
    Communicates securely with https://api.telegram.org using HTTP requests.
    Tokens are strictly retrieved from the environment variables (TELEGRAM_BOT_TOKEN).
    """

    API_BASE = "https://api.telegram.org"

    @classmethod
    def get_token(cls) -> str:
        """Retrieves and normalizes the bot token from environment variables"""
        token = (
            os.environ.get('TELEGRAM_BOT_TOKEN') or
            os.environ.get('TELEGRAM_TOKEN') or
            os.environ.get('BOT_TOKEN') or
            ''
        ).strip()
        return token

    @classmethod
    def get_masked_token(cls) -> str:
        """Returns a safe masked version of the token for logging / diagnostics"""
        tok = cls.get_token()
        if not tok or len(tok) < 10:
            return "[NOT CONFIGURED]"
        return f"{tok[:6]}...{tok[-4:]}"

    @classmethod
    def is_configured(cls) -> bool:
        """Returns True if a valid token is set in environment"""
        return bool(cls.get_token())

    @classmethod
    def get_admin_chat_ids(cls) -> List[Union[int, str]]:
        """Retrieves configured admin chat IDs from environment and database"""
        chat_ids = []
        # Direct environment variables
        for env_key in ('TELEGRAM_ADMIN_CHAT_ID', 'TELEGRAM_CHAT_ID', 'ADMIN_CHAT_ID'):
            val = os.environ.get(env_key)
            if val:
                for item in str(val).split(','):
                    item = item.strip()
                    if item and item not in chat_ids:
                        chat_ids.append(item)

        # Database admin users with linked telegram
        try:
            from app.models.user import User
            from app.models.telegram_user import TelegramUser
            admins = User.query.filter_by(is_admin=True).all()
            for admin in admins:
                tg_u = TelegramUser.query.filter_by(user_id=admin.id).first()
                if tg_u and tg_u.telegram_id and str(tg_u.telegram_id) not in chat_ids:
                    chat_ids.append(str(tg_u.telegram_id))
        except Exception:
            pass

        return chat_ids

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
            logger.error(f"[Telegram API] getMe connection error: {str(e)}")
            return {"ok": False, "error": f"Connection error: {str(e)}"}

    @classmethod
    def send_message(
        cls,
        chat_id: Union[int, str],
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = "HTML",
        disable_web_page_preview: bool = True
    ) -> Dict[str, Any]:
        """
        Sends a text message with optional inline keyboard.
        Includes automatic fallback if HTML parse formatting fails.
        """
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            res = requests.post(cls._url("sendMessage"), json=payload, timeout=12)
            data = res.json()
            # If HTML parsing failed, retry sending plain text
            if not data.get("ok") and parse_mode == "HTML" and "parse" in str(data.get("description", "")).lower():
                plain_text = re.sub(r'<[^>]+>', '', text)
                payload["text"] = plain_text
                payload.pop("parse_mode", None)
                retry_res = requests.post(cls._url("sendMessage"), json=payload, timeout=12)
                return retry_res.json()
            return data
        except Exception as e:
            logger.error(f"[Telegram API] sendMessage error: {str(e)}")
            return {"ok": False, "error": f"Failed to send message: {str(e)}"}

    @classmethod
    def edit_message_text(
        cls,
        chat_id: Union[int, str],
        message_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = "HTML",
        disable_web_page_preview: bool = True
    ) -> Dict[str, Any]:
        """Edits an existing text message inline with HTML fallback"""
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            res = requests.post(cls._url("editMessageText"), json=payload, timeout=10)
            data = res.json()
            if not data.get("ok") and parse_mode == "HTML" and "parse" in str(data.get("description", "")).lower():
                plain_text = re.sub(r'<[^>]+>', '', text)
                payload["text"] = plain_text
                payload.pop("parse_mode", None)
                retry_res = requests.post(cls._url("editMessageText"), json=payload, timeout=10)
                return retry_res.json()
            return data
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
            res = requests.post(cls._url("answerCallbackQuery"), json=payload, timeout=8)
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
        parse_mode: Optional[str] = "HTML"
    ) -> Dict[str, Any]:
        """Sends a photo/QR image to the chat with error recovery"""
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

        try:
            if isinstance(photo, bytes):
                files = {"photo": ("qrcode.png", photo, "image/png")}
                data = {"chat_id": chat_id}
                if parse_mode:
                    data["parse_mode"] = parse_mode
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
                    "photo": photo
                }
                if parse_mode:
                    payload["parse_mode"] = parse_mode
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
    def set_webhook(cls, url: str, drop_pending_updates: bool = False) -> Dict[str, Any]:
        """
        Sets the webhook endpoint for production with URL normalization.
        Ensures HTTPS and correct /telegram/webhook route.
        """
        if not cls.is_configured():
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

        url = url.strip()
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'https://' + url
        elif url.startswith('http://'):
            url = 'https://' + url[7:]

        if not url.endswith('/telegram/webhook') and not url.endswith('/webhook'):
            url = f"{url.rstrip('/')}/telegram/webhook"

        payload = {
            "url": url,
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": drop_pending_updates
        }
        try:
            res = requests.post(cls._url("setWebhook"), json=payload, timeout=15)
            data = res.json()
            if data.get('ok'):
                logger.info(f"[Telegram Webhook] Successfully set webhook to {url}")
            else:
                logger.warning(f"[Telegram Webhook] Failed to set webhook: {data.get('description')}")
            return data
        except Exception as e:
            logger.error(f"[Telegram API] setWebhook error: {str(e)}")
            return {"ok": False, "error": f"Failed to set webhook: {str(e)}"}

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

    @classmethod
    def send_admin_notification(cls, title: str, message: str, event_type: str = 'info') -> bool:
        """
        Dispatches high-priority system/admin notification to all configured admin Telegram chats.
        """
        if not cls.is_configured():
            return False

        admin_chat_ids = cls.get_admin_chat_ids()
        if not admin_chat_ids:
            return False

        icons = {
            'admin_otp': '🔐',
            'security': '🛡️',
            'login': '👤',
            'payout': '💸',
            'warning': '⚠️',
            'success': '✅',
            'info': '🔔'
        }
        icon = icons.get(event_type, '🔔')
        formatted_text = f"{icon} <b>[ADMIN ALERT] {title}</b>\n\n{message}\n\n<i>PocketPay Admin • {datetime.utcnow().strftime('%H:%M:%S UTC')}</i>"

        dispatched = False
        for chat_id in admin_chat_ids:
            try:
                res = cls.send_message(chat_id, formatted_text)
                if res.get('ok'):
                    dispatched = True
            except Exception as e:
                logger.error(f"[Telegram Admin Alert] Failed to send to {chat_id}: {str(e)}")

        return dispatched
