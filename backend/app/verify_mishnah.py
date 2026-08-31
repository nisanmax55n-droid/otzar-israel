from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models.mishnah import MishnahSeder, MishnahTractate, MishnahUnit


def main() -> None:
    db = SessionLocal()
    try:
        sedarim = db.scalar(select(func.count(MishnahSeder.id))) or 0
        tractates = db.scalar(select(func.count(MishnahTractate.id))) or 0
        units = db.scalar(select(func.count(MishnahUnit.id))) or 0
        by_seder = db.execute(
            select(MishnahSeder.title_he, func.count(MishnahTractate.id))
            .outerjoin(MishnahTractate, MishnahTractate.seder_id == MishnahSeder.id)
            .group_by(MishnahSeder.id, MishnahSeder.title_he, MishnahSeder.seder_order)
            .order_by(MishnahSeder.seder_order)
        ).all()
        print({
            "sedarim": sedarim,
            "tractates": tractates,
            "mishnayot": units,
            "by_seder": [{"seder": name, "tractates": count} for name, count in by_seder],
        }, flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
