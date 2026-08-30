from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import TorahBook, TorahParasha, TorahVerse
from app.services.text_utils import normalize_hebrew


VERSION_TITLE = "Tanach with Nikkud"
SOURCE_URL = "https://www.sefaria.org/Genesis.1.1?lang=he&vhe=hebrew%7CTanach_with_Nikkud&with=About"
GCS_BASE = "https://storage.googleapis.com/sefaria-export"


TORAH_BOOKS = [
    {"slug": "genesis", "title_en": "Genesis", "title_he": "בראשית", "order": 1, "chapters": 50},
    {"slug": "exodus", "title_en": "Exodus", "title_he": "שמות", "order": 2, "chapters": 40},
    {"slug": "leviticus", "title_en": "Leviticus", "title_he": "ויקרא", "order": 3, "chapters": 27},
    {"slug": "numbers", "title_en": "Numbers", "title_he": "במדבר", "order": 4, "chapters": 36},
    {"slug": "deuteronomy", "title_en": "Deuteronomy", "title_he": "דברים", "order": 5, "chapters": 34},
]


PARASHOT: dict[str, list[tuple[str, str, int, int, int, int]]] = {
    "Genesis": [
        ("בראשית", "Bereshit", 1, 1, 6, 8),
        ("נח", "Noach", 6, 9, 11, 32),
        ("לך לך", "Lech Lecha", 12, 1, 17, 27),
        ("וירא", "Vayera", 18, 1, 22, 24),
        ("חיי שרה", "Chayei Sara", 23, 1, 25, 18),
        ("תולדות", "Toldot", 25, 19, 28, 9),
        ("ויצא", "Vayetzei", 28, 10, 32, 3),
        ("וישלח", "Vayishlach", 32, 4, 36, 43),
        ("וישב", "Vayeshev", 37, 1, 40, 23),
        ("מקץ", "Miketz", 41, 1, 44, 17),
        ("ויגש", "Vayigash", 44, 18, 47, 27),
        ("ויחי", "Vayechi", 47, 28, 50, 26),
    ],
    "Exodus": [
        ("שמות", "Shemot", 1, 1, 6, 1),
        ("וארא", "Vaera", 6, 2, 9, 35),
        ("בא", "Bo", 10, 1, 13, 16),
        ("בשלח", "Beshalach", 13, 17, 17, 16),
        ("יתרו", "Yitro", 18, 1, 20, 23),
        ("משפטים", "Mishpatim", 21, 1, 24, 18),
        ("תרומה", "Terumah", 25, 1, 27, 19),
        ("תצוה", "Tetzaveh", 27, 20, 30, 10),
        ("כי תשא", "Ki Tisa", 30, 11, 34, 35),
        ("ויקהל", "Vayakhel", 35, 1, 38, 20),
        ("פקודי", "Pekudei", 38, 21, 40, 38),
    ],
    "Leviticus": [
        ("ויקרא", "Vayikra", 1, 1, 5, 26),
        ("צו", "Tzav", 6, 1, 8, 36),
        ("שמיני", "Shemini", 9, 1, 11, 47),
        ("תזריע", "Tazria", 12, 1, 13, 59),
        ("מצורע", "Metzora", 14, 1, 15, 33),
        ("אחרי מות", "Achrei Mot", 16, 1, 18, 30),
        ("קדושים", "Kedoshim", 19, 1, 20, 27),
        ("אמור", "Emor", 21, 1, 24, 23),
        ("בהר", "Behar", 25, 1, 26, 2),
        ("בחוקותי", "Bechukotai", 26, 3, 27, 34),
    ],
    "Numbers": [
        ("במדבר", "Bamidbar", 1, 1, 4, 20),
        ("נשא", "Nasso", 4, 21, 7, 89),
        ("בהעלותך", "Behaalotecha", 8, 1, 12, 16),
        ("שלח", "Shelach", 13, 1, 15, 41),
        ("קרח", "Korach", 16, 1, 18, 32),
        ("חקת", "Chukat", 19, 1, 22, 1),
        ("בלק", "Balak", 22, 2, 25, 9),
        ("פינחס", "Pinchas", 25, 10, 30, 1),
        ("מטות", "Matot", 30, 2, 32, 42),
        ("מסעי", "Masei", 33, 1, 36, 13),
    ],
    "Deuteronomy": [
        ("דברים", "Devarim", 1, 1, 3, 22),
        ("ואתחנן", "Vaetchanan", 3, 23, 7, 11),
        ("עקב", "Eikev", 7, 12, 11, 25),
        ("ראה", "Reeh", 11, 26, 16, 17),
        ("שופטים", "Shoftim", 16, 18, 21, 9),
        ("כי תצא", "Ki Teitzei", 21, 10, 25, 19),
        ("כי תבוא", "Ki Tavo", 26, 1, 29, 8),
        ("נצבים", "Nitzavim", 29, 9, 30, 20),
        ("וילך", "Vayelech", 31, 1, 31, 30),
        ("האזינו", "Haazinu", 32, 1, 32, 52),
        ("וזאת הברכה", "Vezot Haberakhah", 33, 1, 34, 12),
    ],
}


def _whole_ref(title_en: str, row: tuple[str, str, int, int, int, int]) -> str:
    _, _, sc, sv, ec, ev = row
    return f"{title_en} {sc}:{sv}-{ec}:{ev}"


def _text_url(title_en: str) -> str:
    filename = quote(f"{VERSION_TITLE}.json")
    return f"{GCS_BASE}/json/Tanakh/Torah/{title_en}/Hebrew/{filename}"


def _extract_chapters(payload: Any) -> list[list[str]]:
    if isinstance(payload, dict):
        chapters = payload.get("text")
    else:
        chapters = payload
    if not isinstance(chapters, list):
        raise RuntimeError("Unexpected Sefaria Export JSON structure: no text array")
    return chapters


class TorahImporter:
    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "Otzar-Israel/0.2"})

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

        text_url = _text_url(info["title_en"])
        response = self.client.get(text_url)
        response.raise_for_status()
        chapters = _extract_chapters(response.json())
        if len(chapters) != info["chapters"]:
            raise RuntimeError(f"Unexpected chapter count for {info['title_en']}: {len(chapters)}")

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

        for order, row in enumerate(PARASHOT[info["title_en"]], start=1):
            title_he, title_en, sc, sv, ec, ev = row
            self.db.add(TorahParasha(
                book_id=book.id,
                title_he=title_he,
                title_en=title_en,
                parasha_order=order,
                whole_ref=_whole_ref(info["title_en"], row),
                start_chapter=sc,
                start_verse=sv,
                end_chapter=ec,
                end_verse=ev,
            ))

        verse_count = 0
        for chapter_number, chapter in enumerate(chapters, start=1):
            if not isinstance(chapter, list):
                raise RuntimeError(f"Unexpected chapter shape for {info['title_en']} {chapter_number}")
            for verse_number, text in enumerate(chapter, start=1):
                if not isinstance(text, str) or not text.strip():
                    continue
                verse_count += 1
                self.db.add(TorahVerse(
                    book_id=book.id,
                    chapter=chapter_number,
                    verse=verse_number,
                    text_nikkud=text.strip(),
                    normalized_text=normalize_hebrew(text),
                    sefaria_ref=f"{info['title_en']} {chapter_number}:{verse_number}",
                ))
        self.db.commit()
        return {
            "book": info["title_he"],
            "status": "imported",
            "parashot": len(PARASHOT[info["title_en"]]),
            "verses": verse_count,
        }
