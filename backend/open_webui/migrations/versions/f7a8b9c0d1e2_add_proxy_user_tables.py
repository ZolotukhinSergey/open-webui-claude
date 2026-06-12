"""Add proxy_user_config and proxy_usage_log tables

Revision ID: f7a8b9c0d1e2
Revises: a5c220713937
Create Date: 2026-06-11 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'a5c220713937'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'proxy_user_config' not in existing_tables:
        op.create_table(
            'proxy_user_config',
            sa.Column('user_id', sa.String(), nullable=False, primary_key=True),
            sa.Column('api_key', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
            sa.Column('hourly_token_limit', sa.BigInteger(), nullable=True),
            sa.Column('three_hourly_token_limit', sa.BigInteger(), nullable=True),
            sa.Column('daily_token_limit', sa.BigInteger(), nullable=True),
            sa.Column('weekly_token_limit', sa.BigInteger(), nullable=True),
            sa.Column('monthly_token_limit', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=True),
            sa.Column('updated_at', sa.BigInteger(), nullable=True),
        )

    if 'proxy_usage_log' not in existing_tables:
        op.create_table(
            'proxy_usage_log',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('model', sa.String(), nullable=True),
            sa.Column('prompt_tokens', sa.BigInteger(), nullable=True, server_default='0'),
            sa.Column('completion_tokens', sa.BigInteger(), nullable=True, server_default='0'),
            sa.Column('total_tokens', sa.BigInteger(), nullable=True, server_default='0'),
            sa.Column('files_sent', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('created_at', sa.BigInteger(), nullable=True),
        )
        op.create_index('ix_proxy_usage_log_user_id', 'proxy_usage_log', ['user_id'])
        op.create_index('ix_proxy_usage_log_created_at', 'proxy_usage_log', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_proxy_usage_log_created_at', table_name='proxy_usage_log')
    op.drop_index('ix_proxy_usage_log_user_id', table_name='proxy_usage_log')
    op.drop_table('proxy_usage_log')
    op.drop_table('proxy_user_config')
