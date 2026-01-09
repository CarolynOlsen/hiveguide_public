"""Add login event logging table

Revision ID: 1edce0f2f460
Revises: 20250831_add_inspection_date
Create Date: 2025-10-06 14:20:18.348085

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1edce0f2f460'
down_revision: Union[str, Sequence[str], None] = '20250831_add_inspection_date'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('login_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('platform', sa.String(), nullable=False),
    sa.Column('success', sa.Boolean(), nullable=False),
    sa.Column('ip_address', sa.String(), nullable=True),
    sa.Column('user_agent', sa.String(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('failure_reason', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_login_events_id'), 'login_events', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_login_events_id'), table_name='login_events')
    op.drop_table('login_events')
