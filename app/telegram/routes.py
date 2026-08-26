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

    return jsonify({
        'status': 'active' if configured else 'unconfigured',
        'configured': configured,
        'bot': bot_info if configured else None,
        'webhook_url': '/telegram/webhook',
        'mode': 'webhook'
    }), 200


@bp.route('/set-webhook', methods=['GET', 'POST'])
def set_webhook():
    """
    Sets the official Telegram Bot API webhook to this server's public HTTPS URL.
    Safely utilizes server-side TELEGRAM_BOT_TOKEN without exposing it.
    """
    import os
    if not TelegramService.is_configured():
        return jsonify({'ok': False, 'error': 'Telegram bot is not configured on this server'}), 503

    explicit_url = request.args.get('url') or os.environ.get('TELEGRAM_WEBHOOK_URL')
    if explicit_url:
        webhook_url = explicit_url
    else:
        host_url = request.host_url.rstrip('/')
        if request.headers.get('X-Forwarded-Proto') == 'https' or request.is_secure:
            if host_url.startswith('http://'):
                host_url = 'https://' + host_url[7:]
        webhook_url = f"{host_url}/telegram/webhook"

    result = TelegramService.set_webhook(webhook_url)
    return jsonify({
        'ok': result.get('ok', False),
        'message': 'Webhook configured successfully' if result.get('ok') else 'Failed to configure webhook',
        'webhook_url': webhook_url,
        'telegram_response': result
    }), (200 if result.get('ok') else 400)


@bp.route('/webhook-info', methods=['GET'])
def webhook_info():
    """Returns official webhook status reported by Telegram API"""
    if not TelegramService.is_configured():
        return jsonify({'ok': False, 'error': 'Telegram bot is not configured'}), 503
    return jsonify(TelegramService.get_webhook_info())

