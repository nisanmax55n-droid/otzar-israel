from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import NeviimBook, NeviimVerse
from app.services.text_utils import normalize_hebrew

VERSION_TITLE = "Tanach with Nikkud"
GCS_BASE = "https://storage.googleapis.com/sefaria-export"
SOURCE_URL = "https://www.sefaria.org/Joshua.1.1?lang=he&with=About"

NEVIIM_BOOKS = [
    {"slug":"joshua","title_en":"Joshua","title_he":"יהושע","order":1,"chapters":24},
    {"slug":"judges","title_en":"Judges","title_he":"שופטים","order":2,"chapters":21},
    {"slug":"i-samuel","title_en":"I Samuel","title_he":"שמואל א׳","order":3,"chapters":31},
    {"slug":"ii-samuel","title_en":"II Samuel","title_he":"שמואל ב׳","order":4,"chapters":24},
    {"slug":"i-kings","title_en":"I Kings","title_he":"מלכים א׳","order":5,"chapters":22},
    {"slug":"ii-kings","title_en":"II Kings","title_he":"מלכים ב׳","order":6,"chapters":25},
    {"slug":"isaiah","title_en":"Isaiah","title_he":"ישעיהו","order":7,"chapters":66},
    {"slug":"jeremiah","title_en":"Jeremiah","title_he":"ירמיהו","order":8,"chapters":52},
    {"slug":"ezekiel","title_en":"Ezekiel","title_he":"יחזקאל","order":9,"chapters":48},
    {"slug":"hosea","title_en":"Hosea","title_he":"הושע","order":10,"chapters":14},
    {"slug":"joel","title_en":"Joel","title_he":"יואל","order":11,"chapters":4},
    {"slug":"amos","title_en":"Amos","title_he":"עמוס","order":12,"chapters":9},
    {"slug":"obadiah","title_en":"Obadiah","title_he":"עובדיה","order":13,"chapters":1},
    {"slug":"jonah","title_en":"Jonah","title_he":"יונה","order":14,"chapters":4},
    {"slug":"micah","title_en":"Micah","title_he":"מיכה","order":15,"chapters":7},
    {"slug":"nahum","title_en":"Nahum","title_he":"נחום","order":16,"chapters":3},
    {"slug":"habakkuk","title_en":"Habakkuk","title_he":"חבקוק","order":17,"chapters":3},
    {"slug":"zephaniah","title_en":"Zephaniah","title_he":"צפניה","order":18,"chapters":3},
    {"slug":"haggai","title_en":"Haggai","title_he":"חגי","order":19,"chapters":2},
    {"slug":"zechariah","title_en":"Zechariah","title_he":"זכריה","order":20,"chapters":14},
    {"slug":"malachi","title_en":"Malachi","title_he":"מלאכי","order":21,"chapters":3},
]


def _text_url(title_en: str) -> str:
    return f"{GCS_BASE}/json/Tanakh/Prophets/{quote(title_en)}/Hebrew/{quote(VERSION_TITLE + '.json')}"


def _extract_chapters(payload: Any) -> list[list[str]]:
    chapters = payload.get("text") if isinstance(payload, dict) else payload
    if not isinstance(chapters, list):
        raise RuntimeError("Unexpected Sefaria Export JSON structure: no text array")
    return chapters


class NeviimImporter:
    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent":"Otzar-Israel/0.3"})

    def close(self) -> None:
        self.client.close()

    def import_all(self, replace: bool = True) -> dict[str, Any]:
        if replace:
            self.db.execute(delete(NeviimVerse))
            self.db.execute(delete(NeviimBook))
            self.db.commit()
        summary=[]
        try:
            for info in NEVIIM_BOOKS:
                summary.append(self.import_book(info))
            return {"status":"ok","books":summary}
        finally:
            self.close()

    def import_book(self, info: dict[str, Any]) -> dict[str, Any]:
        if self.db.scalar(select(NeviimBook).where(NeviimBook.slug==info["slug"])):
            return {"book":info["title_he"],"status":"exists"}
        response=self.client.get(_text_url(info["title_en"]))
        response.raise_for_status()
        chapters=_extract_chapters(response.json())
        if len(chapters)!=info["chapters"]:
            raise RuntimeError(f"Unexpected chapter count for {info['title_en']}: {len(chapters)} expected {info['chapters']}")
        book=NeviimBook(slug=info["slug"],title_he=info["title_he"],title_en=info["title_en"],book_order=info["order"],chapter_count=info["chapters"],source_name=VERSION_TITLE,source_url=SOURCE_URL,license="Public Domain")
        self.db.add(book)
        self.db.flush()
        verse_count=0
        for chapter_number,chapter in enumerate(chapters,start=1):
            if not isinstance(chapter,list):
                raise RuntimeError(f"Unexpected chapter shape for {info['title_en']} {chapter_number}")
            for verse_number,text in enumerate(chapter,start=1):
                if not isinstance(text,str) or not text.strip():
                    continue
                verse_count+=1
                self.db.add(NeviimVerse(book_id=book.id,chapter=chapter_number,verse=verse_number,text_nikkud=text.strip(),normalized_text=normalize_hebrew(text),sefaria_ref=f"{info['title_en']} {chapter_number}:{verse_number}"))
        self.db.commit()
        return {"book":info["title_he"],"status":"imported","verses":verse_count}
