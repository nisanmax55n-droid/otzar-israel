from __future__ import annotations

import json
import re
from typing import Any, Iterable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import TextSegment, TextVersion, Work
from app.services.text_utils import normalize_hebrew

ALLOWED_LICENSE_PREFIXES = ("Public Domain", "CC0", "CC-BY", "CC BY")
SEFARIA_EXPORT_LICENSE = "Sefaria Export - copyright-filtered free/public text corpus"


def is_importable_license(license_name: str | None) -> bool:
    if not license_name:
        return False
    normalized = license_name.strip().upper().replace("_", "-")
    return normalized.startswith(tuple(x.upper() for x in ALLOWED_LICENSE_PREFIXES)) and "NC" not in normalized


def is_official_merged_export(record: dict) -> bool:
    url = str(record.get("json_url") or "")
    return record.get("versionTitle") == "merged" and url.startswith("https://storage.googleapis.com/sefaria-export/")


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
    elif isinstance(node, dict):
        for child in node.values():
            yield from _flatten_text(child, path)


class SefariaImporter:
    def __init__(self, db: Session):
        self.db = db

    def fetch_index(self) -> dict:
        with httpx.Client(timeout=90, follow_redirects=True) as client:
            r = client.get(settings.sefaria_books_index_url)
            r.raise_for_status()
            return r.json()

    def iter_records(self, *, categories: Iterable[str] | None = None, language: str = "Hebrew", merged_only: bool = True):
        data = self.fetch_index()
        wanted = {c.strip() for c in (categories or []) if c and c.strip()}
        for book in data.get("books", []):
            cats = book.get("categories") or []
            if wanted and not wanted.intersection(cats):
                continue
            if language and (book.get("language") or "") != language:
                continue
            if merged_only and book.get("versionTitle") != "merged":
                continue
            yield book

    def preview(self, category: str | None = None, language: str = "Hebrew", limit: int = 50) -> list[dict]:
        records = self.iter_records(categories=[category] if category else None, language=language)
        results = []
        for book in records:
            item = {k: book.get(k) for k in ("title", "categories", "language", "versionTitle", "license", "json_url")}
            item["source_verified"] = is_official_merged_export(book)
            results.append(item)
            if len(results) >= limit:
                break
        return results

    def record_exists(self, record: dict) -> bool:
        title = record.get("title") or ""
        if not title:
            return False
        work = self.db.scalar(select(Work).where(Work.slug == _slugify(title)))
        if not work:
            return False
        language = record.get("language") or "Hebrew"
        version_title = record.get("versionTitle") or "merged"
        return self.db.scalar(
            select(TextVersion.id).where(
                TextVersion.work_id == work.id,
                TextVersion.language == language,
                TextVersion.version_title == version_title,
            )
        ) is not None

    def import_book_record(self, record: dict, allow_noncommercial: bool = False) -> dict:
        explicit_license = record.get("license")
        official_merged = is_official_merged_export(record)
        permitted = is_importable_license(explicit_license) or official_merged
        license_name = explicit_license or (SEFARIA_EXPORT_LICENSE if official_merged else None)
        if not permitted and not allow_noncommercial:
            return {"status": "skipped", "reason": "license_not_approved", "title": record.get("title"), "license": license_name}

        if self.record_exists(record):
            return {"status": "exists", "title": record.get("title"), "version": record.get("versionTitle")}

        url = record.get("json_url")
        if not url:
            return {"status": "skipped", "reason": "missing_json_url", "title": record.get("title")}

        with httpx.Client(timeout=180, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            payload = r.json()

        title = record.get("title") or payload.get("title") or "ללא שם"
        cats = record.get("categories") or payload.get("categories") or ["Other"]
        slug = _slugify(title)
        work = self.db.scalar(select(Work).where(Work.slug == slug))
        if not work:
            work = Work(
                slug=slug,
                title_he=payload.get("heTitle") or title,
                title_en=title,
                category=cats[0],
                subcategory=cats[1] if len(cats) > 1 else None,
                structure_json=json.dumps(payload.get("schema") or {}, ensure_ascii=False),
            )
            self.db.add(work)
            self.db.flush()

        version_title = record.get("versionTitle") or payload.get("versionTitle") or "Sefaria export"
        language = record.get("language") or payload.get("language") or "Hebrew"
        version = TextVersion(
            work_id=work.id,
            language=language,
            version_title=version_title,
            license=license_name,
            license_verified=permitted,
            source_url=url,
            source_name="Sefaria Export",
        )
        self.db.add(version)
        self.db.flush()

        text_node = payload.get("text") or payload.get("chapter") or []
        count = 0
        batch = []
        for path, text in _flatten_text(text_node):
            if not text or not text.strip():
                continue
            suffix = ":".join(str(x) for x in path)
            ref = f"{title} {suffix}" if suffix else title
            batch.append(TextSegment(
                version_id=version.id,
                ref=ref,
                section_title=str(path[0]) if path else None,
                level1=path[0] if len(path) > 0 else None,
                level2=path[1] if len(path) > 1 else None,
                level3=path[2] if len(path) > 2 else None,
                position=count,
                text=text,
                normalized_text=normalize_hebrew(text),
            ))
            count += 1
            if len(batch) >= 1000:
                self.db.add_all(batch)
                self.db.flush()
                batch.clear()
        if batch:
            self.db.add_all(batch)

        self.db.commit()
        return {"status": "imported", "title": title, "segments": count, "license": license_name}

    def bulk_import(self, *, categories: Iterable[str] | None = None, language: str = "Hebrew", max_books: int = 500) -> dict:
        summary = {"examined": 0, "imported": 0, "exists": 0, "skipped": 0, "failed": 0, "segments": 0, "errors": []}
        attempted_new = 0
        for record in self.iter_records(categories=categories, language=language, merged_only=True):
            summary["examined"] += 1
            if self.record_exists(record):
                summary["exists"] += 1
                continue
            if attempted_new >= max_books:
                break
            attempted_new += 1
            try:
                result = self.import_book_record(record)
                status = result.get("status")
                if status == "imported":
                    summary["imported"] += 1
                    summary["segments"] += int(result.get("segments") or 0)
                elif status == "exists":
                    summary["exists"] += 1
                else:
                    summary["skipped"] += 1
            except Exception as exc:
                self.db.rollback()
                summary["failed"] += 1
                if len(summary["errors"]) < 50:
                    summary["errors"].append({"title": record.get("title"), "error": str(exc)[:300]})
        return summary
