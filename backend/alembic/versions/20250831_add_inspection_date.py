"""Add inspection_date field for user-editable dates

Revision ID: 20250831_add_inspection_date
Revises: 20250827_add_action_items
Create Date: 2025-08-31 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250831_add_inspection_date'
down_revision: Union[str, Sequence[str], None] = '20250827_add_action_items'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add inspection_date column to inspections table
    # This will be the user-editable date, separate from the creation timestamp
    op.add_column('inspections', sa.Column('inspection_date', sa.Date(), nullable=True))
    
    # Populate existing rows with date extracted from timestamp
    op.execute("UPDATE inspections SET inspection_date = DATE(timestamp) WHERE inspection_date IS NULL")


def downgrade() -> None:
    # Remove the inspection_date column
    op.drop_column('inspections', 'inspection_date')