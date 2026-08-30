from app.core.db import SessionLocal
from app.services.torah_importer import TorahImporter

# One-shot production task: import only the five books of the Torah.
def main() -> None:
    db = SessionLocal()
    try:
        result = TorahImporter(db).import_all(replace=True)
        print(result, flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
