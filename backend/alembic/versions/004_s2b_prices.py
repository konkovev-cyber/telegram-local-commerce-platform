"""004_s2b_prices

Revision ID: 004_s2b_prices
Revises: 003_s2a_catalog
Create Date: 2026-10-03 12:00:00.000000

S2-B Prices: ensure prices table has shop_id index (already created in 001,
just adds the named index if missing). Prices table and idx_prices_active
were created in 001_s0_initial_schema. This migration documents S2-B scope
and is idempotent.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_s2b_prices"
down_revision: Union[str, None] = "003_s2a_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # prices.shop_id index — already exists from 001 (no-op if present)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename='prices' AND indexname='ix_prices_shop_id'"
        )
    )
    if not result.fetchone():
        op.create_index("ix_prices_shop_id", "prices", ["shop_id"])

    # product_media already created in 001 — add sort_order index for public vitrine
    result2 = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename='product_media' AND indexname='ix_product_media_product_id'"
        )
    )
    if not result2.fetchone():
        op.create_index("ix_product_media_product_id", "product_media", ["product_id"])


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename='product_media' AND indexname='ix_product_media_product_id'"
        )
    )
    if result.fetchone():
        op.drop_index("ix_product_media_product_id", table_name="product_media")

    result2 = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename='prices' AND indexname='ix_prices_shop_id'"
        )
    )
    if result2.fetchone():
        op.drop_index("ix_prices_shop_id", table_name="prices")
