import os
from flask import Flask
from .config import config
from .extensions import db, login_manager, migrate, mail, cors


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    app = Flask(__name__, 
                template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    app.config.from_object(config[config_name])
    
    os.makedirs(app.instance_path, exist_ok=True)
    
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None
    
    from app.blueprints.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.blueprints.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.blueprints.pockets import bp as pockets_bp
    app.register_blueprint(pockets_bp, url_prefix='/api/pockets')
    
    from app.blueprints.wallet import bp as wallet_bp
    app.register_blueprint(wallet_bp, url_prefix='/api/wallet')
    
    from app.blueprints.transactions import bp as transactions_bp
    app.register_blueprint(transactions_bp, url_prefix='/api/transactions')
    
    from app.blueprints.analytics import bp as analytics_bp
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    
    from app.blueprints.payouts import bp as payouts_bp
    app.register_blueprint(payouts_bp, url_prefix='/api/payouts')
    
    from app.blueprints.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    from app.telegram.routes import bp as telegram_bp
    app.register_blueprint(telegram_bp, url_prefix='/telegram')
    
    from app.blueprints.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    from app.blueprints.qr import bp as qr_bp
    app.register_blueprint(qr_bp, url_prefix='/qr')
    
    with app.app_context():
        from sqlalchemy import inspect, text
        db.create_all()
        try:
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            if 'users' in tables:
                columns = [c['name'] for c in inspector.get_columns('users')]
                with db.engine.connect() as conn:
                    if 'is_admin' not in columns:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                    if 'telegram_linking_token' not in columns:
                        conn.execute(text("ALTER TABLE users ADD COLUMN telegram_linking_token VARCHAR(64)"))
                    if 'telegram_linking_token_expires_at' not in columns:
                        conn.execute(text("ALTER TABLE users ADD COLUMN telegram_linking_token_expires_at DATETIME"))
                    if 'telegram_notifications_enabled' not in columns:
                        conn.execute(text("ALTER TABLE users ADD COLUMN telegram_notifications_enabled BOOLEAN DEFAULT 1"))
                    conn.commit()
            if 'telegram_users' in tables:
                tg_columns = [c['name'] for c in inspector.get_columns('telegram_users')]
                with db.engine.connect() as conn:
                    if 'notifications_enabled' not in tg_columns:
                        conn.execute(text("ALTER TABLE telegram_users ADD COLUMN notifications_enabled BOOLEAN DEFAULT 1"))
                    conn.commit()
        except Exception:
            pass

        if config_name != 'testing':
            from app.seeds import seed_database_if_empty
            seed_database_if_empty()

            # Non-blocking Telegram webhook synchronization on production startup
            if os.environ.get('TELEGRAM_WEBHOOK_URL') or os.environ.get('RENDER_EXTERNAL_URL'):
                try:
                    from app.telegram.service import TelegramService
                    TelegramService.auto_sync_webhook_async(app)
                except Exception:
                    pass
    
    return app


# WSGI application instance export for 'gunicorn app:app'
app = create_app()

