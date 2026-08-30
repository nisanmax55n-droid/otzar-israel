from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models import Work, TextSegment, TextVersion
from app.schemas.library import SearchHit, SegmentOut, WorkOut
from app.services.sefaria_importer import SefariaImporter
from app.services.text_utils import normalize_hebrew

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health():
    return {"status": "ok", "service": "otzar-israel"}


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    works_count = db.scalar(select(func.count(Work.id))) or 0
    versions_count = db.scalar(select(func.count(TextVersion.id))) or 0
    segments_count = db.scalar(select(func.count(TextSegment.id))) or 0
    verified_versions = db.scalar(select(func.count(TextVersion.id)).where(TextVersion.license_verified.is_(True))) or 0
    categories_rows = db.execute(
        select(Work.category, func.count(Work.id))
        .group_by(Work.category)
        .order_by(func.count(Work.id).desc(), Work.category)
    ).all()
    return {
        "works": works_count,
        "versions": versions_count,
        "segments": segments_count,
        "verified_versions": verified_versions,
        "categories": [{"name": name, "count": count} for name, count in categories_rows],
    }


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Work.category, func.count(Work.id))
        .group_by(Work.category)
        .order_by(Work.category)
    ).all()
    return [{"name": name, "count": count} for name, count in rows]


@router.get("/works", response_model=list[WorkOut])
def works(category: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Work).order_by(Work.category, Work.subcategory, Work.title_he)
    if category:
        stmt = stmt.where(Work.category == category)
    if q:
        stmt = stmt.where(or_(Work.title_he.contains(q), Work.title_en.contains(q)))
    return list(db.scalars(stmt.limit(5000)).all())


@router.get("/works/{work_id}/sections")
def work_sections(work_id: int, db: Session = Depends(get_db)):
    version = db.scalar(
        select(TextVersion)
        .where(TextVersion.work_id == work_id, TextVersion.license_verified.is_(True))
        .order_by(TextVersion.id)
    )
    if not version:
        raise HTTPException(404, "לא נמצאה מהדורה מאושרת להצגה")
    rows = db.execute(
        select(TextSegment.level1, func.count(TextSegment.id))
        .where(TextSegment.version_id == version.id, TextSegment.level1.is_not(None))
        .group_by(TextSegment.level1)
        .order_by(TextSegment.level1)
    ).all()
    return [{"level1": level1, "count": count} for level1, count in rows]


@router.get("/works/{work_id}/segments", response_model=list[SegmentOut])
def segments(
    work_id: int,
    level1: int | None = None,
    offset: int = 0,
    limit: int = Query(500, le=2000),
    db: Session = Depends(get_db),
):
    version = db.scalar(
        select(TextVersion)
        .where(TextVersion.work_id == work_id, TextVersion.license_verified.is_(True))
        .order_by(TextVersion.id)
    )
    if not version:
        raise HTTPException(404, "לא נמצאה מהדורה מאושרת להצגה")
    stmt = select(TextSegment).where(TextSegment.version_id == version.id)
    if level1 is not None:
        stmt = stmt.where(TextSegment.level1 == level1)
    stmt = stmt.order_by(TextSegment.position).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


@router.get("/search", response_model=list[SearchHit])
def search(q: str = Query(min_length=2), limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    nq = normalize_hebrew(q)
    stmt = (
        select(TextSegment, Work)
        .join(TextVersion, TextSegment.version_id == TextVersion.id)
        .join(Work, TextVersion.work_id == Work.id)
        .where(TextVersion.license_verified.is_(True), TextSegment.normalized_text.contains(nq))
        .limit(limit)
    )
    return [SearchHit(work_id=w.id, work_title=w.title_he, ref=s.ref, text=s.text) for s, w in db.execute(stmt).all()]


@router.get("/admin/import/sefaria/preview")
def import_preview(category: str | None = None, limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    return SefariaImporter(db).preview(category=category, limit=limit)
