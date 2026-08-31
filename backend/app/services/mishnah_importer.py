from __future__ import annotations

import re
from typing import Any

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.mishnah import MishnahSeder, MishnahTractate, MishnahUnit
from app.services.text_utils import normalize_hebrew

BOOKS_INDEX = "https://raw.githubusercontent.com/Sefaria/Sefaria-Export/master/books.json"
SOURCE_NAME = "Sefaria Export - Hebrew merged"
LICENSE = "Sefaria Export - copyright-filtered"

SEDARIM = [
    {
        "slug": "zeraim", "title_he": "זרעים", "title_en": "Zeraim", "order": 1,
        "tractates": [
            ("berakhot", "ברכות", "Mishnah Berakhot"), ("peah", "פאה", "Mishnah Peah"),
            ("demai", "דמאי", "Mishnah Demai"), ("kilayim", "כלאים", "Mishnah Kilayim"),
            ("sheviit", "שביעית", "Mishnah Sheviit"), ("terumot", "תרומות", "Mishnah Terumot"),
            ("maasrot", "מעשרות", "Mishnah Maasrot"), ("maaser-sheni", "מעשר שני", "Mishnah Maaser Sheni"),
            ("challah", "חלה", "Mishnah Challah"), ("orlah", "ערלה", "Mishnah Orlah"),
            ("bikkurim", "ביכורים", "Mishnah Bikkurim"),
        ],
    },
    {
        "slug": "moed", "title_he": "מועד", "title_en": "Moed", "order": 2,
        "tractates": [
            ("shabbat", "שבת", "Mishnah Shabbat"), ("eruvin", "עירובין", "Mishnah Eruvin"),
            ("pesachim", "פסחים", "Mishnah Pesachim"), ("shekalim", "שקלים", "Mishnah Shekalim"),
            ("yoma", "יומא", "Mishnah Yoma"), ("sukkah", "סוכה", "Mishnah Sukkah"),
            ("beitzah", "ביצה", "Mishnah Beitzah"), ("rosh-hashanah", "ראש השנה", "Mishnah Rosh Hashanah"),
            ("taanit", "תענית", "Mishnah Ta'anit"), ("megillah", "מגילה", "Mishnah Megillah"),
            ("moed-katan", "מועד קטן", "Mishnah Moed Katan"), ("chagigah", "חגיגה", "Mishnah Chagigah"),
        ],
    },
    {
        "slug": "nashim", "title_he": "נשים", "title_en": "Nashim", "order": 3,
        "tractates": [
            ("yevamot", "יבמות", "Mishnah Yevamot"), ("ketubot", "כתובות", "Mishnah Ketubot"),
            ("nedarim", "נדרים", "Mishnah Nedarim"), ("nazir", "נזיר", "Mishnah Nazir"),
            ("sotah", "סוטה", "Mishnah Sotah"), ("gittin", "גיטין", "Mishnah Gittin"),
            ("kiddushin", "קידושין", "Mishnah Kiddushin"),
        ],
    },
    {
        "slug": "nezikin", "title_he": "נזיקין", "title_en": "Nezikin", "order": 4,
        "tractates": [
            ("bava-kamma", "בבא קמא", "Mishnah Bava Kamma"), ("bava-metzia", "בבא מציעא", "Mishnah Bava Metzia"),
            ("bava-batra", "בבא בתרא", "Mishnah Bava Batra"), ("sanhedrin", "סנהדרין", "Mishnah Sanhedrin"),
            ("makkot", "מכות", "Mishnah Makkot"), ("shevuot", "שבועות", "Mishnah Shevuot"),
            ("eduyot", "עדויות", "Mishnah Eduyot"), ("avodah-zarah", "עבודה זרה", "Mishnah Avodah Zarah"),
            ("avot", "אבות", "Pirkei Avot"), ("horayot", "הוריות", "Mishnah Horayot"),
        ],
    },
    {
        "slug": "kodashim", "title_he": "קדשים", "title_en": "Kodashim", "order": 5,
        "tractates": [
            ("zevachim", "זבחים", "Mishnah Zevachim"), ("menachot", "מנחות", "Mishnah Menachot"),
            ("chullin", "חולין", "Mishnah Chullin"), ("bekhorot", "בכורות", "Mishnah Bekhorot"),
            ("arakhin", "ערכין", "Mishnah Arakhin"), ("temurah", "תמורה", "Mishnah Temurah"),
            ("keritot", "כריתות", "Mishnah Keritot"), ("meilah", "מעילה", "Mishnah Meilah"),
            ("tamid", "תמיד", "Mishnah Tamid"), ("middot", "מידות", "Mishnah Middot"),
            ("kinnim", "קינים", "Mishnah Kinnim"),
        ],
    },
    {
        "slug": "tohorot", "title_he": "טהרות", "title_en": "Tohorot", "order": 6,
        "tractates": [
            ("kelim", "כלים", "Mishnah Kelim"), ("oholot", "אהלות", "Mishnah Oholot"),
            ("negaim", "נגעים", "Mishnah Negaim"), ("parah", "פרה", "Mishnah Parah"),
            ("tahorot", "טהרות", "Mishnah Tahorot"), ("mikvaot", "מקוואות", "Mishnah Mikvaot"),
            ("niddah", "נדה", "Mishnah Niddah"), ("makhshirin", "מכשירין", "Mishnah Makhshirin"),
            ("zavim", "זבים", "Mishnah Zavim"), ("tevul-yom", "טבול יום", "Mishnah Tevul Yom"),
            ("yadayim", "ידים", "Mishnah Yadayim"), ("oktzin", "עוקצין", "Mishnah Oktzin"),
        ],
    },
]


def _title_slug(title: str) -> str:
    value = title.strip().lower()
    if value.startswith("mishnah "):
        value = value[8:]
    value = value.replace("'", "").replace("’", "").replace("ʻ", "")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value


def _extract_chapters(payload: Any) -> list[list[str]]:
    chapters = payload.get("text") if isinstance(payload, dict) else payload
    if not isinstance(chapters, list):
        raise RuntimeError("Unexpected Mishnah export structure")
    return chapters


class MishnahImporter:
    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "Otzar-Israel/0.6"})
        self.records = self._load_export_index()

    def _load_export_index(self) -> dict[str, dict[str, Any]]:
        response = self.client.get(BOOKS_INDEX)
        response.raise_for_status()
        payload = response.json()
        books = payload.get("books", []) if isinstance(payload, dict) else []
        result: dict[str, dict[str, Any]] = {}
        for record in books:
            if not isinstance(record, dict):
                continue
            language = str(record.get("language", "")).lower()
            categories = record.get("categories") or []
            if language not in {"hebrew", "he"} or record.get("versionTitle") != "merged" or "Mishnah" not in categories:
                continue
            title = str(record.get("title", ""))
            json_url = record.get("json_url")
            if title and json_url:
                result[_title_slug(title)] = record
        if not result:
            raise RuntimeError("No Hebrew merged Mishnah records found in Sefaria Export index")
        return result

    def _record_for(self, slug: str) -> dict[str, Any]:
        aliases = [slug]
        if slug == "avot":
            aliases.append("pirkei-avot")
        for candidate in aliases:
            if candidate in self.records:
                return self.records[candidate]
        raise RuntimeError(f"Missing Mishnah export record for {slug}")

    def close(self) -> None:
        self.client.close()

    def import_all(self, replace: bool = True) -> dict[str, Any]:
        if replace:
            self.db.execute(delete(MishnahUnit))
            self.db.execute(delete(MishnahTractate))
            self.db.execute(delete(MishnahSeder))
            self.db.commit()
        result: list[dict[str, Any]] = []
        try:
            for seder_info in SEDARIM:
                result.append(self.import_seder(seder_info))
            return {"status": "ok", "sedarim": result}
        except Exception:
            self.db.rollback()
            raise
        finally:
            self.close()

    def import_seder(self, info: dict[str, Any]) -> dict[str, Any]:
        seder = MishnahSeder(slug=info["slug"], title_he=info["title_he"], title_en=info["title_en"], seder_order=info["order"])
        self.db.add(seder)
        self.db.flush()
        tractates = []
        for order, (slug, title_he, fallback_title) in enumerate(info["tractates"], start=1):
            tractates.append(self.import_tractate(seder, order, slug, title_he, fallback_title))
        self.db.commit()
        return {"seder": info["title_he"], "tractates": tractates}

    def import_tractate(self, seder: MishnahSeder, order: int, slug: str, title_he: str, fallback_title: str) -> dict[str, Any]:
        record = self._record_for(slug)
        source_url = str(record["json_url"])
        title_en = str(record.get("title") or fallback_title)
        response = self.client.get(source_url)
        response.raise_for_status()
        chapters = _extract_chapters(response.json())
        tractate = MishnahTractate(
            seder_id=seder.id,
            slug=slug,
            title_he=title_he,
            title_en=title_en,
            tractate_order=order,
            chapter_count=len(chapters),
            source_name=SOURCE_NAME,
            source_url=source_url,
            license=LICENSE,
        )
        self.db.add(tractate)
        self.db.flush()
        count = 0
        for chapter_no, chapter in enumerate(chapters, start=1):
            if not isinstance(chapter, list):
                raise RuntimeError(f"Unexpected chapter shape: {title_en} {chapter_no}")
            for mishnah_no, text in enumerate(chapter, start=1):
                if not isinstance(text, str) or not text.strip():
                    continue
                cleaned = text.strip()
                self.db.add(MishnahUnit(
                    tractate_id=tractate.id,
                    chapter=chapter_no,
                    mishnah=mishnah_no,
                    text=cleaned,
                    normalized_text=normalize_hebrew(cleaned),
                    sefaria_ref=f"{title_en} {chapter_no}:{mishnah_no}",
                ))
                count += 1
        self.db.flush()
        return {"tractate": title_he, "chapters": len(chapters), "mishnayot": count}
