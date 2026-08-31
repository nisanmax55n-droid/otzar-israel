from __future__ import annotations

import re
from typing import Any, Iterable

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.talmud import TalmudSegment, TalmudTractate
from app.services.text_utils import normalize_hebrew

BOOKS_INDEX = "https://raw.githubusercontent.com/Sefaria/Sefaria-Export/master/books.json"
SOURCE_NAME = "Sefaria Export - Hebrew merged"
ALLOWED_LICENSE_PREFIXES = ("Public Domain", "CC0", "CC-BY", "CC-BY-SA")
TRADITIONS = {"bavli": "Bavli", "yerushalmi": "Yerushalmi"}
SEDER_ORDER = {
    "Seder Zeraim": 1,
    "Seder Moed": 2,
    "Seder Nashim": 3,
    "Seder Nezikin": 4,
    "Seder Kodashim": 5,
    "Seder Tohorot": 6,
}


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
    if tradition == "bavli":
        base = f"{title} {_bavli_label(section)}"
    else:
        base = f"{title} {section}"
    suffix = ":".join(str(x) for x in path)
    return f"{base}:{suffix}" if suffix else base


class TalmudImporter:
    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.Client(timeout=180, follow_redirects=True, headers={"User-Agent": "Otzar-Israel/0.7"})

    def close(self) -> None:
        self.client.close()

    def _records(self, tradition: str) -> list[dict[str, Any]]:
        sefaria_category = TRADITIONS[tradition]
        response = self.client.get(BOOKS_INDEX)
        response.raise_for_status()
        payload = response.json()
        books = payload.get("books", []) if isinstance(payload, dict) else []
        records: list[dict[str, Any]] = []
        for record in books:
            if not isinstance(record, dict):
                continue
            categories = record.get("categories") or []
            language = str(record.get("language", "")).lower()
            if language not in {"hebrew", "he"}:
                continue
            if record.get("versionTitle") != "merged":
                continue
            if "Talmud" not in categories or sefaria_category not in categories:
                continue
            if not record.get("json_url") or not record.get("title"):
                continue
            records.append(record)

        def sort_key(record: dict[str, Any]) -> tuple[int, str]:
            categories = record.get("categories") or []
            seder = next((c for c in categories if isinstance(c, str) and c.startswith("Seder ")), "")
            return (SEDER_ORDER.get(seder, 99), str(record.get("title", "")))

        return sorted(records, key=sort_key)

    def import_tradition(self, tradition: str, replace: bool = True, max_tractates: int | None = None) -> dict[str, Any]:
        if tradition not in TRADITIONS:
            raise ValueError("tradition must be bavli or yerushalmi")
        if replace:
            ids = [row.id for row in self.db.query(TalmudTractate.id).filter(TalmudTractate.tradition == tradition).all()]
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
        source_url = str(record["json_url"])
        response = self.client.get(source_url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return {"status": "skipped", "reason": "unexpected JSON structure"}

        license_name = _allowed_license(payload.get("license"))
        if not license_name:
            return {"status": "skipped", "reason": f"license not approved: {payload.get('license')!r}"}

        text = payload.get("text")
        if not isinstance(text, list) or not text:
            return {"status": "skipped", "reason": "missing text"}

        title_en = str(payload.get("title") or record.get("title") or "").strip()
        title_he = str(payload.get("heTitle") or payload.get("titleVariants", [""])[0] or title_en).strip()
        categories = record.get("categories") or []
        seder_name = next((str(c).replace("Seder ", "", 1) for c in categories if isinstance(c, str) and c.startswith("Seder ")), "")
        tractate = TalmudTractate(
            tradition=tradition,
            seder_name=seder_name,
            slug=_slug(title_en),
            title_he=title_he,
            title_en=title_en,
            tractate_order=order,
            section_count=len(text),
            source_name=SOURCE_NAME,
            source_url=source_url,
            license=license_name,
            license_verified=True,
        )
        self.db.add(tractate)
        self.db.flush()

        segment_count = 0
        for section_no, section_node in enumerate(text, start=1):
            position = 0
            for path, segment_text in _flatten_strings(section_node):
                position += 1
                ref = _section_ref(title_en, tradition, section_no, path)
                self.db.add(TalmudSegment(
                    tractate_id=tractate.id,
                    section=section_no,
                    position=position,
                    path=".".join(str(x) for x in path),
                    text=segment_text,
                    normalized_text=normalize_hebrew(segment_text),
                    sefaria_ref=ref,
                ))
                segment_count += 1
        self.db.flush()
        return {
            "status": "imported",
            "title": title_he,
            "sections": len(text),
            "segments": segment_count,
            "license": license_name,
        }
