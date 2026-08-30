from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class Work(Base):
    __tablename__ = "works"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    title_he: Mapped[str] = mapped_column(String(320), index=True)
    title_en: Mapped[str | None] = mapped_column(String(320), nullable=True)
    category: Mapped[str] = mapped_column(String(120), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    author: Mapped[str | None] = mapped_column(String(240), nullable=True)
    era: Mapped[str | None] = mapped_column(String(120), nullable=True)
    structure_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_system: Mapped[str] = mapped_column(String(80), default="sefaria")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    versions: Mapped[list["TextVersion"]] = relationship(back_populates="work", cascade="all, delete-orphan")


class TextVersion(Base):
    __tablename__ = "text_versions"
    __table_args__ = (UniqueConstraint("work_id", "language", "version_title", name="uq_work_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), index=True)
    language: Mapped[str] = mapped_column(String(32), index=True)
    version_title: Mapped[str] = mapped_column(String(320))
    license: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    license_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    work: Mapped[Work] = relationship(back_populates="versions")
    segments: Mapped[list["TextSegment"]] = relationship(back_populates="version", cascade="all, delete-orphan")


class TextSegment(Base):
    __tablename__ = "text_segments"
    __table_args__ = (
        UniqueConstraint("version_id", "ref", name="uq_version_ref"),
        Index("ix_segments_ref_title", "ref", "section_title"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("text_versions.id", ondelete="CASCADE"), index=True)
    ref: Mapped[str] = mapped_column(String(420), index=True)
    section_title: Mapped[str | None] = mapped_column(String(320), nullable=True)
    level1: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    level2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text, index=False)
    version: Mapped[TextVersion] = relationship(back_populates="segments")
