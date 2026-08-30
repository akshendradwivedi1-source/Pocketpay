"""add_telegram_fields_and_missing_columns

Revision ID: 049eebe197a5
Revises: 
Create Date: 2026-08-30 13:00:08.946059

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '049eebe197a5'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Ensure telegram_users table exists
    if 'telegram_users' not in tables:
        op.create_table(
            'telegram_users',
            sa.Column('telegram_id', sa.BigInteger(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('username', sa.String(length=128), nullable=True),
            sa.Column('first_name', sa.String(length=128), nullable=True),
            sa.Column('state', sa.String(length=64), server_default='START', nullable=False),
            sa.Column('state_data', sa.JSON(), nullable=False),
            sa.Column('notifications_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
            sa.Column('last_active_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        op.create_index('ix_telegram_users_user_id', 'telegram_users', ['user_id'])
    else:
        tg_cols = [c['name'] for c in inspector.get_columns('telegram_users')]
        with op.batch_alter_table('telegram_users', schema=None) as batch_op:
            if 'notifications_enabled' not in tg_cols:
                batch_op.add_column(sa.Column('notifications_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False))

    # 2. Ensure users table has all Telegram and security columns
    if 'users' in tables:
        user_cols = [c['name'] for c in inspector.get_columns('users')]
        with op.batch_alter_table('users', schema=None) as batch_op:
            if 'is_admin' not in user_cols:
                batch_op.add_column(sa.Column('is_admin', sa.Boolean(), server_default=sa.text('false'), nullable=True))
            if 'telegram_linking_token' not in user_cols:
                batch_op.add_column(sa.Column('telegram_linking_token', sa.String(length=64), nullable=True))
            if 'telegram_linking_token_expires_at' not in user_cols:
                batch_op.add_column(sa.Column('telegram_linking_token_expires_at', sa.DateTime(), nullable=True))
            if 'telegram_notifications_enabled' not in user_cols:
                batch_op.add_column(sa.Column('telegram_notifications_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=True))
            if 'otp_approval_token' not in user_cols:
                batch_op.add_column(sa.Column('otp_approval_token', sa.String(length=128), nullable=True))
            if 'otp_approval_status' not in user_cols:
                batch_op.add_column(sa.Column('otp_approval_status', sa.String(length=32), server_default='none', nullable=True))

        # Check for unique index on telegram_linking_token
        try:
            indexes = [ix['name'] for ix in inspector.get_indexes('users')]
            if 'ix_users_telegram_linking_token' not in indexes and 'telegram_linking_token' in (user_cols + ['telegram_linking_token']):
                op.create_index('ix_users_telegram_linking_token', 'users', ['telegram_linking_token'], unique=True)
            if 'ix_users_otp_approval_token' not in indexes and 'otp_approval_token' in (user_cols + ['otp_approval_token']):
                op.create_index('ix_users_otp_approval_token', 'users', ['otp_approval_token'], unique=False)
        except Exception:
            pass


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'users' in tables:
        user_cols = [c['name'] for c in inspector.get_columns('users')]
        with op.batch_alter_table('users', schema=None) as batch_op:
            if 'telegram_linking_token' in user_cols:
                batch_op.drop_column('telegram_linking_token')
            if 'telegram_linking_token_expires_at' in user_cols:
                batch_op.drop_column('telegram_linking_token_expires_at')
            if 'telegram_notifications_enabled' in user_cols:
                batch_op.drop_column('telegram_notifications_enabled')
