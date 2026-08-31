from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.mishnah import MishnahSeder, MishnahTractate, MishnahUnit

router = APIRouter(prefix="/api/v1/mishnah", tags=["mishnah"])


@router.get("/sedarim")
def sedarim(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(MishnahSeder).order_by(MishnahSeder.seder_order)).all())
    return [
        {
            "id": s.id,
            "slug": s.slug,
            "title_he": s.title_he,
            "title_en": s.title_en,
            "order": s.seder_order,
            "tractate_count": len(s.tractates),
        }
        for s in rows
    ]


@router.get("/sedarim/{seder_slug}/tractates")
def tractates(seder_slug: str, db: Session = Depends(get_db)):
    seder = db.scalar(select(MishnahSeder).where(MishnahSeder.slug == seder_slug))
    if not seder:
        raise HTTPException(404, "סדר לא קיים")
    rows = list(
        db.scalars(
            select(MishnahTractate)
            .where(MishnahTractate.seder_id == seder.id)
            .order_by(MishnahTractate.tractate_order)
        ).all()
    )
    return [
        {
            "id": t.id,
            "slug": t.slug,
            "title_he": t.title_he,
            "title_en": t.title_en,
            "order": t.tractate_order,
            "chapter_count": t.chapter_count,
            "source_name": t.source_name,
            "license": t.license,
        }
        for t in rows
    ]


def _tractate_or_404(slug: str, db: Session) -> MishnahTractate:
    row = db.scalar(select(MishnahTractate).where(MishnahTractate.slug == slug))
    if not row:
        raise HTTPException(404, "המסכת עדיין לא נטענה")
    return row


@router.get("/tractates/{slug}/chapters/{chapter}")
def chapter(slug: str, chapter: int, db: Session = Depends(get_db)):
    tractate = _tractate_or_404(slug, db)
    if chapter < 1 or chapter > tractate.chapter_count:
        raise HTTPException(404, "פרק לא קיים")
    rows = list(
        db.scalars(
            select(MishnahUnit)
            .where(MishnahUnit.tractate_id == tractate.id, MishnahUnit.chapter == chapter)
            .order_by(MishnahUnit.mishnah)
        ).all()
    )
    return [
        {
            "id": m.id,
            "chapter": m.chapter,
            "mishnah": m.mishnah,
            "text": m.text,
            "ref": m.sefaria_ref,
        }
        for m in rows
    ]


@router.get("/tractates/{slug}/book-view")
def tractate_view(slug: str, db: Session = Depends(get_db)):
    tractate = _tractate_or_404(slug, db)
    rows = list(
        db.scalars(
            select(MishnahUnit)
            .where(MishnahUnit.tractate_id == tractate.id)
            .order_by(MishnahUnit.chapter, MishnahUnit.mishnah)
        ).all()
    )
    return [
        {
            "id": m.id,
            "chapter": m.chapter,
            "mishnah": m.mishnah,
            "text": m.text,
            "ref": m.sefaria_ref,
        }
        for m in rows
    ]
