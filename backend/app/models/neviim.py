from __future__ import annotations

from datetime import datetime
from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class NeviimBook(Base):
    __tablename__ = "neviim_books"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    title_he: Mapped[str] = mapped_column(String(80), unique=True)
    title_en: Mapped[str] = mapped_column(String(80), unique=True)
    book_order: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    chapter_count: Mapped[int] = mapped_column(Integer)
    source_name: Mapped[str] = mapped_column(String(160), default="Tanach with Nikkud")
    source_url: Mapped[str] = mapped_column(Text, default="https://www.sefaria.org")
    license: Mapped[str] = mapped_column(String(80), default="Public Domain")
    imported_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    verses: Mapped[list["NeviimVerse"]] = relationship(back_populates="book", cascade="all, delete-orphan")


class NeviimVerse(Base):
    __tablename__ = "neviim_verses"
    __table_args__ = (
        UniqueConstraint("book_id", "chapter", "verse", name="uq_neviim_book_chapter_verse"),
        Index("ix_neviim_book_chapter", "book_id", "chapter", "verse"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("neviim_books.id", ondelete="CASCADE"), index=True)
    chapter: Mapped[int] = mapped_column(Integer, index=True)
    verse: Mapped[int] = mapped_column(Integer)
    text_nikkud: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    sefaria_ref: Mapped[str] = mapped_column(String(120), unique=True, index=True)

    book: Mapped[NeviimBook] = relationship(back_populates="verses")
