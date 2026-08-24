"""Phase 2 reliability engine migration

Revision ID: 002_phase2_reliability_engine
Revises: 001_initial_schema
Create Date: 2026-08-22 19:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new cancellation, rescheduling, and idempotency fields to appointments table
    op.add_column("appointments", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True))
    op.add_column("appointments", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("appointments", sa.Column("rescheduled_from_id", sa.Integer(), nullable=True))
    op.add_column("appointments", sa.Column("idempotency_key", sa.String(length=255), nullable=True))

    op.create_foreign_key(
        "fk_appointments_cancelled_by_user_id",
        "appointments",
        "users",
        ["cancelled_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_appointments_rescheduled_from_id",
        "appointments",
        "appointments",
        ["rescheduled_from_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_appointments_idempotency_key"), "appointments", ["idempotency_key"], unique=False)

    # Create idempotency_keys table
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "action", "key", name="uq_user_action_idempotency_key"),
    )
    op.create_index(op.f("ix_idempotency_keys_id"), "idempotency_keys", ["id"], unique=False)
    op.create_index(op.f("ix_idempotency_keys_key"), "idempotency_keys", ["key"], unique=False)
    op.create_index(op.f("ix_idempotency_keys_user_id"), "idempotency_keys", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_index(op.f("ix_appointments_idempotency_key"), table_name="appointments")
    op.drop_constraint("fk_appointments_rescheduled_from_id", "appointments", type_="foreignkey")
    op.drop_constraint("fk_appointments_cancelled_by_user_id", "appointments", type_="foreignkey")
    op.drop_column("appointments", "idempotency_key")
    op.drop_column("appointments", "rescheduled_from_id")
    op.drop_column("appointments", "cancelled_at")
    op.drop_column("appointments", "cancelled_by_user_id")
    op.drop_column("appointments", "cancellation_reason")
