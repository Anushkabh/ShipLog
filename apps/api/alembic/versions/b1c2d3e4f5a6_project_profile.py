"""project product-profile fields (AI drafting context)

Revision ID: b1c2d3e4f5a6
Revises: 9242d7943715
Create Date: 2026-08-15 19:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "9242d7943715"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("product_summary", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("audience", sa.String(length=255), nullable=True))
    op.add_column("projects", sa.Column("tone", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "tone")
    op.drop_column("projects", "audience")
    op.drop_column("projects", "product_summary")
