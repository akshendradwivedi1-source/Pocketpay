"""
PocketPay Production WSGI Application Entry Point
Used by Gunicorn, uWSGI, and cloud platforms (Render, Railway, Heroku, AWS).
"""
import os
import sys
from dotenv import load_dotenv

# Load .env variables if present (local fallback)
load_dotenv()

# Ensure application directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

# Create the master production WSGI application
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    app.run(host=host, port=port)
