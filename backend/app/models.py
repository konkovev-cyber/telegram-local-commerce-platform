import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index,
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    entries = relationship("Entry", back_populates="category")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)

    entries = relationship("Entry", secondary="entry_tags", back_populates="tags")


class EntryTag(Base):
    __tablename__ = "entry_tags"
    __table_args__ = (UniqueConstraint("entry_id", "tag_id"),)

    entry_id = Column(Integer, ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)


class Entry(Base):
    __tablename__ = "entries"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    content = Column(Text, default="")
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    is_favorite = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    category = relationship("Category", back_populates="entries")
    tags = relationship("Tag", secondary="entry_tags", back_populates="entries")
    attachments = relationship("Attachment", back_populates="entry", cascade="all, delete-orphan", order_by="Attachment.created_at")
    history = relationship("EntryHistory", back_populates="entry", cascade="all, delete-orphan", order_by="EntryHistory.created_at.desc()")


class EntryHistory(Base):
    __tablename__ = "entry_history"

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    entry = relationship("Entry", back_populates="history")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    mime_type = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    entry = relationship("Entry", back_populates="attachments")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False, index=True)
    department = Column(String(100), index=True)
    position = Column(String(100))
    phone = Column(String(50))
    email = Column(String(255))
    sip = Column(String(50))
    domain_login = Column(String(100), index=True)
    room = Column(String(50))
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    assets = relationship("Asset", back_populates="employee")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    asset_type = Column(String(50), nullable=False, index=True)
    vendor = Column(String(100), index=True)
    model = Column(String(255))
    serial_number = Column(String(100), index=True)
    inventory_number = Column(String(100), index=True)
    mac_address = Column(String(50), index=True)
    ip_address = Column(String(50), index=True)
    status = Column(String(50), default="в работе", index=True)
    location = Column(String(255), index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    purchase_date = Column(String(20))
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    employee = relationship("Employee", back_populates="assets")
