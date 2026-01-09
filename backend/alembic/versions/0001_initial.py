"""Initial migration: create users, hives, and inspections tables

Revision ID: 0001_initial
Revises: 
Create Date: 2024-06-08 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('email', sa.String(), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('is_admin', sa.Boolean(), default=False),
        sa.Column('is_approved', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'hives',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('nickname', sa.String(), nullable=False),
        sa.Column('photo_url', sa.String(), nullable=True),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
    )
    # Note: index on 'id' is automatically created by primary_key=True above

    op.create_table(
        'inspections',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('hive_id', sa.Integer(), sa.ForeignKey('hives.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('transcription', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('weather', sa.String(), nullable=True),
        sa.Column('temperature', sa.String(), nullable=True),
        sa.Column('queen_visible', sa.Boolean(), default=False),
        sa.Column('eggs_visible', sa.Boolean(), default=False),
        sa.Column('larvae_visible', sa.Boolean(), default=False),
        sa.Column('capped_brood_visible', sa.Boolean(), default=False),
        sa.Column('laying_pattern', sa.String(), nullable=True),
        sa.Column('activity_level', sa.String(), nullable=True),
        sa.Column('photos', sa.JSON(), nullable=True),
    )
    # Note: index on 'id' is automatically created by primary_key=True above

def downgrade() -> None:
    op.drop_table('inspections')
    op.drop_table('hives')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')