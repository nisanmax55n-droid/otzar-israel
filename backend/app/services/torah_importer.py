from __future__ import annotations

import re
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import TorahBook, TorahParasha, TorahVerse
from app.services.text_utils import normalize_hebrew


TORAH_BOOKS = [
    {"slug": "genesis", "title_en": "Genesis", "title_he": "בראשית", "order": 1, "chapters": 50},
    {"slug": "exodus", "title_en": "Exodus", "title_he": "שמות", "order": 2, "chapters": 40},
    {"slug": "leviticus", "title_en": "Leviticus", "title_he": "ויקרא", "order": 3, "chapters": 27},
    {"slug": "numbers", "title_en": "Numbers", "title_he": "במדבר", "order": 4, "chapters": 36},
    {"slug": "deuteronomy", "title_en": "Deuteronomy", "title_he": "דברים", "order": 5, "chapters": 34},
]

SEFARIA_BASE = "https://www.sefaria.org"
VERSION_TITLE = "Tanach with Nikkud"
SOURCE_URL = "https://www.sefaria.org/Genesis.1.1?lang=he&vhe=hebrew%7CTanach_with_Nikkud&with=About"


def _primary_title(node: dict[str, Any], lang: str) -> str:
    titles = node.get("titles") or []
    for title in titles:
        if title.get("lang") == lang and title.get("primary"):
            return title.get("text", "")
    for title in titles:
        if title.get("lang") == lang:
            return title.get("text", "")
    return ""


def _parasha_nodes(index: dict[str, Any]) -> list[dict[str, Any]]:
    root = (index.get("alt_structs") or {}).get("Parasha") or {}
    found: list[dict[str, Any]] = []

    def walk(node: dict[str, Any]) -> None:
        if node.get("wholeRef"):
            found.append(node)
        for child in node.get("nodes") or []:
            walk(child)

    walk(root)
    return found


def _parse_whole_ref(whole_ref: str, book_title: str) -> tuple[int, int, int, int]:
    value = whole_ref.replace("–", "-").replace("—", "-")
    value = re.sub(rf"^{re.escape(book_title)}\s+", "", value).strip()
    match = re.fullmatch(r"(\d+):(\d+)-(\d+):(\d+)", value)
    if match:
        return tuple(int(x) for x in match.groups())  # type: ignore[return-value]
    match = re.fullmatch(r"(\d+):(\d+)-(\d+)", value)
    if match:
        chapter, start_verse, end_verse = (int(x) for x in match.groups())
        return chapter, start_verse, chapter, end_verse
    match = re.fullmatch(r"(\d+):(\d+)", value)
    if match:
        chapter, verse = (int(x) for x in match.groups())
        return chapter, verse, chapter, verse
    raise ValueError(f"Unsupported Torah parasha reference: {whole_ref}")


class TorahImporter:
    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "Otzar-Israel/0.2"})

    def close(self) -> None:
        self.client.close()

    def import_all(self, replace: bool = True) -> dict[str, Any]:
        if replace:
            self.db.execute(delete(TorahVerse))
            self.db.execute(delete(TorahParasha))
            self.db.execute(delete(TorahBook))
            self.db.commit()

        summary: list[dict[str, Any]] = []
        try:
            for info in TORAH_BOOKS:
                summary.append(self.import_book(info))
            return {"status": "ok", "books": summary}
        finally:
            self.close()

    def import_book(self, info: dict[str, Any]) -> dict[str, Any]:
        existing = self.db.scalar(select(TorahBook).where(TorahBook.slug == info["slug"]))
        if existing:
            return {"book": info["title_he"], "status": "exists"}

        index_response = self.client.get(f"{SEFARIA_BASE}/api/v2/raw/index/{info['title_en']}")
        index_response.raise_for_status()
        index_data = index_response.json()

        book = TorahBook(
            slug=info["slug"],
            title_he=info["title_he"],
            title_en=info["title_en"],
            book_order=info["order"],
            chapter_count=info["chapters"],
            source_name=VERSION_TITLE,
            source_url=SOURCE_URL,
            license="Public Domain",
        )
        self.db.add(book)
        self.db.flush()

        parasha_count = 0
        for node in _parasha_nodes(index_data):
            whole_ref = node.get("wholeRef", "")
            try:
                sc, sv, ec, ev = _parse_whole_ref(whole_ref, info["title_en"])
            except ValueError:
                continue
            title_he = _primary_title(node, "he")
            title_en = _primary_title(node, "en")
            if not title_he or not title_en:
                continue
            parasha_count += 1
            self.db.add(TorahParasha(
                book_id=book.id,
                title_he=title_he,
                title_en=title_en,
                parasha_order=parasha_count,
                whole_ref=whole_ref,
                start_chapter=sc,
                start_verse=sv,
                end_chapter=ec,
                end_verse=ev,
            ))

        verse_count = 0
        for chapter in range(1, info["chapters"] + 1):
            response = self.client.get(
                f"{SEFARIA_BASE}/api/v3/texts/{info['title_en']} {chapter}",
                params={"version": f"he|{VERSION_TITLE}"},
            )
            response.raise_for_status()
            payload = response.json()
            versions = payload.get("versions") or []
            if not versions:
                raise RuntimeError(f"No {VERSION_TITLE} text returned for {info['title_en']} {chapter}")
            verses = versions[0].get("text") or []
            for verse_number, text in enumerate(verses, start=1):
                if not isinstance(text, str) or not text.strip():
                    continue
                verse_count += 1
                self.db.add(TorahVerse(
                    book_id=book.id,
                    chapter=chapter,
                    verse=verse_number,
                    text_nikkud=text.strip(),
                    normalized_text=normalize_hebrew(text),
                    sefaria_ref=f"{info['title_en']} {chapter}:{verse_number}",
                ))
            if chapter % 5 == 0:
                self.db.commit()

        self.db.commit()
        return {"book": info["title_he"], "status": "imported", "parashot": parasha_count, "verses": verse_count}
