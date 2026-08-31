import os

from app.core.db import SessionLocal
from app.services.talmud_importer import TalmudImporter


def main() -> None:
    tradition = os.getenv("OTZAR_TALMUD_TRADITION", "bavli").strip().lower()
    max_tractates_raw = os.getenv("OTZAR_IMPORT_MAX_TRACTATES", "0").strip()
    max_tractates = int(max_tractates_raw) if max_tractates_raw.isdigit() else 0
    db = SessionLocal()
    try:
        result = TalmudImporter(db).import_tradition(
            tradition=tradition,
            replace=True,
            max_tractates=max_tractates or None,
        )
        print(result, flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
