"""add_sessions_table

Revision ID: 20250810_add_sessions_table
Revises: b1a2c3d4e5f6_add_rag_tables
Create Date: 2025-08-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250810_add_sessions_table'
down_revision: Union[str, Sequence[str], None] = 'b1a2c3d4e5f6_add_rag_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    )
    op.create_index('ix_sessions_id', 'sessions', ['id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_sessions_id', table_name='sessions')
    op.drop_table('sessions')


