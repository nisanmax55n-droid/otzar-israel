from __future__ import annotations
import json
import re
from typing import Any
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import Work, TextVersion, TextSegment
from app.services.text_utils import normalize_hebrew

ALLOWED_LICENSE_PREFIXES = ("Public Domain", "CC0", "CC-BY", "CC BY")


def is_importable_license(license_name: str | None) -> bool:
    if not license_name:
        return False
    normalized = license_name.strip().upper().replace("_", "-")
    return normalized.startswith(tuple(x.upper() for x in ALLOWED_LICENSE_PREFIXES)) and "NC" not in normalized


def _slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9\u0590-\u05FF]+", "-", value).strip("-")
    return value.lower() or "work"


def _flatten_text(node: Any, path: list[int] | None = None):
    path = path or []
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, list):
        for i, child in enumerate(node, 1):
            yield from _flatten_text(child, path + [i])


class SefariaImporter:
    def __init__(self, db: Session):
        self.db = db

    def fetch_index(self) -> dict:
        with httpx.Client(timeout=60) as client:
            r = client.get(settings.sefaria_books_index_url)
            r.raise_for_status()
            return r.json()

    def preview(self, category: str | None = None, language: str = "Hebrew", limit: int = 50) -> list[dict]:
        data = self.fetch_index()
        results = []
        for book in data.get("books", []):
            cats = book.get("categories") or []
            if category and category not in cats:
                continue
            if language and (book.get("language") or "") != language:
                continue
            results.append({k: book.get(k) for k in ("title", "categories", "language", "versionTitle", "license", "json_url")})
            if len(results) >= limit:
                break
        return results

    def import_book_record(self, record: dict, allow_noncommercial: bool = False) -> dict:
        license_name = record.get("license")
        permitted = is_importable_license(license_name)
        if not permitted and not allow_noncommercial:
            return {"status": "skipped", "reason": "license_not_approved", "title": record.get("title"), "license": license_name}
        url = record.get("json_url")
        if not url:
            return {"status": "skipped", "reason": "missing_json_url", "title": record.get("title")}
        with httpx.Client(timeout=120) as client:
            r = client.get(url)
            r.raise_for_status()
            payload = r.json()
        title = record.get("title") or payload.get("title") or "ללא שם"
        cats = record.get("categories") or payload.get("categories") or ["Other"]
        slug = _slugify(title)
        work = self.db.scalar(select(Work).where(Work.slug == slug))
        if not work:
            work = Work(slug=slug, title_he=payload.get("heTitle") or title, title_en=title, category=cats[0], subcategory=cats[1] if len(cats)>1 else None, structure_json=json.dumps(payload.get("schema") or {}, ensure_ascii=False))
            self.db.add(work)
            self.db.flush()
        version_title = record.get("versionTitle") or payload.get("versionTitle") or "Sefaria export"
        language = record.get("language") or payload.get("language") or "Hebrew"
        existing = self.db.scalar(select(TextVersion).where(TextVersion.work_id == work.id, TextVersion.language == language, TextVersion.version_title == version_title))
        if existing:
            return {"status": "exists", "title": title, "version": version_title}
        version = TextVersion(work_id=work.id, language=language, version_title=version_title, license=license_name, license_verified=permitted, source_url=url, source_name="Sefaria Export")
        self.db.add(version)
        self.db.flush()
        text_node = payload.get("text") or payload.get("chapter") or []
        count = 0
        for path, text in _flatten_text(text_node):
            if not text or not text.strip():
                continue
            suffix = ":".join(str(x) for x in path)
            ref = f"{title} {suffix}" if suffix else title
            self.db.add(TextSegment(version_id=version.id, ref=ref, section_title=str(path[0]) if path else None, level1=path[0] if len(path)>0 else None, level2=path[1] if len(path)>1 else None, level3=path[2] if len(path)>2 else None, position=count, text=text, normalized_text=normalize_hebrew(text)))
            count += 1
        self.db.commit()
        return {"status": "imported", "title": title, "segments": count, "license": license_name}
