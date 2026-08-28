import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()

if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = app.config.get('DEBUG', True)
    print("""
====================================================================
              PocketPay Smart Pocket System v1.0
====================================================================
  [Info] Demo Account:
     Email: demo@pocketpay.app
     Password: Demo@123
     PIN: 1234
====================================================================
  URL: http://localhost:{:<5d}
====================================================================
""".format(port))

    # Auto-start Telegram poller in background thread if configured
    try:
        from app.telegram.poller import start_background_poller
        start_background_poller(app)
    except Exception as e:
        print(f"[Telegram] Could not auto-start poller: {e}")
        
    app.run(host=host, port=port, debug=debug, use_reloader=False)
