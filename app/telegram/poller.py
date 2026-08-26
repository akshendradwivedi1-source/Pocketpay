import time
import signal
import sys
import logging
from app import create_app
from app.telegram.service import TelegramService
from app.telegram.handlers import TelegramHandler

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [PocketPay Telegram Poller] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def run_polling():
    """
    Runs the Telegram Bot Long-Polling runner for local development and testing.
    Does not require any public HTTPS tunnel or webhook registration.
    """
    app = create_app()
    with app.app_context():
        if not TelegramService.is_configured():
            logger.error("TELEGRAM_BOT_TOKEN is not set in environment or .env file.")
            logger.info("Please add TELEGRAM_BOT_TOKEN=your_token to your .env file and restart.")
            sys.exit(1)

        me = TelegramService.get_me()
        if not me.get('ok'):
            logger.error(f"Failed to connect to Telegram Bot API: {me.get('description', 'Unknown error')}")
            sys.exit(1)

        bot_username = me.get('result', {}).get('username', 'PocketPayBot')
        logger.info("=" * 60)
        logger.info(f" PocketPay Telegram Bot Poller Active: @{bot_username}")
        logger.info(" Ready to receive messages, commands, and transfers.")
        logger.info(" Press Ctrl+C to stop.")
        logger.info("=" * 60)

        # Clear any existing webhook to enable long-polling
        TelegramService.delete_webhook(drop_pending_updates=False)

        last_update_id = None
        running = True

        def signal_handler(sig, frame):
            nonlocal running
            logger.info("Stopping Telegram polling runner...")
            running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        while running:
            try:
                res = TelegramService.get_updates(offset=last_update_id, timeout=25)
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
                if running:
                    logger.warning(f"Polling loop exception: {str(e)}")
                    time.sleep(3)


if __name__ == "__main__":
    run_polling()
