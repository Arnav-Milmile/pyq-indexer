from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from app import database
from app.config import get_settings
from app.models import Paper
from app.sync.ftp_sync import fetch_ftp_file


router = APIRouter(prefix="/api", tags=["papers"])


@router.get("/papers", response_model=list[Paper])
def papers(
    course: list[str] | None = Query(default=None),
    branch: list[str] | None = Query(default=None),
    department: str | None = None,
    subject: str | None = None,
    year: list[str] | None = Query(default=None),
    exam_category: list[str] | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return database.list_papers(
        course=course,
        branch=branch,
        department=department,
        subject=subject,
        year=year,
        exam_category=exam_category,
        limit=limit,
        offset=offset,
    )


@router.get("/papers/count", response_model=dict[str, int])
def papers_count(
    course: list[str] | None = Query(default=None),
    branch: list[str] | None = Query(default=None),
    department: str | None = None,
    subject: str | None = None,
    year: list[str] | None = Query(default=None),
    exam_category: list[str] | None = Query(default=None),
) -> dict[str, int]:
    return {
        "total": database.count_papers(
            course=course,
            branch=branch,
            department=department,
            subject=subject,
            year=year,
            exam_category=exam_category,
        )
    }


@router.get("/papers/search", response_model=list[Paper])
def search_papers(
    q: str = Query(..., min_length=1),
    course: list[str] | None = Query(default=None),
    branch: list[str] | None = Query(default=None),
    year: list[str] | None = Query(default=None),
    exam_category: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return database.search_papers(
        q,
        course=course,
        branch=branch,
        year=year,
        exam_category=exam_category,
        limit=limit,
        offset=offset,
    )


@router.get("/papers/search/count", response_model=dict[str, int])
def search_papers_count(
    q: str = Query(..., min_length=1),
    course: list[str] | None = Query(default=None),
    branch: list[str] | None = Query(default=None),
    year: list[str] | None = Query(default=None),
    exam_category: list[str] | None = Query(default=None),
) -> dict[str, int]:
    return {
        "total": database.count_search_papers(
            q,
            course=course,
            branch=branch,
            year=year,
            exam_category=exam_category,
        )
    }


@router.get("/papers/{paper_id}", response_model=Paper)
def paper_detail(paper_id: int) -> dict:
    paper = database.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


def _pdf_response(paper: dict, disposition: str):
    filename = paper["filename"].replace('"', "")

    if paper.get("filepath"):
        local_path = Path(paper["filepath"])
        if not local_path.is_absolute():
            local_path = get_settings().papers_dir / local_path
        if local_path.exists():
            return FileResponse(
                local_path,
                media_type="application/pdf",
                headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
            )

    try:
        content = fetch_ftp_file(paper["ftp_path"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to fetch file from FTP") from exc

    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.get("/papers/{paper_id}/preview")
def preview_paper(paper_id: int):
    paper = database.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return _pdf_response(paper, "inline")


@router.get("/papers/{paper_id}/download")
def download_paper(paper_id: int):
    paper = database.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return _pdf_response(paper, "attachment")


@router.get("/departments", response_model=list[str])
def departments() -> list[str]:
    return database.distinct_values("department")


@router.get("/courses", response_model=list[str])
def courses() -> list[str]:
    return database.distinct_values("course")


@router.get("/branches", response_model=list[str])
def branches(course: list[str] | None = Query(default=None)) -> list[str]:
    return database.distinct_values("branch", {"course": course})


@router.get("/branch-options", response_model=list[dict[str, str]])
def branch_options(course: list[str] | None = Query(default=None)) -> list[dict[str, str]]:
    return database.branch_options(course)


@router.get("/exam-categories", response_model=list[str])
def exam_categories(
    course: list[str] | None = Query(default=None),
    branch: list[str] | None = Query(default=None),
) -> list[str]:
    return database.distinct_values("exam_category", {"course": course, "branch": branch})


@router.get("/sessions", response_model=list[str])
def sessions(
    course: str | None = None,
    branch: str | None = None,
    exam_category: str | None = None,
) -> list[str]:
    return database.distinct_values(
        "session",
        {"course": course, "branch": branch, "exam_category": exam_category},
    )


@router.get("/semesters", response_model=list[str])
def semesters(
    course: str | None = None,
    branch: str | None = None,
    exam_category: str | None = None,
    session: str | None = None,
) -> list[str]:
    return database.distinct_values(
        "semester",
        {
            "course": course,
            "branch": branch,
            "exam_category": exam_category,
            "session": session,
        },
    )


@router.get("/subjects", response_model=list[str])
def subjects(branch: str | None = None, semester: str | None = None) -> list[str]:
    return database.distinct_values("subject", {"branch": branch, "semester": semester})


@router.get("/years", response_model=list[str])
def years(
    course: list[str] | None = Query(default=None),
    branch: list[str] | None = Query(default=None),
    exam_category: list[str] | None = Query(default=None),
    semester: str | None = None,
) -> list[str]:
    return database.distinct_values(
        "year",
        {
            "course": course,
            "branch": branch,
            "exam_category": exam_category,
            "semester": semester,
        },
    )
