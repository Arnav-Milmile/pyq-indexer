from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Paper(BaseModel):
    id: int
    filename: str
    filepath: str | None = None
    ftp_path: str
    course: str | None = None
    branch: str | None = None
    display_branch: str | None = None
    department: str | None = None
    subject: str | None = None
    year: str | None = None
    season: str | None = None
    session: str | None = None
    semester: str | None = None
    exam_category: str | None = None
    exam_type: str | None = None
    file_size: int | None = None
    synced_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaperFilters(BaseModel):
    course: str | None = None
    branch: str | None = None
    display_branch: str | None = None
    department: str | None = None
    subject: str | None = None
    year: str | None = None
    session: str | None = None
    semester: str | None = None
    exam_category: str | None = None
