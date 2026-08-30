"""
PocketPay Application Entry Point for Gunicorn & Cloud Deployments (Render, Railway, Heroku).
Guarantees full compatibility when Gunicorn is executed as:
- 'gunicorn app:app'
- 'gunicorn wsgi:app'
- 'gunicorn run:app'
"""
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wsgi import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    app.run(host=host, port=port)
