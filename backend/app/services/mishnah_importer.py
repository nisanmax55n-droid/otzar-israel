from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.mishnah import MishnahSeder, MishnahTractate, MishnahUnit
from app.services.text_utils import normalize_hebrew

GCS_BASE = "https://storage.googleapis.com/sefaria-export/json/Mishnah"
SOURCE_NAME = "Sefaria Export - Hebrew merged"
LICENSE = "Sefaria Export - copyright-filtered"

SEDARIM = [
    {
        "slug": "zeraim", "title_he": "זרעים", "title_en": "Zeraim", "order": 1, "path": "Seder Zeraim",
        "tractates": [
            ("berakhot", "ברכות", "Mishnah Berakhot"),
            ("peah", "פאה", "Mishnah Peah"),
            ("demai", "דמאי", "Mishnah Demai"),
            ("kilayim", "כלאים", "Mishnah Kilayim"),
            ("sheviit", "שביעית", "Mishnah Sheviit"),
            ("terumot", "תרומות", "Mishnah Terumot"),
            ("maasrot", "מעשרות", "Mishnah Maasrot"),
            ("maaser-sheni", "מעשר שני", "Mishnah Maaser Sheni"),
            ("challah", "חלה", "Mishnah Challah"),
            ("orlah", "ערלה", "Mishnah Orlah"),
            ("bikkurim", "ביכורים", "Mishnah Bikkurim"),
        ],
    },
    {
        "slug": "moed", "title_he": "מועד", "title_en": "Moed", "order": 2, "path": "Seder Moed",
        "tractates": [
            ("shabbat", "שבת", "Mishnah Shabbat"),
            ("eruvin", "עירובין", "Mishnah Eruvin"),
            ("pesachim", "פסחים", "Mishnah Pesachim"),
            ("shekalim", "שקלים", "Mishnah Shekalim"),
            ("yoma", "יומא", "Mishnah Yoma"),
            ("sukkah", "סוכה", "Mishnah Sukkah"),
            ("beitzah", "ביצה", "Mishnah Beitzah"),
            ("rosh-hashanah", "ראש השנה", "Mishnah Rosh Hashanah"),
            ("taanit", "תענית", "Mishnah Taanit"),
            ("megillah", "מגילה", "Mishnah Megillah"),
            ("moed-katan", "מועד קטן", "Mishnah Moed Katan"),
            ("chagigah", "חגיגה", "Mishnah Chagigah"),
        ],
    },
    {
        "slug": "nashim", "title_he": "נשים", "title_en": "Nashim", "order": 3, "path": "Seder Nashim",
        "tractates": [
            ("yevamot", "יבמות", "Mishnah Yevamot"),
            ("ketubot", "כתובות", "Mishnah Ketubot"),
            ("nedarim", "נדרים", "Mishnah Nedarim"),
            ("nazir", "נזיר", "Mishnah Nazir"),
            ("sotah", "סוטה", "Mishnah Sotah"),
            ("gittin", "גיטין", "Mishnah Gittin"),
            ("kiddushin", "קידושין", "Mishnah Kiddushin"),
        ],
    },
    {
        "slug": "nezikin", "title_he": "נזיקין", "title_en": "Nezikin", "order": 4, "path": "Seder Nezikin",
        "tractates": [
            ("bava-kamma", "בבא קמא", "Mishnah Bava Kamma"),
            ("bava-metzia", "בבא מציעא", "Mishnah Bava Metzia"),
            ("bava-batra", "בבא בתרא", "Mishnah Bava Batra"),
            ("sanhedrin", "סנהדרין", "Mishnah Sanhedrin"),
            ("makkot", "מכות", "Mishnah Makkot"),
            ("shevuot", "שבועות", "Mishnah Shevuot"),
            ("eduyot", "עדויות", "Mishnah Eduyot"),
            ("avodah-zarah", "עבודה זרה", "Mishnah Avodah Zarah"),
            ("avot", "אבות", "Pirkei Avot"),
            ("horayot", "הוריות", "Mishnah Horayot"),
        ],
    },
    {
        "slug": "kodashim", "title_he": "קדשים", "title_en": "Kodashim", "order": 5, "path": "Seder Kodashim",
        "tractates": [
            ("zevachim", "זבחים", "Mishnah Zevachim"),
            ("menachot", "מנחות", "Mishnah Menachot"),
            ("chullin", "חולין", "Mishnah Chullin"),
            ("bekhorot", "בכורות", "Mishnah Bekhorot"),
            ("arakhin", "ערכין", "Mishnah Arakhin"),
            ("temurah", "תמורה", "Mishnah Temurah"),
            ("keritot", "כריתות", "Mishnah Keritot"),
            ("meilah", "מעילה", "Mishnah Meilah"),
            ("tamid", "תמיד", "Mishnah Tamid"),
            ("middot", "מידות", "Mishnah Middot"),
            ("kinnim", "קינים", "Mishnah Kinnim"),
        ],
    },
    {
        "slug": "tohorot", "title_he": "טהרות", "title_en": "Tohorot", "order": 6, "path": "Seder Tohorot",
        "tractates": [
            ("kelim", "כלים", "Mishnah Kelim"),
            ("oholot", "אהלות", "Mishnah Oholot"),
            ("negaim", "נגעים", "Mishnah Negaim"),
            ("parah", "פרה", "Mishnah Parah"),
            ("tahorot", "טהרות", "Mishnah Tahorot"),
            ("mikvaot", "מקוואות", "Mishnah Mikvaot"),
            ("niddah", "נדה", "Mishnah Niddah"),
            ("makhshirin", "מכשירין", "Mishnah Makhshirin"),
            ("zavim", "זבים", "Mishnah Zavim"),
            ("tevul-yom", "טבול יום", "Mishnah Tevul Yom"),
            ("yadayim", "ידים", "Mishnah Yadayim"),
            ("oktzin", "עוקצין", "Mishnah Oktzin"),
        ],
    },
]


def _url(seder_path: str, title_en: str) -> str:
    return f"{GCS_BASE}/{quote(seder_path)}/{quote(title_en)}/Hebrew/merged.json"


def _extract_chapters(payload: Any) -> list[list[str]]:
    chapters = payload.get("text") if isinstance(payload, dict) else payload
    if not isinstance(chapters, list):
        raise RuntimeError("Unexpected Mishnah export structure")
    return chapters


class MishnahImporter:
    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "Otzar-Israel/0.5"})

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
        finally:
            self.close()

    def import_seder(self, info: dict[str, Any]) -> dict[str, Any]:
        seder = MishnahSeder(slug=info["slug"], title_he=info["title_he"], title_en=info["title_en"], seder_order=info["order"])
        self.db.add(seder)
        self.db.flush()
        tractates = []
        for order, (slug, title_he, title_en) in enumerate(info["tractates"], start=1):
            tractates.append(self.import_tractate(seder, info["path"], order, slug, title_he, title_en))
        self.db.commit()
        return {"seder": info["title_he"], "tractates": tractates}

    def import_tractate(self, seder: MishnahSeder, seder_path: str, order: int, slug: str, title_he: str, title_en: str) -> dict[str, Any]:
        source_url = _url(seder_path, title_en)
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
