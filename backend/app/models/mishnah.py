from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class MishnahSeder(Base):
    __tablename__ = "mishnah_sedarim"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    title_he: Mapped[str] = mapped_column(String(60), unique=True)
    title_en: Mapped[str] = mapped_column(String(60), unique=True)
    seder_order: Mapped[int] = mapped_column(Integer, unique=True, index=True)

    tractates: Mapped[list["MishnahTractate"]] = relationship(back_populates="seder", cascade="all, delete-orphan")


class MishnahTractate(Base):
    __tablename__ = "mishnah_tractates"
    __table_args__ = (
        UniqueConstraint("seder_id", "tractate_order", name="uq_mishnah_seder_tractate_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    seder_id: Mapped[int] = mapped_column(ForeignKey("mishnah_sedarim.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title_he: Mapped[str] = mapped_column(String(100), index=True)
    title_en: Mapped[str] = mapped_column(String(120), unique=True)
    tractate_order: Mapped[int] = mapped_column(Integer)
    chapter_count: Mapped[int] = mapped_column(Integer)
    source_name: Mapped[str] = mapped_column(String(160), default="Sefaria Export - Hebrew merged")
    source_url: Mapped[str] = mapped_column(Text)
    license: Mapped[str] = mapped_column(String(120), default="Sefaria Export - copyright-filtered")
    imported_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    seder: Mapped[MishnahSeder] = relationship(back_populates="tractates")
    mishnayot: Mapped[list["MishnahUnit"]] = relationship(back_populates="tractate", cascade="all, delete-orphan")


class MishnahUnit(Base):
    __tablename__ = "mishnah_units"
    __table_args__ = (
        UniqueConstraint("tractate_id", "chapter", "mishnah", name="uq_mishnah_tractate_chapter_unit"),
        Index("ix_mishnah_tractate_chapter", "tractate_id", "chapter", "mishnah"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tractate_id: Mapped[int] = mapped_column(ForeignKey("mishnah_tractates.id", ondelete="CASCADE"), index=True)
    chapter: Mapped[int] = mapped_column(Integer, index=True)
    mishnah: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    sefaria_ref: Mapped[str] = mapped_column(String(180), unique=True, index=True)

    tractate: Mapped[MishnahTractate] = relationship(back_populates="mishnayot")
