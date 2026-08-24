"""Phase 3 Clinical workflow, Prescriptions, Medication Reminders, Notifications, and Google Calendar tokens

Revision ID: 003
Revises: 002
Create Date: 2026-08-23 02:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create prescription_medications table
    op.create_table(
        'prescription_medications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prescription_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('dosage', sa.String(length=100), nullable=False),
        sa.Column('frequency', sa.String(length=100), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='ACTIVE', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['prescription_id'], ['prescriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prescription_medications_id'), 'prescription_medications', ['id'], unique=False)
    op.create_index(op.f('ix_prescription_medications_prescription_id'), 'prescription_medications', ['prescription_id'], unique=False)

    # 2. Create google_calendar_tokens table
    op.create_table(
        'google_calendar_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('encrypted_access_token', sa.Text(), nullable=True),
        sa.Column('encrypted_refresh_token', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('connection_status', sa.String(length=50), server_default='NOT_CONNECTED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_google_calendar_token_user')
    )
    op.create_index(op.f('ix_google_calendar_tokens_id'), 'google_calendar_tokens', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('google_calendar_tokens')
    op.drop_table('prescription_medications')
