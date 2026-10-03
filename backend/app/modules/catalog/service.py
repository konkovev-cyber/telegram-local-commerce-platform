import uuid
from typing import Optional, Tuple
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.modules.catalog.models import Unit, Category, Product, ProductVariant
from app.core.db import Base


class CatalogService:
    @staticmethod
    async def create_unit(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        name: str,
        short_name: str,
    ) -> Unit:
        unit = Unit(id=uuid.uuid4(), shop_id=shop_id, name=name, short_name=short_name)
        session.add(unit)
        await session.flush()
        return unit

    @staticmethod
    async def get_unit(
        session: AsyncSession,
        *,
        unit_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> Optional[Unit]:
        stmt = select(Unit).where(Unit.id == unit_id, Unit.shop_id == shop_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_units(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
    ) -> list[Unit]:
        stmt = select(Unit).where(Unit.shop_id == shop_id).order_by(Unit.name)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_unit(
        session: AsyncSession,
        *,
        unit: Unit,
        name: Optional[str] = None,
        short_name: Optional[str] = None,
    ) -> Unit:
        if name is not None:
            unit.name = name
        if short_name is not None:
            unit.short_name = short_name
        await session.flush()
        return unit

    @staticmethod
    async def _get_category_tree(session: AsyncSession, category_id: uuid.UUID) -> list[Category]:
        """Return [category, child, grandchild, ...] from root to the given category."""
        stmt = select(Category).where(Category.id == category_id)
        cat = (await session.execute(stmt)).scalar_one_or_none()
        if not cat:
            return []
        return [cat]

    @staticmethod
    async def _find_all_descendants(
        session: AsyncSession, category_id: uuid.UUID
    ) -> list[Category]:
        """BFS to find all descendants of a category."""
        result: list[Category] = []
        queue: list[uuid.UUID] = [category_id]
        while queue:
            current_id = queue.pop(0)
            stmt = select(Category).where(Category.parent_id == current_id)
            res = await session.execute(stmt)
            children = list(res.scalars().all())
            for child in children:
                result.append(child)
                queue.append(child.id)
        return result

    @staticmethod
    async def _get_max_relative_depth(
        session: AsyncSession, category_id: uuid.UUID
    ) -> int:
        """Calculate the max depth relative to the given category (root=1)."""
        descendants = await CatalogService._find_all_descendants(session, category_id)
        if not descendants:
            return 1
        max_rel = 1
        for desc in descendants:
            rel = 1
            node = desc
            while node.parent_id is not None:
                node = await session.get(Category, node.parent_id)
                if node is None or node.id == category_id:
                    break
                rel += 1
            if rel > max_rel:
                max_rel = rel
        return max_rel

    @staticmethod
    async def create_category(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        name: str,
        slug: str,
        parent_id: Optional[uuid.UUID] = None,
        sort_order: int = 0,
    ) -> Category:
        if parent_id is not None:
            parent = await session.get(Category, parent_id)
            if parent is None or parent.shop_id != shop_id:
                raise ValueError("invalid_parent")
            # Check for cycle: walk up from parent's parent; if we reach parent_id again → cycle
            stmt = select(Category).where(Category.id == parent_id)
            ancestor = (await session.execute(stmt)).scalar_one_or_none()
            while ancestor and ancestor.parent_id:
                ancestor = await session.get(Category, ancestor.parent_id)
                if ancestor and ancestor.id == parent_id:
                    raise ValueError("cycle")
            new_depth = parent.depth + 1
        else:
            new_depth = 1

        if new_depth > 3:
            raise ValueError("depth_exceeded")

        category = Category(
            id=uuid.uuid4(),
            shop_id=shop_id,
            parent_id=parent_id,
            name=name,
            slug=slug,
            sort_order=sort_order,
            depth=new_depth,
        )
        session.add(category)
        await session.flush()
        return category

    @staticmethod
    async def relocate_subtree(
        session: AsyncSession,
        *,
        category_id: uuid.UUID,
        shop_id: uuid.UUID,
        new_parent_id: Optional[uuid.UUID] = None,
    ) -> Category:
        """Relocate a category subtree to a new parent, recalculating depths atomically."""
        category = await session.get(Category, category_id)
        if not category or category.shop_id != shop_id:
            raise ValueError("not_found")

        if new_parent_id is not None:
            new_parent = await session.get(Category, new_parent_id)
            if not new_parent or new_parent.shop_id != shop_id:
                raise ValueError("invalid_parent")
            if new_parent_id == category_id:
                raise ValueError("self_parent")
            # Check cycle: new_parent must not be in category's subtree
            descendants = await CatalogService._find_all_descendants(session, category_id)
            desc_ids = {d.id for d in descendants}
            if new_parent_id in desc_ids:
                raise ValueError("cycle")
            new_root_depth = new_parent.depth + 1
        else:
            new_root_depth = 1

        max_rel = await CatalogService._get_max_relative_depth(session, category_id)
        new_max_depth = new_root_depth + (max_rel - 1)
        if new_max_depth > 3:
            raise ValueError("depth_exceeded")

        # Relocate: update parent_id and depth for category and all descendants
        category.parent_id = new_parent_id
        old_depth = category.depth
        category.depth = new_root_depth

        if descendants:
            for desc in descendants:
                # Count edges from category down to desc by walking up from desc
                rel_depth = 0
                node = desc
                while node.parent_id and node.parent_id != category_id:
                    node = await session.get(Category, node.parent_id)
                    rel_depth += 1
                # desc is rel_depth edges below category; category is at new_root_depth
                desc.depth = new_root_depth + rel_depth + 1

        await session.flush()
        return category

    @staticmethod
    async def list_categories(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
    ) -> list[Category]:
        stmt = (
            select(Category)
            .where(Category.shop_id == shop_id, Category.parent_id.is_(None))
            .order_by(Category.sort_order, Category.name)
        )
        res = await session.execute(stmt)
        roots = list(res.scalars().all())
        return roots

    @staticmethod
    async def list_all_categories(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
    ) -> list[Category]:
        stmt = select(Category).where(Category.shop_id == shop_id).order_by(Category.sort_order, Category.name)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def create_product(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        name: str,
        slug: str,
        sku: str,
        barcode: Optional[str] = None,
        description: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
        unit_id: Optional[uuid.UUID] = None,
        tags: Optional[list] = None,
    ) -> Product:
        if category_id:
            cat = await session.get(Category, category_id)
            if not cat or cat.shop_id != shop_id:
                raise ValueError("invalid_category")
        if unit_id:
            unit = await session.get(Unit, unit_id)
            if not unit or unit.shop_id != shop_id:
                raise ValueError("invalid_unit")

        product = Product(
            id=uuid.uuid4(),
            shop_id=shop_id,
            name=name,
            slug=slug,
            sku=sku,
            barcode=barcode,
            description=description,
            category_id=category_id,
            unit_id=unit_id,
            tags=tags or [],
        )
        session.add(product)
        await session.flush()
        return product

    @staticmethod
    async def get_product(
        session: AsyncSession,
        *,
        product_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> Optional[Product]:
        stmt = select(Product).where(Product.id == product_id, Product.shop_id == shop_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_products(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
    ) -> list[Product]:
        stmt = select(Product).where(Product.shop_id == shop_id).order_by(Product.name)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_product(
        session: AsyncSession,
        *,
        product: Product,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        sku: Optional[str] = None,
        barcode: Optional[str] = None,
        description: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
        unit_id: Optional[uuid.UUID] = None,
        is_active: Optional[bool] = None,
        tags: Optional[list] = None,
    ) -> Product:
        if name is not None:
            product.name = name
        if slug is not None:
            product.slug = slug
        if sku is not None:
            product.sku = sku
        if barcode is not None:
            product.barcode = barcode
        if description is not None:
            product.description = description
        if category_id is not None:
            cat = await session.get(Category, category_id)
            if not cat or cat.shop_id != product.shop_id:
                raise ValueError("invalid_category")
            product.category_id = category_id
        if unit_id is not None:
            unit = await session.get(Unit, unit_id)
            if not unit or unit.shop_id != product.shop_id:
                raise ValueError("invalid_unit")
            product.unit_id = unit_id
        if is_active is not None:
            product.is_active = is_active
        if tags is not None:
            product.tags = tags
        await session.flush()
        return product

    @staticmethod
    async def create_variant(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        product_id: uuid.UUID,
        name: str,
        sku: str,
        barcode: Optional[str] = None,
        qty_value: Optional[float] = None,
        sort_order: int = 0,
    ) -> ProductVariant:
        product = await session.get(Product, product_id)
        if not product or product.shop_id != shop_id:
            raise ValueError("invalid_product")

        variant = ProductVariant(
            id=uuid.uuid4(),
            shop_id=shop_id,
            product_id=product_id,
            name=name,
            sku=sku,
            barcode=barcode,
            qty_value=qty_value,
            sort_order=sort_order,
        )
        session.add(variant)
        await session.flush()
        return variant

    @staticmethod
    async def list_variants(
        session: AsyncSession,
        *,
        product_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> list[ProductVariant]:
        stmt = (
            select(ProductVariant)
            .where(ProductVariant.product_id == product_id, ProductVariant.shop_id == shop_id)
            .order_by(ProductVariant.sort_order, ProductVariant.name)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_variant(
        session: AsyncSession,
        *,
        variant_id: uuid.UUID,
        product_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> Optional[ProductVariant]:
        stmt = select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
            ProductVariant.shop_id == shop_id,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    def handle_integrity_error(exc: IntegrityError) -> str:
        msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
        if "uq_units_shop_name" in msg or 'duplicate key value violates unique constraint "uq_units_shop_name"' in msg:
            return "unit_name_duplicate"
        if "uq_units_shop_short_name" in msg:
            return "unit_short_name_duplicate"
        if "uq_categories_shop_slug" in msg:
            return "category_slug_duplicate"
        if "uq_products_shop_sku" in msg or "uq_products_shop_slug" in msg:
            return "product_duplicate"
        if "uq_variants_shop_sku" in msg:
            return "variant_sku_duplicate"
        if "uq_variants_shop_barcode" in msg or "uq_products_shop_barcode" in msg:
            return "barcode_duplicate"
        return "duplicate_key"
