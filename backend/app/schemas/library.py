from pydantic import BaseModel, ConfigDict


class WorkOut(BaseModel):
    id: int
    slug: str
    title_he: str
    title_en: str | None
    category: str
    subcategory: str | None
    author: str | None
    model_config = ConfigDict(from_attributes=True)


class SegmentOut(BaseModel):
    id: int
    ref: str
    section_title: str | None
    level1: int | None
    level2: int | None
    level3: int | None
    position: int
    text: str
    model_config = ConfigDict(from_attributes=True)


class SearchHit(BaseModel):
    work_id: int
    work_title: str
    ref: str
    text: str
