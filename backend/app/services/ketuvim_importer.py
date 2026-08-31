from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import KetuvimBook, KetuvimVerse
from app.services.text_utils import normalize_hebrew

VERSION_TITLE = "Tanach with Nikkud"
GCS_BASE = "https://storage.googleapis.com/sefaria-export"
SOURCE_URL = "https://www.sefaria.org/Psalms.1.1?lang=he&with=About"

KETUVIM_BOOKS = [
    {"slug":"psalms","title_en":"Psalms","title_he":"תהילים","order":1,"chapters":150},
    {"slug":"proverbs","title_en":"Proverbs","title_he":"משלי","order":2,"chapters":31},
    {"slug":"job","title_en":"Job","title_he":"איוב","order":3,"chapters":42},
    {"slug":"song-of-songs","title_en":"Song of Songs","title_he":"שיר השירים","order":4,"chapters":8},
    {"slug":"ruth","title_en":"Ruth","title_he":"רות","order":5,"chapters":4},
    {"slug":"lamentations","title_en":"Lamentations","title_he":"איכה","order":6,"chapters":5},
    {"slug":"ecclesiastes","title_en":"Ecclesiastes","title_he":"קהלת","order":7,"chapters":12},
    {"slug":"esther","title_en":"Esther","title_he":"אסתר","order":8,"chapters":10},
    {"slug":"daniel","title_en":"Daniel","title_he":"דניאל","order":9,"chapters":12},
    {"slug":"ezra","title_en":"Ezra","title_he":"עזרא","order":10,"chapters":10},
    {"slug":"nehemiah","title_en":"Nehemiah","title_he":"נחמיה","order":11,"chapters":13},
    {"slug":"i-chronicles","title_en":"I Chronicles","title_he":"דברי הימים א׳","order":12,"chapters":29},
    {"slug":"ii-chronicles","title_en":"II Chronicles","title_he":"דברי הימים ב׳","order":13,"chapters":36},
]


def _text_url(title_en: str) -> str:
    return f"{GCS_BASE}/json/Tanakh/Writings/{quote(title_en)}/Hebrew/{quote(VERSION_TITLE + '.json')}"


def _extract_chapters(payload: Any) -> list[list[str]]:
    chapters = payload.get("text") if isinstance(payload, dict) else payload
    if not isinstance(chapters, list):
        raise RuntimeError("Unexpected Sefaria Export JSON structure: no text array")
    return chapters


class KetuvimImporter:
    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent":"Otzar-Israel/0.4"})

    def close(self) -> None:
        self.client.close()

    def import_all(self, replace: bool = True) -> dict[str, Any]:
        if replace:
            self.db.execute(delete(KetuvimVerse))
            self.db.execute(delete(KetuvimBook))
            self.db.commit()
        summary=[]
        try:
            for info in KETUVIM_BOOKS:
                summary.append(self.import_book(info))
            return {"status":"ok","books":summary}
        finally:
            self.close()

    def import_book(self, info: dict[str, Any]) -> dict[str, Any]:
        if self.db.scalar(select(KetuvimBook).where(KetuvimBook.slug==info["slug"])):
            return {"book":info["title_he"],"status":"exists"}
        response=self.client.get(_text_url(info["title_en"]))
        response.raise_for_status()
        chapters=_extract_chapters(response.json())
        if len(chapters)!=info["chapters"]:
            raise RuntimeError(f"Unexpected chapter count for {info['title_en']}: {len(chapters)} expected {info['chapters']}")
        book=KetuvimBook(slug=info["slug"],title_he=info["title_he"],title_en=info["title_en"],book_order=info["order"],chapter_count=info["chapters"],source_name=VERSION_TITLE,source_url=SOURCE_URL,license="Public Domain")
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
                self.db.add(KetuvimVerse(book_id=book.id,chapter=chapter_number,verse=verse_number,text_nikkud=text.strip(),normalized_text=normalize_hebrew(text),sefaria_ref=f"{info['title_en']} {chapter_number}:{verse_number}"))
        self.db.commit()
        return {"book":info["title_he"],"status":"imported","verses":verse_count}
