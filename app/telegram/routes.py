import os
import logging
from flask import Blueprint, request, jsonify
from .service import TelegramService
from .handlers import TelegramHandler

logger = logging.getLogger(__name__)

bp = Blueprint('telegram', __name__)


@bp.route('/webhook', methods=['POST'])
def telegram_webhook():
    """
    Official Telegram Bot API Webhook Endpoint.
    Receives JSON update payloads from Telegram servers and delegates to TelegramHandler.
    """
    if not TelegramService.is_configured():
        return jsonify({'status': 'error', 'message': 'Telegram bot is not configured'}), 503

    update = request.get_json(silent=True, force=True)
    if not update:
        return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400

    try:
        TelegramHandler.handle_update(update)
        return jsonify({'ok': True}), 200
    except Exception as e:
        logger.error(f"[Telegram Webhook] Handler error: {str(e)}", exc_info=False)
        return jsonify({'ok': True}), 200  # Return 200 to Telegram to prevent retry loops


@bp.route('/status', methods=['GET'])
def telegram_status():
    """Returns the current configuration and operational status of the Telegram Bot"""
    configured = TelegramService.is_configured()
    bot_info = {}
    webhook_status = {}
    
    if configured:
        me = TelegramService.get_me()
        if me.get('ok'):
            bot_info = {
                'id': me.get('result', {}).get('id'),
                'username': me.get('result', {}).get('username'),
                'first_name': me.get('result', {}).get('first_name'),
                'can_join_groups': me.get('result', {}).get('can_join_groups'),
                'can_read_all_group_messages': me.get('result', {}).get('can_read_all_group_messages'),
                'supports_inline_queries': me.get('result', {}).get('supports_inline_queries')
            }
        wh = TelegramService.get_webhook_info()
        if wh.get('ok'):
            webhook_status = wh.get('result', {})

    return jsonify({
        'status': 'active' if configured else 'unconfigured',
        'configured': configured,
        'mode': 'webhook',
        'token_masked': TelegramService.get_masked_token(),
        'bot': bot_info if configured else None,
        'webhook': webhook_status if configured else None,
        'webhook_url': '/telegram/webhook',
        'admin_chat_ids_count': len(TelegramService.get_admin_chat_ids())
    }), 200


@bp.route('/set-webhook', methods=['GET', 'POST'])
def set_webhook():
    """
    Sets the official Telegram Bot API webhook to this server's public HTTPS URL.
    Auto-detects Render live deployment URL (RENDER_EXTERNAL_URL) or TELEGRAM_WEBHOOK_URL.
    Safely utilizes server-side TELEGRAM_BOT_TOKEN without exposing it.
    """
    if not TelegramService.is_configured():
        return jsonify({'ok': False, 'error': 'Telegram bot is not configured on this server'}), 503

    explicit_url = (
        request.args.get('url') or
        (request.get_json(silent=True) or {}).get('url') or
        request.form.get('url') or
        os.environ.get('TELEGRAM_WEBHOOK_URL') or
        os.environ.get('RENDER_EXTERNAL_URL')
    )

    if explicit_url:
        target_url = explicit_url.strip()
    else:
        host_url = request.host_url.rstrip('/')
        if request.headers.get('X-Forwarded-Proto') == 'https' or request.is_secure:
            if host_url.startswith('http://'):
                host_url = 'https://' + host_url[7:]
        target_url = f"{host_url}/telegram/webhook"

    result = TelegramService.set_webhook(target_url)
    return jsonify({
        'ok': result.get('ok', False),
        'message': 'Webhook configured successfully' if result.get('ok') else 'Failed to configure webhook',
        'webhook_url': target_url,
        'telegram_response': result
    }), (200 if result.get('ok') else 400)


@bp.route('/delete-webhook', methods=['GET', 'POST'])
def delete_webhook():
    """Deletes the current webhook (useful for local development or polling switch)"""
    if not TelegramService.is_configured():
        return jsonify({'ok': False, 'error': 'Telegram bot is not configured'}), 503

    result = TelegramService.delete_webhook()
    return jsonify({
        'ok': result.get('ok', False),
        'message': 'Webhook deleted successfully' if result.get('ok') else 'Failed to delete webhook',
        'telegram_response': result
    }), (200 if result.get('ok') else 400)


@bp.route('/webhook-info', methods=['GET'])
def webhook_info():
    """Returns official webhook status reported by Telegram API"""
    if not TelegramService.is_configured():
        return jsonify({'ok': False, 'error': 'Telegram bot is not configured'}), 503
    return jsonify(TelegramService.get_webhook_info())


@bp.route('/test-notification', methods=['GET', 'POST'])
def test_notification():
    """
    Sends a test notification to a specific Telegram chat_id or configured admin chats.
    Usage:
      GET /telegram/test-notification?chat_id=<id>&message=<msg>
      POST /telegram/test-notification with JSON { "chat_id": 12345, "message": "Test" }
    """
    if not TelegramService.is_configured():
        return jsonify({'ok': False, 'error': 'Telegram bot is not configured'}), 503

    data = request.get_json(silent=True) or {}
    chat_id = request.args.get('chat_id') or data.get('chat_id')
    custom_msg = request.args.get('message') or data.get('message') or 'This is a test notification from your PocketPay server.'

    if chat_id:
        text = f"🔔 <b>PocketPay Notification Test</b>\n\n{custom_msg}\n\n✅ <i>Telegram Bot API is fully functional.</i>"
        res = TelegramService.send_message(chat_id, text)
        return jsonify({
            'ok': res.get('ok', False),
            'chat_id': chat_id,
            'response': res
        }), (200 if res.get('ok') else 400)
    else:
        # Send to admin chats
        admin_dispatched = TelegramService.send_admin_notification(
            title="Notification Test",
            message=custom_msg,
            event_type='info'
        )
        return jsonify({
            'ok': admin_dispatched,
            'message': 'Test alert dispatched to admin chats' if admin_dispatched else 'No chat_id provided and no admin chats configured. Pass ?chat_id=<your_telegram_id> to test direct delivery.',
            'admin_chat_ids': TelegramService.get_admin_chat_ids()
        }), (200 if admin_dispatched else 200)
