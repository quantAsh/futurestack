"""add experience retreat metadata fields

Revision ID: 8d3e2f022b8d
Revises: f76a7f2c6222
Create Date: 2025-12-13 15:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d3e2f022b8d"
down_revision: Union[str, None] = "f76a7f2c6222"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("experiences", sa.Column("website", sa.String(), nullable=True))
    op.add_column(
        "experiences", sa.Column("membership_link", sa.String(), nullable=True)
    )
    op.add_column("experiences", sa.Column("city", sa.String(), nullable=True))
    op.add_column("experiences", sa.Column("country", sa.String(), nullable=True))
    op.add_column("experiences", sa.Column("price_label", sa.String(), nullable=True))
    op.add_column(
        "experiences", sa.Column("duration_label", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("experiences", "duration_label")
    op.drop_column("experiences", "price_label")
    op.drop_column("experiences", "country")
    op.drop_column("experiences", "city")
    op.drop_column("experiences", "membership_link")
    op.drop_column("experiences", "website")
