from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from app.api.routes import router
from app.api.mishnah_routes import router as mishnah_router
from app.api.talmud_routes import router as talmud_router
from app.core.config import settings
from app.core.db import Base, SessionLocal, engine
from app.models.talmud import TalmudTractate
from app import models  # noqa: F401

Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.include_router(mishnah_router)
app.include_router(talmud_router)

@app.get("/health")
def health():
    db = SessionLocal()
    try:
        rows = db.execute(select(TalmudTractate.tradition, func.count(TalmudTractate.id)).group_by(TalmudTractate.tradition)).all()
        counts = {tradition: count for tradition, count in rows}
        first = db.scalar(select(TalmudTractate).where(TalmudTractate.tradition == "bavli").order_by(TalmudTractate.id).limit(1))
        print({"TALMUD_VERIFY": counts, "first_bavli": None if not first else {"title_he": first.title_he, "section_count": first.section_count, "license": first.license, "license_verified": first.license_verified}}, flush=True)
    finally:
        db.close()
    return {"status": "ok"}

@app.get("/")
def root():
    return {"name": settings.app_name, "version": "0.1.0", "docs": "/docs"}
