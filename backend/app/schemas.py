import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CategoryUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CategoryRead(BaseModel):
    id: int
    name: str
    slug: str
    entry_count: int = 0

    class Config:
        from_attributes = True


class TagRead(BaseModel):
    id: int
    name: str
    entry_count: int = 0

    class Config:
        from_attributes = True


class EntryHistoryRead(BaseModel):
    id: int
    entry_id: int
    title: str
    content: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class AttachmentRead(BaseModel):
    id: int
    entry_id: int
    original_filename: str
    stored_filename: str
    mime_type: str
    size: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class EntryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = ""
    category_id: Optional[int] = None
    is_favorite: bool = False
    tags: List[str] = []


class EntryUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = None
    category_id: Optional[int] = None
    is_favorite: Optional[bool] = None
    tags: Optional[List[str]] = None


class EntryRead(BaseModel):
    id: int
    title: str
    content: str
    category_id: Optional[int]
    category_name: Optional[str]
    is_favorite: bool
    tags: List[TagRead] = []
    attachments: List[AttachmentRead] = []
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    entries: List[EntryRead]
    total: int


class ImportResult(BaseModel):
    created: int
    entries: List[EntryRead]
