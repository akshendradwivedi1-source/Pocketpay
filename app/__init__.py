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

    from app.blueprints.premium import bp as premium_bp
    app.register_blueprint(premium_bp, url_prefix='/api/premium')

    # =========================================================================
    # GLOBAL API ERROR HANDLERS (Guarantees JSON responses for API/Auth routes)
    # =========================================================================
    from flask import jsonify, request

    def is_api_request():
        return (
            request.path.startswith('/api/') or
            request.path.startswith('/auth/') or
            request.path.startswith('/admin/api/') or
            request.is_json or
            'application/json' in request.headers.get('Accept', '')
        )

    @app.errorhandler(400)
    def handle_bad_request(e):
        if is_api_request():
            msg = getattr(e, 'description', None) or 'Bad Request'
            return jsonify({'success': False, 'message': str(msg), 'code': 'BAD_REQUEST'}), 400
        return e

    @app.errorhandler(401)
    def handle_unauthorized(e):
        if is_api_request():
            return jsonify({'success': False, 'message': 'Authentication required. Please log in.', 'code': 'UNAUTHORIZED'}), 401
        return e

    @app.errorhandler(403)
    def handle_forbidden(e):
        if is_api_request():
            return jsonify({'success': False, 'message': 'Access forbidden. You do not have permission for this action.', 'code': 'FORBIDDEN'}), 403
        return e

    @app.errorhandler(404)
    def handle_not_found(e):
        if is_api_request():
            return jsonify({'success': False, 'message': 'Requested API endpoint or resource not found.', 'code': 'NOT_FOUND'}), 404
        return e

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        if is_api_request():
            return jsonify({'success': False, 'message': 'Method not allowed for this endpoint.', 'code': 'METHOD_NOT_ALLOWED'}), 405
        return e

    @app.errorhandler(429)
    def handle_too_many_requests(e):
        if is_api_request():
            return jsonify({'success': False, 'message': 'Too many requests. Please try again later.', 'code': 'RATE_LIMITED'}), 429
        return e

    @app.errorhandler(500)
    def handle_server_error(e):
        if is_api_request():
            app.logger.error(f"[Unhandled Server Error on {request.path}] {e}")
            return jsonify({'success': False, 'message': 'Internal server error. Please try again later.', 'code': 'SERVER_ERROR'}), 500
        return e
    
    with app.app_context():
        from sqlalchemy import inspect, text
        db.create_all()

        # 1. Run Alembic migrations automatically on startup (skip in testing mode)
        if config_name != 'testing':
            try:
                from flask_migrate import upgrade as flask_migrate_upgrade
                flask_migrate_upgrade()
            except Exception as e:
                app.logger.debug(f"[Alembic Upgrade Info] {e}")

        # 2. Database-agnostic schema sync fallback (guarantees columns exist on PostgreSQL, SQLite, MySQL)
        try:
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            is_postgres = db.engine.dialect.name.lower().startswith('postgres')

            bool_false = "BOOLEAN DEFAULT FALSE" if is_postgres else "BOOLEAN DEFAULT 0"
            bool_true = "BOOLEAN DEFAULT TRUE" if is_postgres else "BOOLEAN DEFAULT 1"
            datetime_type = "TIMESTAMP" if is_postgres else "DATETIME"

            if 'users' in tables:
                columns = [c['name'] for c in inspector.get_columns('users')]
                alter_statements = []
                if 'is_admin' not in columns:
                    alter_statements.append(f"ALTER TABLE users ADD COLUMN is_admin {bool_false}")
                if 'security_version' not in columns:
                    alter_statements.append("ALTER TABLE users ADD COLUMN security_version INTEGER DEFAULT 1")
                if 'telegram_linking_token' not in columns:
                    alter_statements.append("ALTER TABLE users ADD COLUMN telegram_linking_token VARCHAR(64)")
                if 'telegram_linking_token_expires_at' not in columns:
                    alter_statements.append(f"ALTER TABLE users ADD COLUMN telegram_linking_token_expires_at {datetime_type}")
                if 'telegram_notifications_enabled' not in columns:
                    alter_statements.append(f"ALTER TABLE users ADD COLUMN telegram_notifications_enabled {bool_true}")
                if 'otp_approval_token' not in columns:
                    alter_statements.append("ALTER TABLE users ADD COLUMN otp_approval_token VARCHAR(128)")
                if 'otp_approval_status' not in columns:
                    alter_statements.append("ALTER TABLE users ADD COLUMN otp_approval_status VARCHAR(32) DEFAULT 'none'")
                if 'security_setup_completed' not in columns:
                    alter_statements.append(f"ALTER TABLE users ADD COLUMN security_setup_completed {bool_false}")
                if 'deleted_at' not in columns:
                    alter_statements.append(f"ALTER TABLE users ADD COLUMN deleted_at {datetime_type}")
                if 'transfer_frozen' not in columns:
                    alter_statements.append(f"ALTER TABLE users ADD COLUMN transfer_frozen {bool_false}")
                if 'transaction_limit' not in columns:
                    alter_statements.append("ALTER TABLE users ADD COLUMN transaction_limit FLOAT DEFAULT 50000.0")

                for stmt in alter_statements:
                    try:
                        with db.engine.begin() as conn:
                            conn.execute(text(stmt))
                    except Exception as col_err:
                        app.logger.debug(f"[Schema Sync] Notice on '{stmt}': {col_err}")

            try:
                db.create_all()
            except Exception:
                pass

            if 'telegram_users' in tables:
                tg_columns = [c['name'] for c in inspector.get_columns('telegram_users')]
                if 'notifications_enabled' not in tg_columns:
                    try:
                        with db.engine.begin() as conn:
                            conn.execute(text(f"ALTER TABLE telegram_users ADD COLUMN notifications_enabled {bool_true}"))
                    except Exception:
                        pass

            if 'transactions' in tables:
                tx_columns = [c['name'] for c in inspector.get_columns('transactions')]
                tx_alter = []
                if 'source_type' not in tx_columns:
                    tx_alter.append("ALTER TABLE transactions ADD COLUMN source_type VARCHAR(32)")
                if 'destination_type' not in tx_columns:
                    tx_alter.append("ALTER TABLE transactions ADD COLUMN destination_type VARCHAR(32)")
                if 'source_id' not in tx_columns:
                    tx_alter.append("ALTER TABLE transactions ADD COLUMN source_id VARCHAR(64)")
                if 'destination_id' not in tx_columns:
                    tx_alter.append("ALTER TABLE transactions ADD COLUMN destination_id VARCHAR(64)")
                if 'reference_id' not in tx_columns:
                    tx_alter.append("ALTER TABLE transactions ADD COLUMN reference_id VARCHAR(128)")
                if 'failure_reason' not in tx_columns:
                    tx_alter.append("ALTER TABLE transactions ADD COLUMN failure_reason VARCHAR(255)")
                if is_postgres and 'qr_code_url' in tx_columns:
                    tx_alter.append("ALTER TABLE transactions ALTER COLUMN qr_code_url TYPE TEXT")

                for stmt in tx_alter:
                    try:
                        with db.engine.begin() as conn:
                            conn.execute(text(stmt))
                    except Exception:
                        pass

            if 'money_requests' in tables:
                mr_columns = [c['name'] for c in inspector.get_columns('money_requests')]
                mr_alter = []
                if 'expires_at' not in mr_columns:
                    mr_alter.append(f"ALTER TABLE money_requests ADD COLUMN expires_at {datetime_type}")
                if 'target_pocket_id' not in mr_columns:
                    mr_alter.append("ALTER TABLE money_requests ADD COLUMN target_pocket_id INTEGER")
                for stmt in mr_alter:
                    try:
                        with db.engine.begin() as conn:
                            conn.execute(text(stmt))
                    except Exception:
                        pass

            if 'idempotency_records' not in tables:
                try:
                    db.create_all()
                except Exception:
                    pass
        except Exception as e:
            app.logger.debug(f"[Schema Sync Exception] {e}")

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

