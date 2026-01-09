"""add_circles_and_memberships

Revision ID: 58c88e7c6900
Revises: d4656325404a
Create Date: 2025-08-08 22:43:22.090775

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58c88e7c6900'
down_revision: Union[str, Sequence[str], None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create circles table
    op.create_table(
        'circles',
        sa.Column('id', sa.Integer(), primary_key=True, index=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    # Note: index on 'id' is automatically created by index=True above

    # Create circle_memberships table
    op.create_table(
        'circle_memberships',
        sa.Column('id', sa.Integer(), primary_key=True, index=True, nullable=False),
        sa.Column('circle_id', sa.Integer(), sa.ForeignKey('circles.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=True),
    )
    # Note: index on 'id' is automatically created by index=True above


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('circle_memberships')
    op.drop_table('circles')
