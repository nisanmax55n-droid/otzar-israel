from __future__ import annotations

import re
from typing import Any, Iterable

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.talmud import TalmudSegment, TalmudTractate
from app.services.text_utils import normalize_hebrew

BOOKS_INDEX = "https://raw.githubusercontent.com/Sefaria/Sefaria-Export/master/books.json"
ALLOWED_LICENSE_PREFIXES = ("Public Domain", "CC0", "CC-BY", "CC-BY-SA")
TRADITIONS = {"bavli": "Bavli", "yerushalmi": "Yerushalmi"}

BAVLI_CANON = [
    ("Zeraim", "Berakhot", "ברכות"),
    ("Moed", "Shabbat", "שבת"), ("Moed", "Eruvin", "עירובין"), ("Moed", "Pesachim", "פסחים"),
    ("Moed", "Rosh Hashanah", "ראש השנה"), ("Moed", "Yoma", "יומא"), ("Moed", "Sukkah", "סוכה"),
    ("Moed", "Beitzah", "ביצה"), ("Moed", "Taanit", "תענית"), ("Moed", "Megillah", "מגילה"),
    ("Moed", "Moed Katan", "מועד קטן"), ("Moed", "Chagigah", "חגיגה"),
    ("Nashim", "Yevamot", "יבמות"), ("Nashim", "Ketubot", "כתובות"), ("Nashim", "Nedarim", "נדרים"),
    ("Nashim", "Nazir", "נזיר"), ("Nashim", "Sotah", "סוטה"), ("Nashim", "Gittin", "גיטין"),
    ("Nashim", "Kiddushin", "קידושין"),
    ("Nezikin", "Bava Kamma", "בבא קמא"), ("Nezikin", "Bava Metzia", "בבא מציעא"),
    ("Nezikin", "Bava Batra", "בבא בתרא"), ("Nezikin", "Sanhedrin", "סנהדרין"),
    ("Nezikin", "Makkot", "מכות"), ("Nezikin", "Shevuot", "שבועות"),
    ("Nezikin", "Avodah Zarah", "עבודה זרה"), ("Nezikin", "Horayot", "הוריות"),
    ("Kodashim", "Zevachim", "זבחים"), ("Kodashim", "Menachot", "מנחות"),
    ("Kodashim", "Chullin", "חולין"), ("Kodashim", "Bekhorot", "בכורות"),
    ("Kodashim", "Arakhin", "ערכין"), ("Kodashim", "Temurah", "תמורה"),
    ("Kodashim", "Keritot", "כריתות"), ("Kodashim", "Meilah", "מעילה"),
    ("Kodashim", "Tamid", "תמיד"), ("Tohorot", "Niddah", "נדה"),
]

YERUSHALMI_CANON = [
    ("Zeraim", "Jerusalem Talmud Berakhot", "ברכות"), ("Zeraim", "Jerusalem Talmud Peah", "פאה"),
    ("Zeraim", "Jerusalem Talmud Demai", "דמאי"), ("Zeraim", "Jerusalem Talmud Kilayim", "כלאים"),
    ("Zeraim", "Jerusalem Talmud Sheviit", "שביעית"), ("Zeraim", "Jerusalem Talmud Terumot", "תרומות"),
    ("Zeraim", "Jerusalem Talmud Maasrot", "מעשרות"), ("Zeraim", "Jerusalem Talmud Maaser Sheni", "מעשר שני"),
    ("Zeraim", "Jerusalem Talmud Challah", "חלה"), ("Zeraim", "Jerusalem Talmud Orlah", "ערלה"),
    ("Zeraim", "Jerusalem Talmud Bikkurim", "ביכורים"),
    ("Moed", "Jerusalem Talmud Shabbat", "שבת"), ("Moed", "Jerusalem Talmud Eruvin", "עירובין"),
    ("Moed", "Jerusalem Talmud Pesachim", "פסחים"), ("Moed", "Jerusalem Talmud Yoma", "יומא"),
    ("Moed", "Jerusalem Talmud Shekalim", "שקלים"), ("Moed", "Jerusalem Talmud Sukkah", "סוכה"),
    ("Moed", "Jerusalem Talmud Rosh Hashanah", "ראש השנה"), ("Moed", "Jerusalem Talmud Beitzah", "ביצה"),
    ("Moed", "Jerusalem Talmud Taanit", "תענית"), ("Moed", "Jerusalem Talmud Megillah", "מגילה"),
    ("Moed", "Jerusalem Talmud Chagigah", "חגיגה"), ("Moed", "Jerusalem Talmud Moed Katan", "מועד קטן"),
    ("Nashim", "Jerusalem Talmud Yevamot", "יבמות"), ("Nashim", "Jerusalem Talmud Sotah", "סוטה"),
    ("Nashim", "Jerusalem Talmud Ketubot", "כתובות"), ("Nashim", "Jerusalem Talmud Nedarim", "נדרים"),
    ("Nashim", "Jerusalem Talmud Nazir", "נזיר"), ("Nashim", "Jerusalem Talmud Gittin", "גיטין"),
    ("Nashim", "Jerusalem Talmud Kiddushin", "קידושין"),
    ("Nezikin", "Jerusalem Talmud Bava Kamma", "בבא קמא"), ("Nezikin", "Jerusalem Talmud Bava Metzia", "בבא מציעא"),
    ("Nezikin", "Jerusalem Talmud Bava Batra", "בבא בתרא"), ("Nezikin", "Jerusalem Talmud Sanhedrin", "סנהדרין"),
    ("Nezikin", "Jerusalem Talmud Shevuot", "שבועות"), ("Nezikin", "Jerusalem Talmud Avodah Zarah", "עבודה זרה"),
    ("Nezikin", "Jerusalem Talmud Makkot", "מכות"), ("Nezikin", "Jerusalem Talmud Horayot", "הוריות"),
]

CANON = {"bavli": BAVLI_CANON, "yerushalmi": YERUSHALMI_CANON}


def _slug(title: str) -> str:
    value = title.strip().lower().replace("'", "").replace("’", "")
    value = re.sub(r"^(babylonian talmud|jerusalem talmud)\s+", "", value)
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def _allowed_license(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    license_name = value.strip()
    if not license_name or "NC" in license_name.upper():
        return None
    if any(license_name == prefix or license_name.startswith(prefix + " ") for prefix in ALLOWED_LICENSE_PREFIXES):
        return license_name
    return None


def _flatten_strings(node: Any, path: tuple[int, ...] = ()) -> Iterable[tuple[tuple[int, ...], str]]:
    if isinstance(node, str):
        cleaned = node.strip()
        if cleaned:
            yield path, cleaned
        return
    if isinstance(node, list):
        for index, child in enumerate(node, start=1):
            yield from _flatten_strings(child, path + (index,))


def _bavli_label(section: int) -> str:
    page = 2 + (section - 1) // 2
    side = "a" if section % 2 else "b"
    return f"{page}{side}"


def _section_ref(title: str, tradition: str, section: int, path: tuple[int, ...]) -> str:
    base = f"{title} {_bavli_label(section)}" if tradition == "bavli" else f"{title} {section}"
    suffix = ":".join(str(x) for x in path)
    return f"{base}:{suffix}" if suffix else base


class TalmudImporter:
    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.Client(timeout=180, follow_redirects=True, headers={"User-Agent": "Otzar-Israel/0.8"})

    def close(self) -> None:
        self.client.close()

    def _records(self, tradition: str) -> list[dict[str, Any]]:
        response = self.client.get(BOOKS_INDEX)
        response.raise_for_status()
        payload = response.json()
        books = payload.get("books", []) if isinstance(payload, dict) else []
        by_title: dict[str, list[dict[str, Any]]] = {}
        for record in books:
            if not isinstance(record, dict):
                continue
            if str(record.get("language", "")).lower() not in {"hebrew", "he"}:
                continue
            if str(record.get("versionTitle", "")).strip().lower() == "merged":
                continue
            title = str(record.get("title", "")).strip()
            if title and record.get("json_url"):
                by_title.setdefault(title, []).append(record)

        result: list[dict[str, Any]] = []
        for order, (seder_name, title_en, title_he) in enumerate(CANON[tradition], start=1):
            candidates = sorted(
                by_title.get(title_en, []),
                key=lambda r: ("wikisource" not in str(r.get("versionTitle", "")).lower(), str(r.get("versionTitle", ""))),
            )
            result.append({
                "title": title_en,
                "title_he": title_he,
                "seder_name": seder_name,
                "canonical_order": order,
                "candidates": candidates,
            })
        return result

    def import_tradition(self, tradition: str, replace: bool = True, max_tractates: int | None = None) -> dict[str, Any]:
        if tradition not in TRADITIONS:
            raise ValueError("tradition must be bavli or yerushalmi")
        if replace:
            ids = list(self.db.scalars(select(TalmudTractate.id).where(TalmudTractate.tradition == tradition)).all())
            if ids:
                self.db.execute(delete(TalmudSegment).where(TalmudSegment.tractate_id.in_(ids)))
            self.db.execute(delete(TalmudTractate).where(TalmudTractate.tradition == tradition))
            self.db.commit()

        records = self._records(tradition)
        if max_tractates and max_tractates > 0:
            records = records[:max_tractates]

        imported: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        try:
            for order, record in enumerate(records, start=1):
                result = self.import_tractate(tradition, order, record)
                if result.get("status") == "skipped":
                    skipped.append({"title": str(record.get("title", "")), "reason": str(result.get("reason", ""))})
                else:
                    imported.append(result)
            self.db.commit()
            return {"status": "ok", "tradition": tradition, "imported": imported, "skipped": skipped}
        except Exception:
            self.db.rollback()
            raise
        finally:
            self.close()

    def import_tractate(self, tradition: str, order: int, record: dict[str, Any]) -> dict[str, Any]:
        title_en = str(record.get("title", "")).strip()
        title_he = str(record.get("title_he", "")).strip()
        candidates = record.get("candidates") or []
        rejection_reasons: list[str] = []

        chosen_payload: dict[str, Any] | None = None
        chosen_record: dict[str, Any] | None = None
        chosen_license: str | None = None
        for candidate in candidates:
            source_url = str(candidate.get("json_url", ""))
            version_title = str(candidate.get("versionTitle", "")).strip()
            try:
                response = self.client.get(source_url)
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                rejection_reasons.append(f"{version_title}: download failed ({type(exc).__name__})")
                continue
            if not isinstance(payload, dict):
                rejection_reasons.append(f"{version_title}: unexpected JSON structure")
                continue
            license_name = _allowed_license(payload.get("license"))
            if not license_name:
                rejection_reasons.append(f"{version_title}: license not approved ({payload.get('license')!r})")
                continue
            text = payload.get("text")
            if not isinstance(text, list) or not text:
                rejection_reasons.append(f"{version_title}: missing text")
                continue
            chosen_payload, chosen_record, chosen_license = payload, candidate, license_name
            break

        if not chosen_payload or not chosen_record or not chosen_license:
            reason = "; ".join(rejection_reasons[:6]) or "no approved Hebrew version found"
            return {"status": "skipped", "reason": reason}

        text = chosen_payload["text"]
        version_title = str(chosen_record.get("versionTitle", "")).strip() or "unnamed version"
        source_url = str(chosen_record["json_url"])
        tractate = TalmudTractate(
            tradition=tradition,
            seder_name=str(record.get("seder_name", "")),
            slug=_slug(title_en),
            title_he=title_he,
            title_en=title_en,
            tractate_order=order,
            section_count=len(text),
            source_name=f"Sefaria Export - {version_title}",
            source_url=source_url,
            license=chosen_license,
            license_verified=True,
        )
        self.db.add(tractate)
        self.db.flush()

        segment_count = 0
        for section_no, section_node in enumerate(text, start=1):
            position = 0
            for path, segment_text in _flatten_strings(section_node):
                position += 1
                self.db.add(TalmudSegment(
                    tractate_id=tractate.id,
                    section=section_no,
                    position=position,
                    path=".".join(str(x) for x in path),
                    text=segment_text,
                    normalized_text=normalize_hebrew(segment_text),
                    sefaria_ref=_section_ref(title_en, tradition, section_no, path),
                ))
                segment_count += 1
        self.db.flush()
        return {
            "status": "imported",
            "title": title_he,
            "version": version_title,
            "sections": len(text),
            "segments": segment_count,
            "license": chosen_license,
        }
