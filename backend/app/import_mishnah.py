from app.core.db import SessionLocal
from app.services.mishnah_importer import MishnahImporter


# One-shot Railway worker for approved content import pulses; production smoke checks may reuse this service temporarily.
def main() -> None:
    db = SessionLocal()
    try:
        print(MishnahImporter(db).import_all(replace=True), flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
