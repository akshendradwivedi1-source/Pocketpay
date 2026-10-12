import os
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Explicitly anchor to PocketPay's own .env file to prevent environment bleed
pp_env_path = os.path.abspath(os.path.join(BASE_DIR, '..', '.env'))
if os.path.exists(pp_env_path):
    load_dotenv(pp_env_path, override=False)
else:
    load_dotenv(override=False)


def get_database_uri():
    instance_dir = os.path.abspath(os.path.join(BASE_DIR, '..', 'instance'))
    os.makedirs(instance_dir, exist_ok=True)
    raw_url = (os.environ.get('DATABASE_URL') or '').strip()
    if raw_url and '://' in raw_url:
        if raw_url.startswith('postgres://'):
            raw_url = raw_url.replace('postgres://', 'postgresql://', 1)
        if raw_url.startswith('postgresql://'):
            if 'sslmode=' not in raw_url and 'localhost' not in raw_url and '127.0.0.1' not in raw_url:
                separator = '&' if '?' in raw_url else '?'
                raw_url = f"{raw_url}{separator}sslmode=prefer"
            return raw_url
        if raw_url.startswith('sqlite:///'):
            db_name = os.path.basename(raw_url[len('sqlite:///'):])
            if not db_name or 'travelease' in db_name.lower():
                db_name = 'pocketpay.db'
            return 'sqlite:///' + os.path.join(instance_dir, db_name).replace('\\', '/')
        return raw_url
    return 'sqlite:///' + os.path.join(instance_dir, 'pocketpay.db').replace('\\', '/')



def get_mail_port():
    try:
        return int(os.environ.get('MAIL_PORT') or 587)
    except (ValueError, TypeError):
        return 587


class Config:
    # 1. Core Secret Key
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 2. Database Configuration
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # 3. Email (Transactional HTTP APIs & Flask-Mail SMTP) Configuration
    EMAIL_PROVIDER = (os.environ.get('EMAIL_PROVIDER') or 'auto').strip().lower()
    RESEND_API_KEY = (os.environ.get('RESEND_API_KEY') or '').strip()
    BREVO_API_KEY = (os.environ.get('BREVO_API_KEY') or os.environ.get('SENDINBLUE_API_KEY') or '').strip()
    SENDGRID_API_KEY = (os.environ.get('SENDGRID_API_KEY') or '').strip()
    MAILGUN_API_KEY = (os.environ.get('MAILGUN_API_KEY') or '').strip()
    MAILGUN_DOMAIN = (os.environ.get('MAILGUN_DOMAIN') or '').strip()
    
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = get_mail_port()
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').strip().lower() in ('true', '1', 'yes', 't')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').strip().lower() in ('true', '1', 'yes', 't')
    MAIL_USERNAME = (os.environ.get('MAIL_USERNAME') or '').strip()
    MAIL_PASSWORD = (os.environ.get('MAIL_PASSWORD') or '').strip()
    MAIL_DEFAULT_SENDER = (os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@pocketpay.app').strip()
    
    # 4. Security, Admin & Sessions
    POCKETPAY_ADMIN_EMAIL = (
        os.environ.get('POCKETPAY_ADMIN_EMAIL') or
        os.environ.get('ADMIN_EMAIL') or
        os.environ.get('MAIL_USERNAME') or
        'akshendra.dwivedi1@gmail.com'
    ).strip().lower()
    
    WTF_CSRF_ENABLED = False
    OTP_EXPIRY_MINUTES = int(os.environ.get('OTP_EXPIRY_MINUTES', 5))
    PIN_ATTEMPTS_LIMIT = int(os.environ.get('PIN_ATTEMPTS_LIMIT', 5))
    PIN_LOCKOUT_MINUTES = int(os.environ.get('PIN_LOCKOUT_MINUTES', 15))
    
    # 5. Payment Gateways (Razorpay & Partner Integrations)
    RAZORPAY_KEY_ID = (os.environ.get('RAZORPAY_KEY_ID') or '').strip()
    RAZORPAY_KEY_SECRET = (os.environ.get('RAZORPAY_KEY_SECRET') or '').strip()
    RAZORPAY_WEBHOOK_SECRET = (os.environ.get('RAZORPAY_WEBHOOK_SECRET') or '').strip()
    POCKETPAY_PARTNER_API_KEY = (os.environ.get('POCKETPAY_PARTNER_API_KEY') or 'travelease_service_key_live_99812').strip()
    TRAVELEASE_API_URL = (os.environ.get('TRAVELEASE_API_URL') or 'http://127.0.0.1:5000').strip()
    TRAVELEASE_API_KEY = (os.environ.get('TRAVELEASE_API_KEY') or 'travelease_service_key_live_99812').strip()

    # 6. PocketPay AI Assistant (OpenAI Integration)
    OPENAI_API_KEY = (os.environ.get('OPENAI_API_KEY') or '').strip()
    OPENAI_MODEL = (os.environ.get('OPENAI_MODEL') or 'gpt-4o-mini').strip()

    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    JSON_SORT_KEYS = False


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
