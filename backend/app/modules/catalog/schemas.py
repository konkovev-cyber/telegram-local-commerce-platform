from typing import Optional, List
from pydantic import BaseModel, Field


class UnitCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    short_name: str = Field(..., min_length=1, max_length=10)


class UnitResponse(BaseModel):
    id: str
    shop_id: str
    name: str
    short_name: str


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    slug: str = Field(..., min_length=1, max_length=160)
    parent_id: Optional[str] = Field(None, description="UUID of parent category, null for root")
    sort_order: int = Field(0, ge=0)


class CategoryNode(BaseModel):
    id: str
    shop_id: str
    parent_id: Optional[str]
    name: str
    slug: str
    sort_order: int
    is_active: bool
    depth: int
    children: List["CategoryNode"] = Field(default_factory=list)


class ProductCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=270)
    sku: str = Field(..., min_length=1, max_length=100)
    barcode: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    category_id: Optional[str] = None
    unit_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ProductUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=1, max_length=270)
    sku: Optional[str] = Field(None, min_length=1, max_length=100)
    barcode: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    category_id: Optional[str] = None
    unit_id: Optional[str] = None
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = None


class VariantCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    sku: str = Field(..., min_length=1, max_length=100)
    barcode: Optional[str] = Field(None, max_length=100)
    qty_value: Optional[float] = None
    sort_order: int = Field(0, ge=0)


class VariantResponse(BaseModel):
    id: str
    shop_id: str
    product_id: str
    name: str
    sku: str
    barcode: Optional[str]
    qty_value: Optional[float]
    sort_order: int
    is_active: bool
