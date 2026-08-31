from app.core.db import SessionLocal
from app.services.mishnah_importer import MishnahImporter


def main() -> None:
    db = SessionLocal()
    try:
        print(MishnahImporter(db).import_all(replace=True), flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
