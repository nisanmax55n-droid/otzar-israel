from __future__ import annotations

import json
import os

from app.core.db import SessionLocal
from app.services.sefaria_importer import SefariaImporter

# Priority order: foundational corpus first, then major rabbinic / halakhic / liturgical corpora.
DEFAULT_CATEGORIES = [
    "Tanakh",
    "Mishnah",
    "Talmud",
    "Midrash",
    "Halakhah",
    "Tosefta",
    "Liturgy",
    "Jewish Thought",
    "Chasidut",
    "Kabbalah",
    "Musar",
]


def main() -> None:
    raw_categories = os.getenv("OTZAR_IMPORT_CATEGORIES", "")
    categories = [x.strip() for x in raw_categories.split(",") if x.strip()] or DEFAULT_CATEGORIES
    max_books = int(os.getenv("OTZAR_IMPORT_MAX_BOOKS", "500"))

    db = SessionLocal()
    try:
        print(json.dumps({"event": "import_started", "categories": categories, "max_books": max_books}, ensure_ascii=False))
        result = SefariaImporter(db).bulk_import(
            categories=categories,
            language="Hebrew",
            max_books=max_books,
        )
        print(json.dumps({"event": "import_finished", **result}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
