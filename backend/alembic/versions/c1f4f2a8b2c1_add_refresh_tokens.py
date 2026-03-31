"""Add refresh tokens table

Revision ID: c1f4f2a8b2c1
Revises: b92dc1fa17ca
Create Date: 2026-01-06 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1f4f2a8b2c1"
down_revision: Union[str, None] = "b92dc1fa17ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "idx_refresh_token_user", "refresh_tokens", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_refresh_token_user", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
