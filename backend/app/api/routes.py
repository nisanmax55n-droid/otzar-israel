from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import (
    NeviimBook,
    NeviimVerse,
    TextSegment,
    TextVersion,
    TorahBook,
    TorahParasha,
    TorahVerse,
    Work,
)
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
    torah_books = db.scalar(select(func.count(TorahBook.id))) or 0
    neviim_books = db.scalar(select(func.count(NeviimBook.id))) or 0
    versions_count = db.scalar(select(func.count(TextVersion.id))) or 0
    segments_count = db.scalar(select(func.count(TextSegment.id))) or 0
    torah_verses = db.scalar(select(func.count(TorahVerse.id))) or 0
    neviim_verses = db.scalar(select(func.count(NeviimVerse.id))) or 0
    verified_versions = db.scalar(select(func.count(TextVersion.id)).where(TextVersion.license_verified.is_(True))) or 0
    categories_rows = db.execute(
        select(Work.category, func.count(Work.id)).group_by(Work.category).order_by(func.count(Work.id).desc(), Work.category)
    ).all()
    categories = [{"name": name, "count": count} for name, count in categories_rows]
    tanakh_count = torah_books + neviim_books
    if tanakh_count:
        categories.insert(0, {"name": "Tanakh", "count": tanakh_count})
    return {
        "works": works_count + tanakh_count,
        "versions": versions_count,
        "segments": segments_count + torah_verses + neviim_verses,
        "verified_versions": verified_versions,
        "categories": categories,
    }


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    rows = db.execute(select(Work.category, func.count(Work.id)).group_by(Work.category).order_by(Work.category)).all()
    result = [{"name": name, "count": count} for name, count in rows]
    tanakh_count = (db.scalar(select(func.count(TorahBook.id))) or 0) + (db.scalar(select(func.count(NeviimBook.id))) or 0)
    if tanakh_count:
        result.insert(0, {"name": "Tanakh", "count": tanakh_count})
    return result


@router.get("/torah/books")
def torah_books(db: Session = Depends(get_db)):
    books = list(db.scalars(select(TorahBook).order_by(TorahBook.book_order)).all())
    return [{"id":b.id,"slug":b.slug,"title_he":b.title_he,"title_en":b.title_en,"book_order":b.book_order,"chapter_count":b.chapter_count,"source_name":b.source_name,"license":b.license} for b in books]


def _torah_book_or_404(slug: str, db: Session) -> TorahBook:
    book = db.scalar(select(TorahBook).where(TorahBook.slug == slug))
    if not book:
        raise HTTPException(404, "החומש עדיין לא נטען")
    return book


@router.get("/torah/books/{slug}/parashot")
def torah_parashot(slug: str, db: Session = Depends(get_db)):
    book = _torah_book_or_404(slug, db)
    rows = list(db.scalars(select(TorahParasha).where(TorahParasha.book_id == book.id).order_by(TorahParasha.parasha_order)).all())
    return [{"id":p.id,"title_he":p.title_he,"title_en":p.title_en,"order":p.parasha_order,"whole_ref":p.whole_ref,"start_chapter":p.start_chapter,"start_verse":p.start_verse,"end_chapter":p.end_chapter,"end_verse":p.end_verse,"chapters":list(range(p.start_chapter,p.end_chapter+1))} for p in rows]


@router.get("/torah/books/{slug}/chapters/{chapter}")
def torah_chapter(slug: str, chapter: int, db: Session = Depends(get_db)):
    book = _torah_book_or_404(slug, db)
    if chapter < 1 or chapter > book.chapter_count:
        raise HTTPException(404, "פרק לא קיים")
    verses = list(db.scalars(select(TorahVerse).where(TorahVerse.book_id == book.id, TorahVerse.chapter == chapter).order_by(TorahVerse.verse)).all())
    return [{"id":v.id,"chapter":v.chapter,"verse":v.verse,"text":v.text_nikkud,"ref":v.sefaria_ref} for v in verses]


@router.get("/torah/parashot/{parasha_id}/chapters/{chapter}")
def torah_parasha_chapter(parasha_id: int, chapter: int, db: Session = Depends(get_db)):
    parasha = db.get(TorahParasha, parasha_id)
    if not parasha:
        raise HTTPException(404, "פרשה לא קיימת")
    if chapter < parasha.start_chapter or chapter > parasha.end_chapter:
        raise HTTPException(404, "הפרק אינו חלק מהפרשה")
    conditions = [TorahVerse.book_id == parasha.book_id, TorahVerse.chapter == chapter]
    if chapter == parasha.start_chapter:
        conditions.append(TorahVerse.verse >= parasha.start_verse)
    if chapter == parasha.end_chapter:
        conditions.append(TorahVerse.verse <= parasha.end_verse)
    verses = list(db.scalars(select(TorahVerse).where(and_(*conditions)).order_by(TorahVerse.verse)).all())
    return [{"id":v.id,"chapter":v.chapter,"verse":v.verse,"text":v.text_nikkud,"ref":v.sefaria_ref} for v in verses]


@router.get("/torah/books/{slug}/book-view")
def torah_book_view(slug: str, db: Session = Depends(get_db)):
    book = _torah_book_or_404(slug, db)
    verses = list(db.scalars(select(TorahVerse).where(TorahVerse.book_id == book.id).order_by(TorahVerse.chapter, TorahVerse.verse)).all())
    return [{"id":v.id,"chapter":v.chapter,"verse":v.verse,"text":v.text_nikkud,"ref":v.sefaria_ref} for v in verses]


@router.get("/neviim/books")
def neviim_books(db: Session = Depends(get_db)):
    books = list(db.scalars(select(NeviimBook).order_by(NeviimBook.book_order)).all())
    return [{"id":b.id,"slug":b.slug,"title_he":b.title_he,"title_en":b.title_en,"book_order":b.book_order,"chapter_count":b.chapter_count,"source_name":b.source_name,"license":b.license} for b in books]


def _neviim_book_or_404(slug: str, db: Session) -> NeviimBook:
    book = db.scalar(select(NeviimBook).where(NeviimBook.slug == slug))
    if not book:
        raise HTTPException(404, "ספר הנביאים עדיין לא נטען")
    return book


@router.get("/neviim/books/{slug}/chapters/{chapter}")
def neviim_chapter(slug: str, chapter: int, db: Session = Depends(get_db)):
    book = _neviim_book_or_404(slug, db)
    if chapter < 1 or chapter > book.chapter_count:
        raise HTTPException(404, "פרק לא קיים")
    verses = list(db.scalars(select(NeviimVerse).where(NeviimVerse.book_id == book.id, NeviimVerse.chapter == chapter).order_by(NeviimVerse.verse)).all())
    return [{"id":v.id,"chapter":v.chapter,"verse":v.verse,"text":v.text_nikkud,"ref":v.sefaria_ref} for v in verses]


@router.get("/neviim/books/{slug}/book-view")
def neviim_book_view(slug: str, db: Session = Depends(get_db)):
    book = _neviim_book_or_404(slug, db)
    verses = list(db.scalars(select(NeviimVerse).where(NeviimVerse.book_id == book.id).order_by(NeviimVerse.chapter, NeviimVerse.verse)).all())
    return [{"id":v.id,"chapter":v.chapter,"verse":v.verse,"text":v.text_nikkud,"ref":v.sefaria_ref} for v in verses]


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
    version = db.scalar(select(TextVersion).where(TextVersion.work_id == work_id, TextVersion.license_verified.is_(True)).order_by(TextVersion.id))
    if not version:
        raise HTTPException(404, "לא נמצאה מהדורה מאושרת להצגה")
    rows = db.execute(select(TextSegment.level1, func.count(TextSegment.id)).where(TextSegment.version_id == version.id, TextSegment.level1.is_not(None)).group_by(TextSegment.level1).order_by(TextSegment.level1)).all()
    return [{"level1":level1,"count":count} for level1,count in rows]


@router.get("/works/{work_id}/segments", response_model=list[SegmentOut])
def segments(work_id: int, level1: int | None = None, offset: int = 0, limit: int = Query(500, le=2000), db: Session = Depends(get_db)):
    version = db.scalar(select(TextVersion).where(TextVersion.work_id == work_id, TextVersion.license_verified.is_(True)).order_by(TextVersion.id))
    if not version:
        raise HTTPException(404, "לא נמצאה מהדורה מאושרת להצגה")
    stmt = select(TextSegment).where(TextSegment.version_id == version.id)
    if level1 is not None:
        stmt = stmt.where(TextSegment.level1 == level1)
    return list(db.scalars(stmt.order_by(TextSegment.position).offset(offset).limit(limit)).all())


@router.get("/search", response_model=list[SearchHit])
def search(q: str = Query(min_length=2), limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    nq = normalize_hebrew(q)
    generic_stmt = select(TextSegment, Work).join(TextVersion, TextSegment.version_id == TextVersion.id).join(Work, TextVersion.work_id == Work.id).where(TextVersion.license_verified.is_(True), TextSegment.normalized_text.contains(nq)).limit(limit)
    return [SearchHit(work_id=w.id, work_title=w.title_he, ref=s.ref, text=s.text) for s,w in db.execute(generic_stmt).all()]


@router.get("/admin/import/sefaria/preview")
def import_preview(category: str | None = None, limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    return SefariaImporter(db).preview(category=category, limit=limit)
