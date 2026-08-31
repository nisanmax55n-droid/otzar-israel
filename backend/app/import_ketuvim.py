from app.core.db import SessionLocal
from app.services.ketuvim_importer import KetuvimImporter


def main() -> None:
    db = SessionLocal()
    try:
        print(KetuvimImporter(db).import_all(replace=True), flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
