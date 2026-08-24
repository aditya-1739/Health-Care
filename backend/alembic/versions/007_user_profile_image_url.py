"""User Profile Image URL Migration

Revision ID: 007
Revises: 006
Create Date: 2026-08-24 21:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("profile_image_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "profile_image_url")
