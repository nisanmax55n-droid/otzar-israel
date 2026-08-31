import os

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models.talmud import TalmudSegment, TalmudTractate
from app.services.talmud_importer import TalmudImporter, TRADITIONS


def main() -> None:
    tradition = os.getenv("OTZAR_TALMUD_TRADITION", "bavli").strip().lower()
    max_tractates_raw = os.getenv("OTZAR_IMPORT_MAX_TRACTATES", "0").strip()
    max_tractates = int(max_tractates_raw) if max_tractates_raw.isdigit() else 0
    if tradition not in TRADITIONS:
        raise ValueError("OTZAR_TALMUD_TRADITION must be bavli or yerushalmi")

    db = SessionLocal()
    importer = TalmudImporter(db)
    imported = 0
    skipped = 0
    failed = 0
    try:
        records = importer._records(tradition)
        if max_tractates > 0:
            records = records[:max_tractates]

        old_ids = list(db.scalars(select(TalmudTractate.id).where(TalmudTractate.tradition == tradition)).all())
        if old_ids:
            db.execute(delete(TalmudSegment).where(TalmudSegment.tractate_id.in_(old_ids)))
        db.execute(delete(TalmudTractate).where(TalmudTractate.tradition == tradition))
        db.commit()
        print({"event": "reset", "tradition": tradition, "tractates_found": len(records)}, flush=True)

        for order, record in enumerate(records, start=1):
            title = str(record.get("title", ""))
            try:
                result = importer.import_tractate(tradition, order, record)
                if result.get("status") == "imported":
                    db.commit()
                    imported += 1
                else:
                    db.rollback()
                    skipped += 1
                print({"event": "tractate", "index": order, "total": len(records), "title": title, "result": result}, flush=True)
            except Exception as exc:
                db.rollback()
                failed += 1
                print({"event": "tractate_error", "index": order, "total": len(records), "title": title, "error": f"{type(exc).__name__}: {exc}"}, flush=True)

        print({"status": "ok", "tradition": tradition, "found": len(records), "imported": imported, "skipped": skipped, "failed": failed}, flush=True)
    finally:
        importer.close()
        db.close()


if __name__ == "__main__":
    main()
