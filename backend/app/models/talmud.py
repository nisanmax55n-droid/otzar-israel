from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class TalmudTractate(Base):
    __tablename__ = "talmud_tractates"
    __table_args__ = (
        UniqueConstraint("tradition", "slug", name="uq_talmud_tradition_slug"),
        Index("ix_talmud_tradition_order", "tradition", "tractate_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tradition: Mapped[str] = mapped_column(String(20), index=True)  # bavli | yerushalmi
    seder_name: Mapped[str] = mapped_column(String(80), default="")
    slug: Mapped[str] = mapped_column(String(120), index=True)
    title_he: Mapped[str] = mapped_column(String(160), index=True)
    title_en: Mapped[str] = mapped_column(String(180))
    tractate_order: Mapped[int] = mapped_column(Integer)
    section_count: Mapped[int] = mapped_column(Integer)
    source_name: Mapped[str] = mapped_column(String(160), default="Sefaria Export")
    source_url: Mapped[str] = mapped_column(Text)
    license: Mapped[str] = mapped_column(String(120))
    license_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    imported_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    segments: Mapped[list["TalmudSegment"]] = relationship(back_populates="tractate", cascade="all, delete-orphan")


class TalmudSegment(Base):
    __tablename__ = "talmud_segments"
    __table_args__ = (
        UniqueConstraint("tractate_id", "section", "position", name="uq_talmud_section_position"),
        Index("ix_talmud_tractate_section_position", "tractate_id", "section", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tractate_id: Mapped[int] = mapped_column(ForeignKey("talmud_tractates.id", ondelete="CASCADE"), index=True)
    section: Mapped[int] = mapped_column(Integer, index=True)
    position: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(String(120), default="")
    text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    sefaria_ref: Mapped[str] = mapped_column(String(220), index=True)

    tractate: Mapped[TalmudTractate] = relationship(back_populates="segments")
