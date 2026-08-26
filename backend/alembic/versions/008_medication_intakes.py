"""Medication Intakes Migration

Revision ID: 008
Revises: 007
Create Date: 2026-08-25 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "medication_intakes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reminder_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Enum("PENDING", "TAKEN", "MISSED", "CANCELLED", name="intakestatus"), nullable=False),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reminder_id"], ["medication_reminders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reminder_id"),
    )
    op.create_index(op.f("ix_medication_intakes_id"), "medication_intakes", ["id"], unique=False)
    op.create_index(op.f("ix_medication_intakes_patient_id"), "medication_intakes", ["patient_id"], unique=False)
    op.create_index(op.f("ix_medication_intakes_reminder_id"), "medication_intakes", ["reminder_id"], unique=False)
    op.create_index(op.f("ix_medication_intakes_scheduled_at"), "medication_intakes", ["scheduled_at"], unique=False)
    op.create_index(op.f("ix_medication_intakes_status"), "medication_intakes", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_medication_intakes_status"), table_name="medication_intakes")
    op.drop_index(op.f("ix_medication_intakes_scheduled_at"), table_name="medication_intakes")
    op.drop_index(op.f("ix_medication_intakes_reminder_id"), table_name="medication_intakes")
    op.drop_index(op.f("ix_medication_intakes_patient_id"), table_name="medication_intakes")
    op.drop_index(op.f("ix_medication_intakes_id"), table_name="medication_intakes")
    op.drop_table("medication_intakes")
