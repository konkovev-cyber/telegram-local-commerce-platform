"""002_s1_user_telegram_fields

Revision ID: 002_s1_user_telegram_fields
Revises: 001_s0_initial_schema
Create Date: 2026-10-02 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_s1_user_telegram_fields"
down_revision: Union[str, None] = "001_s0_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_id", sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column("first_name", sa.String(200), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(200), nullable=True))
    op.add_column("users", sa.Column("username", sa.String(200), nullable=True))
    op.add_column("users", sa.Column("photo_url", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_users_telegram_id", "users", ["telegram_id"])


def downgrade() -> None:
    op.drop_constraint("uq_users_telegram_id", "users", type_="unique")
    op.drop_column("users", "photo_url")
    op.drop_column("users", "username")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("users", "telegram_id")
