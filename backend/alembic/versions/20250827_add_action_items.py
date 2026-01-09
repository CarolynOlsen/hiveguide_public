"""Add action items support to inspections and hives

Revision ID: 20250827_add_action_items
Revises: 20250813_resize_embedding_vector_3072
Create Date: 2025-08-27 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250827_add_action_items'
down_revision: Union[str, Sequence[str], None] = '9f2a1b7c2d34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add action_items and action_due_date columns to inspections table
    op.add_column('inspections', sa.Column('action_items', sa.JSON(), nullable=True))
    op.add_column('inspections', sa.Column('action_due_date', sa.Date(), nullable=True))
    
    # Add last_action_analysis column to hives table
    op.add_column('hives', sa.Column('last_action_analysis', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove added columns
    op.drop_column('hives', 'last_action_analysis')
    op.drop_column('inspections', 'action_due_date')
    op.drop_column('inspections', 'action_items')