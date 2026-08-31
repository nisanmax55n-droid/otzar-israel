from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.talmud import TalmudSegment, TalmudTractate

router = APIRouter(prefix="/api/v1/talmud", tags=["talmud"])
VALID_TRADITIONS = {"bavli", "yerushalmi"}


def _validate_tradition(tradition: str) -> str:
    if tradition not in VALID_TRADITIONS:
        raise HTTPException(404, "מסורת תלמוד לא קיימת")
    return tradition


def _tractate_or_404(tradition: str, slug: str, db: Session) -> TalmudTractate:
    _validate_tradition(tradition)
    tractate = db.scalar(
        select(TalmudTractate).where(
            TalmudTractate.tradition == tradition,
            TalmudTractate.slug == slug,
            TalmudTractate.license_verified.is_(True),
        )
    )
    if not tractate:
        raise HTTPException(404, "המסכת עדיין לא נטענה או שרישיונה אינו מאומת")
    return tractate


def _section_label(tradition: str, section: int) -> str:
    if tradition == "bavli":
        daf = 2 + (section - 1) // 2
        amud = "א׳" if section % 2 else "ב׳"
        return f"דף {daf} ע״{amud}"
    return f"פרק {section}"


@router.get("/{tradition}/tractates")
def tractates(tradition: str, db: Session = Depends(get_db)):
    tradition = _validate_tradition(tradition)
    rows = list(
        db.scalars(
            select(TalmudTractate)
            .where(TalmudTractate.tradition == tradition, TalmudTractate.license_verified.is_(True))
            .order_by(TalmudTractate.tractate_order)
        ).all()
    )
    return [
        {
            "id": row.id,
            "tradition": row.tradition,
            "seder_name": row.seder_name,
            "slug": row.slug,
            "title_he": row.title_he,
            "title_en": row.title_en,
            "order": row.tractate_order,
            "section_count": row.section_count,
            "source_name": row.source_name,
            "source_url": row.source_url,
            "license": row.license,
            "license_verified": row.license_verified,
        }
        for row in rows
    ]


@router.get("/{tradition}/tractates/{slug}/sections")
def sections(tradition: str, slug: str, db: Session = Depends(get_db)):
    tractate = _tractate_or_404(tradition, slug, db)
    rows = db.execute(
        select(TalmudSegment.section, func.count(TalmudSegment.id))
        .where(TalmudSegment.tractate_id == tractate.id)
        .group_by(TalmudSegment.section)
        .order_by(TalmudSegment.section)
    ).all()
    return [
        {"index": section, "label": _section_label(tradition, section), "count": count}
        for section, count in rows
    ]


@router.get("/{tradition}/tractates/{slug}/sections/{section}")
def section(tradition: str, slug: str, section: int, db: Session = Depends(get_db)):
    tractate = _tractate_or_404(tradition, slug, db)
    if section < 1 or section > tractate.section_count:
        raise HTTPException(404, "החלק אינו קיים")
    rows = list(
        db.scalars(
            select(TalmudSegment)
            .where(TalmudSegment.tractate_id == tractate.id, TalmudSegment.section == section)
            .order_by(TalmudSegment.position)
        ).all()
    )
    return [
        {
            "id": row.id,
            "section": row.section,
            "position": row.position,
            "path": row.path,
            "text": row.text,
            "ref": row.sefaria_ref,
        }
        for row in rows
    ]


@router.get("/{tradition}/tractates/{slug}/book-view")
def book_view(tradition: str, slug: str, db: Session = Depends(get_db)):
    tractate = _tractate_or_404(tradition, slug, db)
    rows = list(
        db.scalars(
            select(TalmudSegment)
            .where(TalmudSegment.tractate_id == tractate.id)
            .order_by(TalmudSegment.section, TalmudSegment.position)
        ).all()
    )
    return [
        {
            "id": row.id,
            "section": row.section,
            "position": row.position,
            "path": row.path,
            "text": row.text,
            "ref": row.sefaria_ref,
        }
        for row in rows
    ]
