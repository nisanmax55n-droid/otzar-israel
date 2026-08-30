from app.core.db import SessionLocal
from app.services.neviim_importer import NeviimImporter


def main() -> None:
    db = SessionLocal()
    try:
        print(NeviimImporter(db).import_all(replace=True), flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
