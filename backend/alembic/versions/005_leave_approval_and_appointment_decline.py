"""Doctor Leave Approval and Appointment Decline Migration

Revision ID: 005
Revises: 004
Create Date: 2026-08-24 02:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Idempotently create PostgreSQL custom ENUM type for LeaveStatus
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'leavestatus') THEN
                CREATE TYPE leavestatus AS ENUM ('PENDING', 'APPROVED', 'DECLINED', 'CANCELLED');
            END IF;
        END $$;
    """)

    # 2. Add columns to doctor_leaves
    op.add_column(
        "doctor_leaves",
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "DECLINED", "CANCELLED", name="leavestatus"),
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column(
        "doctor_leaves",
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "doctor_leaves",
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "doctor_leaves",
        sa.Column(
            "reviewed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "doctor_leaves",
        sa.Column(
            "admin_remarks",
            sa.Text(),
            nullable=True,
        ),
    )

    # 3. Create index on status and composite on (doctor_id, status)
    op.create_index("ix_doctor_leaves_status", "doctor_leaves", ["status"])
    op.create_index("ix_doctor_leaves_doctor_status", "doctor_leaves", ["doctor_id", "status"])

    # 4. Backfill any existing doctor_leaves rows to APPROVED
    op.execute("UPDATE doctor_leaves SET status = 'APPROVED' WHERE status IS NULL OR status = 'PENDING'")


def downgrade() -> None:
    op.drop_index("ix_doctor_leaves_doctor_status", table_name="doctor_leaves")
    op.drop_index("ix_doctor_leaves_status", table_name="doctor_leaves")
    op.drop_column("doctor_leaves", "admin_remarks")
    op.drop_column("doctor_leaves", "reviewed_by_user_id")
    op.drop_column("doctor_leaves", "reviewed_at")
    op.drop_column("doctor_leaves", "requested_at")
    op.drop_column("doctor_leaves", "status")
    op.execute("DROP TYPE IF EXISTS leavestatus")
