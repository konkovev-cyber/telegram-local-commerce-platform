"""003_s2a_catalog

Revision ID: 003_s2a_catalog
Revises: 002_s1_user_telegram_fields
Create Date: 2026-10-03 10:00:00.000000

S2-A Catalog Foundation: add missing columns/indexes/constraints
to existing units, categories, products, product_variants tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_s2a_catalog"
down_revision: Union[str, None] = "002_s1_user_telegram_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── units: add missing columns ──
    op.add_column("units", sa.Column("short_name", sa.String(10), nullable=True))
    op.add_column("units", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("NOW()")))
    op.add_column("units", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("NOW()")))
    op.create_index("ix_units_shop_id", "units", ["shop_id"])
    op.create_unique_constraint("uq_units_shop_name", "units", ["shop_id", "name"])
    op.create_unique_constraint("uq_units_shop_short_name", "units", ["shop_id", "short_name"])
    op.execute("ALTER TABLE units ALTER COLUMN short_name SET NOT NULL")

    # ── categories: add missing timestamps, slug constraint, depth, indexes ──
    op.alter_column("categories", "slug", type_=sa.String(160))
    op.add_column("categories", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("NOW()")))
    op.add_column("categories", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("NOW()")))
    op.add_column("categories", sa.Column("depth", sa.SmallInteger(), nullable=False, server_default="1"))
    op.create_index("ix_categories_shop_id", "categories", ["shop_id"])
    op.create_index("ix_categories_shop_parent_sort", "categories", ["shop_id", "parent_id", "sort_order"])
    op.create_check_constraint("ck_categories_depth", "categories", "depth BETWEEN 1 AND 3")

    # ── products: add slug, convert tags text[] → jsonb, enforce sku NOT NULL ──
    op.add_column("products", sa.Column("slug", sa.String(270), nullable=False, server_default=""))
    op.create_unique_constraint("uq_products_shop_slug", "products", ["shop_id", "slug"])
    op.create_index("ix_products_shop_id", "products", ["shop_id"])
    op.create_index(
        "uq_products_shop_barcode",
        "products",
        ["shop_id", "barcode"],
        unique=True,
        postgresql_where=sa.text("barcode IS NOT NULL"),
    )
    # Convert tags from text[] to jsonb via a temp column
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE products ADD COLUMN tags_new jsonb NOT NULL DEFAULT '[]'::jsonb"))
    conn.execute(sa.text("UPDATE products SET tags_new = to_jsonb(tags)::jsonb"))
    conn.execute(sa.text("ALTER TABLE products DROP COLUMN tags"))
    conn.execute(sa.text("ALTER TABLE products RENAME COLUMN tags_new TO tags"))
    # Enforce NOT NULL on sku (was nullable in S0)
    conn.execute(sa.text("UPDATE products SET sku = '' WHERE sku IS NULL"))
    op.execute("ALTER TABLE products ALTER COLUMN sku SET NOT NULL")

    # ── product_variants: add indexes, enforce sku NOT NULL ──
    op.create_index("ix_product_variants_shop_id", "product_variants", ["shop_id"])
    op.create_index("ix_product_variants_product_id", "product_variants", ["product_id"])
    op.create_index(
        "uq_variants_shop_barcode",
        "product_variants",
        ["shop_id", "barcode"],
        unique=True,
        postgresql_where=sa.text("barcode IS NOT NULL"),
    )
    conn.execute(sa.text("UPDATE product_variants SET sku = '' WHERE sku IS NULL"))
    op.execute("ALTER TABLE product_variants ALTER COLUMN sku SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE product_variants ALTER COLUMN sku DROP NOT NULL")
    op.drop_index("uq_variants_shop_barcode", table_name="product_variants")
    op.drop_index("ix_product_variants_product_id", table_name="product_variants")
    op.drop_index("ix_product_variants_shop_id", table_name="product_variants")
    op.drop_index("uq_products_shop_barcode", table_name="products")
    op.drop_index("ix_products_shop_id", table_name="products")
    op.drop_constraint("uq_products_shop_slug", "products", type_="unique")
    op.drop_column("products", "slug")
    # Revert tags: jsonb → text[] via temp column
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE products ADD COLUMN tags_old text[]"))
    conn.execute(sa.text("UPDATE products SET tags_old = (SELECT array_agg(x::text) FROM jsonb_array_elements(tags) AS x)"))
    conn.execute(sa.text("ALTER TABLE products DROP COLUMN tags"))
    conn.execute(sa.text("ALTER TABLE products RENAME COLUMN tags_old TO tags"))
    op.execute("ALTER TABLE products ALTER COLUMN sku DROP NOT NULL")
    op.drop_constraint("ck_categories_depth", "categories", type_="check")
    op.drop_index("ix_categories_shop_parent_sort", table_name="categories")
    op.drop_index("ix_categories_shop_id", table_name="categories")
    op.drop_column("categories", "depth")
    op.alter_column("categories", "slug", type_=sa.String(200))
    op.drop_column("categories", "updated_at")
    op.drop_column("categories", "created_at")
    op.drop_constraint("uq_units_shop_short_name", "units", type_="unique")
    op.drop_constraint("uq_units_shop_name", "units", type_="unique")
    op.drop_index("ix_units_shop_id", table_name="units")
    op.drop_column("units", "short_name")
    op.drop_column("units", "updated_at")
    op.drop_column("units", "created_at")
