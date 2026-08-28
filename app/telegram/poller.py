import time
import signal
import sys
import threading
import logging
from app.telegram.service import TelegramService
from app.telegram.handlers import TelegramHandler

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [PocketPay Telegram Poller] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

_poller_thread = None
_poller_running = False


def _polling_loop(app):
    global _poller_running
    with app.app_context():
        if not TelegramService.is_configured():
            logger.info("Telegram Bot Token is not configured. Poller inactive.")
            _poller_running = False
            return

        me = TelegramService.get_me()
        if not me.get('ok'):
            logger.warning(f"Telegram Bot API connection issue: {me.get('error', 'Unknown')}")
            _poller_running = False
            return

        bot_username = me.get('result', {}).get('username', 'PocketPayBot')
        logger.info(f"✓ Telegram Poller started successfully for @{bot_username}")

        # Clear any existing webhook to enable long-polling
        TelegramService.delete_webhook(drop_pending_updates=False)

        last_update_id = None

        while _poller_running:
            try:
                res = TelegramService.get_updates(offset=last_update_id, timeout=15)
                if not res.get("ok"):
                    time.sleep(2)
                    continue

                updates = res.get("result", [])
                for upd in updates:
                    upd_id = upd.get("update_id")
                    if last_update_id is None or upd_id >= last_update_id:
                        last_update_id = upd_id + 1

                    try:
                        TelegramHandler.handle_update(upd)
                    except Exception as e:
                        logger.error(f"Error handling update #{upd_id}: {str(e)}")

            except Exception as e:
                if _poller_running:
                    logger.warning(f"Telegram polling loop glitch (will retry): {str(e)}")
                    time.sleep(3)


def start_background_poller(app):
    """Starts Telegram polling in a non-blocking daemon thread within the Flask app lifecycle"""
    global _poller_thread, _poller_running
    if _poller_thread and _poller_thread.is_alive():
        return
    if not TelegramService.is_configured():
        return

    _poller_running = True
    _poller_thread = threading.Thread(target=_polling_loop, args=(app,), daemon=True, name="TelegramPollerThread")
    _poller_thread.start()
    logger.info("Spawned Telegram Bot Poller daemon thread.")


def run_polling():
    """
    Runs the Telegram Bot Long-Polling runner for standalone execution.
    Usage: python run_bot.py
    """
    from app import create_app
    app = create_app()
    global _poller_running
    _poller_running = True

    def signal_handler(sig, frame):
        global _poller_running
        logger.info("Stopping Telegram polling runner...")
        _poller_running = False
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    _polling_loop(app)


if __name__ == "__main__":
    run_polling()

