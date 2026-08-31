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


def _he_title(payload: dict[str, Any], fallback: str) -> str:
    direct = payload.get("heTitle")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    variants = payload.get("heTitleVariants") or payload.get("titleVariants") or []
    if isinstance(variants, list):
        for value in variants:
            if isinstance(value, str) and value.strip() and any("א" <= ch <= "ת" for ch in value):
                return value.strip()
    return fallback


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
        grouped: dict[str, dict[str, Any]] = {}

        for record in books:
            if not isinstance(record, dict):
                continue
            categories = record.get("categories") or []
            language = str(record.get("language", "")).lower()
            title = str(record.get("title", "")).strip()
            if language not in {"hebrew", "he"}:
                continue
            if "Talmud" not in categories or sefaria_category not in categories:
                continue
            if not record.get("json_url") or not title:
                continue
            # A merged export can combine differently licensed versions and may have no license field.
            # Otsar Israel therefore imports only a concrete version whose own JSON declares an approved license.
            if str(record.get("versionTitle", "")).strip().lower() == "merged":
                continue
            group = grouped.setdefault(title, {"title": title, "categories": categories, "candidates": []})
            group["candidates"].append(record)

        def sort_key(group: dict[str, Any]) -> tuple[int, str]:
            categories = group.get("categories") or []
            seder = next((c for c in categories if isinstance(c, str) and c.startswith("Seder ")), "")
            return (SEDER_ORDER.get(seder, 99), str(group.get("title", "")))

        records = sorted(grouped.values(), key=sort_key)
        for group in records:
            group["candidates"] = sorted(
                group["candidates"],
                key=lambda r: ("wikisource" not in str(r.get("versionTitle", "")).lower(), str(r.get("versionTitle", ""))),
            )
        return records

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
            chosen_payload = payload
            chosen_record = candidate
            chosen_license = license_name
            break

        if not chosen_payload or not chosen_record or not chosen_license:
            reason = "; ".join(rejection_reasons[:6]) or "no concrete Hebrew versions found"
            return {"status": "skipped", "reason": reason}

        text = chosen_payload["text"]
        title_he = _he_title(chosen_payload, title_en)
        categories = record.get("categories") or []
        seder_name = next((str(c).replace("Seder ", "", 1) for c in categories if isinstance(c, str) and c.startswith("Seder ")), "")
        version_title = str(chosen_record.get("versionTitle", "")).strip() or "unnamed version"
        source_url = str(chosen_record["json_url"])
        tractate = TalmudTractate(
            tradition=tradition,
            seder_name=seder_name,
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
            "version": version_title,
            "sections": len(text),
            "segments": segment_count,
            "license": chosen_license,
        }
