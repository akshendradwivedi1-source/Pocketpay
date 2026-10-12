"""
Gunicorn configuration for PocketPay Production Deployment on Render / Cloud.
Render automatically sets the PORT environment variable (default: 10000).
"""
import os

# Server socket binding: bind to 0.0.0.0:$PORT
port = os.environ.get('PORT', '10000')
bind = f"0.0.0.0:{port}"

# Worker processes and concurrency
# Render free tier gives 0.5 CPU / 512MB RAM, 2 workers with 4 threads is optimal
workers = int(os.environ.get('WEB_CONCURRENCY', os.environ.get('GUNICORN_WORKERS', 2)))
threads = int(os.environ.get('GUNICORN_THREADS', 4))
worker_class = os.environ.get('GUNICORN_WORKER_CLASS', 'gthread')

# Worker lifetime and timeout
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 120))
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', 5))
graceful_timeout = int(os.environ.get('GUNICORN_GRACEFUL_TIMEOUT', 30))

# Logging: Stream directly to stdout/stderr for Render live logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get('LOG_LEVEL', 'info')
capture_output = True

# Process naming
proc_name = "pocketpay"
