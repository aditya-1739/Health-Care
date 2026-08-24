"""Profile and Medical Profile Migration

Revision ID: 006
Revises: 005
Create Date: 2026-08-24 09:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns to users table
    op.add_column("users", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))

    # 2. Add columns to patients table
    op.add_column("patients", sa.Column("gender", sa.String(20), nullable=True))
    op.add_column("patients", sa.Column("address", sa.String(255), nullable=True))
    op.add_column("patients", sa.Column("emergency_contact_name", sa.String(150), nullable=True))
    op.add_column("patients", sa.Column("emergency_contact_phone", sa.String(50), nullable=True))

    # 3. Add columns to doctors table
    op.add_column("doctors", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("doctors", sa.Column("date_of_birth", sa.Date(), nullable=True))

    # 4. Create patient_medical_profiles table
    op.create_table(
        "patient_medical_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("blood_group", sa.String(10), nullable=True),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("allergies", sa.Text(), nullable=True),
        sa.Column("chronic_conditions", sa.Text(), nullable=True),
        sa.Column("current_medications", sa.Text(), nullable=True),
        sa.Column("past_surgeries", sa.Text(), nullable=True),
        sa.Column("family_history", sa.Text(), nullable=True),
        sa.Column("medical_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_patient_medical_profiles_patient_id", "patient_medical_profiles", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_patient_medical_profiles_patient_id", table_name="patient_medical_profiles")
    op.drop_table("patient_medical_profiles")
    op.drop_column("doctors", "date_of_birth")
    op.drop_column("doctors", "phone")
    op.drop_column("patients", "emergency_contact_phone")
    op.drop_column("patients", "emergency_contact_name")
    op.drop_column("patients", "address")
    op.drop_column("patients", "gender")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "phone")
