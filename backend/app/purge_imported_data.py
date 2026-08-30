from sqlalchemy import delete, func, select

from app.core.db import SessionLocal
from app.models import TextSegment, TextVersion, Work


def main() -> None:
    db = SessionLocal()
    try:
        before = {
            "text_segments": db.scalar(select(func.count()).select_from(TextSegment)) or 0,
            "text_versions": db.scalar(select(func.count()).select_from(TextVersion)) or 0,
            "works": db.scalar(select(func.count()).select_from(Work)) or 0,
        }

        db.execute(delete(TextSegment))
        db.execute(delete(TextVersion))
        db.execute(delete(Work))
        db.commit()

        after = {
            "text_segments": db.scalar(select(func.count()).select_from(TextSegment)) or 0,
            "text_versions": db.scalar(select(func.count()).select_from(TextVersion)) or 0,
            "works": db.scalar(select(func.count()).select_from(Work)) or 0,
        }

        print({"event": "purge_imported_data", "before": before, "after": after}, flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
