import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.config import get_settings


FilterValue = str | list[str] | None


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS papers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL,
    filepath    TEXT,
    ftp_path    TEXT NOT NULL UNIQUE,
    course      TEXT,
    branch      TEXT,
    display_branch TEXT,
    department  TEXT,
    subject     TEXT,
    year        TEXT,
    season      TEXT,
    session     TEXT,
    semester    TEXT,
    exam_category TEXT,
    exam_type   TEXT,
    file_size   INTEGER,
    synced_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_course ON papers(course);
CREATE INDEX IF NOT EXISTS idx_branch ON papers(branch);
CREATE INDEX IF NOT EXISTS idx_display_branch ON papers(display_branch);
CREATE INDEX IF NOT EXISTS idx_department ON papers(department);
CREATE INDEX IF NOT EXISTS idx_subject ON papers(subject);
CREATE INDEX IF NOT EXISTS idx_year ON papers(year);
CREATE INDEX IF NOT EXISTS idx_session ON papers(session);
CREATE INDEX IF NOT EXISTS idx_semester ON papers(semester);
CREATE INDEX IF NOT EXISTS idx_filename ON papers(filename);
"""

SCHEMA = CREATE_TABLE + INDEXES

METADATA_COLUMNS = {
    "course": "TEXT",
    "branch": "TEXT",
    "display_branch": "TEXT",
    "season": "TEXT",
    "session": "TEXT",
    "semester": "TEXT",
    "exam_category": "TEXT",
}


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(zip(row.keys(), row, strict=True))


def get_db_path() -> Path:
    return get_settings().database_path


@contextmanager
def connect() -> Iterable[sqlite3.Connection]:
    conn = sqlite3.connect(get_db_path(), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(CREATE_TABLE)
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(papers)").fetchall()
        }
        for column, column_type in METADATA_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE papers ADD COLUMN {column} {column_type}")
        conn.executescript(INDEXES)


def upsert_paper(paper: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO papers (
                filename, filepath, ftp_path, course, branch, display_branch, department, subject,
                year, season, session, semester, exam_category, exam_type, file_size
            )
            VALUES (
                :filename, :filepath, :ftp_path, :course, :branch, :display_branch, :department, :subject,
                :year, :season, :session, :semester, :exam_category, :exam_type, :file_size
            )
            ON CONFLICT(ftp_path) DO UPDATE SET
                filename=excluded.filename,
                filepath=excluded.filepath,
                course=excluded.course,
                branch=excluded.branch,
                display_branch=excluded.display_branch,
                department=excluded.department,
                subject=excluded.subject,
                year=excluded.year,
                season=excluded.season,
                session=excluded.session,
                semester=excluded.semester,
                exam_category=excluded.exam_category,
                exam_type=excluded.exam_type,
                file_size=excluded.file_size,
                synced_at=CURRENT_TIMESTAMP
            """,
            paper,
        )


def bulk_upsert_papers(papers: list[dict[str, Any]]) -> int:
    if not papers:
        return 0

    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO papers (
                filename, filepath, ftp_path, course, branch, display_branch, department, subject,
                year, season, session, semester, exam_category, exam_type, file_size
            )
            VALUES (
                :filename, :filepath, :ftp_path, :course, :branch, :display_branch, :department, :subject,
                :year, :season, :session, :semester, :exam_category, :exam_type, :file_size
            )
            ON CONFLICT(ftp_path) DO UPDATE SET
                filename=excluded.filename,
                filepath=excluded.filepath,
                course=excluded.course,
                branch=excluded.branch,
                display_branch=excluded.display_branch,
                department=excluded.department,
                subject=excluded.subject,
                year=excluded.year,
                season=excluded.season,
                session=excluded.session,
                semester=excluded.semester,
                exam_category=excluded.exam_category,
                exam_type=excluded.exam_type,
                file_size=excluded.file_size,
                synced_at=CURRENT_TIMESTAMP
            """,
            papers,
        )
    return len(papers)


def list_papers(
    course: FilterValue = None,
    branch: FilterValue = None,
    department: str | None = None,
    subject: str | None = None,
    year: FilterValue = None,
    exam_category: FilterValue = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    where, params = paper_filter_clause(
        course=course,
        branch=branch,
        department=department,
        subject=subject,
        year=year,
        exam_category=exam_category,
    )
    params.update({"limit": limit, "offset": offset})

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM papers
            {where}
            ORDER BY course, branch, exam_category, year DESC, session, semester, filename
            LIMIT :limit OFFSET :offset
            """,
            params,
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def paper_filter_clause(
    course: FilterValue = None,
    branch: FilterValue = None,
    department: str | None = None,
    subject: str | None = None,
    year: FilterValue = None,
    exam_category: FilterValue = None,
) -> tuple[str, dict[str, Any]]:
    filters: list[str] = []
    params: dict[str, Any] = {}

    add_filter(filters, params, "course", course)
    add_filter(filters, params, "branch", branch)
    if department:
        filters.append("department = :department")
        params["department"] = department
    if subject:
        filters.append("subject = :subject")
        params["subject"] = subject
    add_filter(filters, params, "year", year)
    add_filter(filters, params, "exam_category", exam_category)

    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    return where, params


def normalized_values(value: FilterValue) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    return [item for item in value if item]


def add_filter(filters: list[str], params: dict[str, Any], column: str, value: FilterValue) -> None:
    values = normalized_values(value)
    if not values:
        return
    if len(values) == 1:
        filters.append(f"{column} = :{column}")
        params[column] = values[0]
        return
    placeholders = []
    for index, item in enumerate(values):
        key = f"{column}_{index}"
        placeholders.append(f":{key}")
        params[key] = item
    filters.append(f"{column} IN ({', '.join(placeholders)})")


def count_papers(
    course: FilterValue = None,
    branch: FilterValue = None,
    department: str | None = None,
    subject: str | None = None,
    year: FilterValue = None,
    exam_category: FilterValue = None,
) -> int:
    where, params = paper_filter_clause(
        course=course,
        branch=branch,
        department=department,
        subject=subject,
        year=year,
        exam_category=exam_category,
    )
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS total FROM papers
            {where}
            """,
            params,
        ).fetchone()
    return int(row["total"])


def search_clause(query: str) -> tuple[str, dict[str, Any]]:
    term = query.strip()
    like = f"%{term}%"
    prefix = f"{term}%"
    return (
        """
        (
            filename LIKE :query
            OR ftp_path LIKE :query
            OR course LIKE :query
            OR branch LIKE :query
            OR display_branch LIKE :query
            OR department LIKE :query
            OR subject LIKE :query
            OR year LIKE :query
            OR season LIKE :query
            OR session LIKE :query
            OR semester LIKE :query
            OR exam_category LIKE :query
            OR exam_type LIKE :query
        )
        """,
        {
            "term": term,
            "filename": f"{term}.pdf",
            "query": like,
            "prefix": prefix,
        },
    )


def search_papers(
    query: str,
    course: FilterValue = None,
    branch: FilterValue = None,
    year: FilterValue = None,
    exam_category: FilterValue = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    filter_where, filter_params = paper_filter_clause(
        course=course,
        branch=branch,
        year=year,
        exam_category=exam_category,
    )
    search_where, search_params = search_clause(query)
    clauses = [search_where]
    if filter_where:
        clauses.append(filter_where.removeprefix("WHERE "))
    where = f"WHERE {' AND '.join(clauses)}"
    params = {**filter_params, **search_params, "limit": limit, "offset": offset}

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM papers
            {where}
            ORDER BY
                CASE
                    WHEN subject = :term COLLATE NOCASE THEN 0
                    WHEN filename = :filename COLLATE NOCASE THEN 0
                    WHEN subject LIKE :prefix THEN 1
                    WHEN filename LIKE :prefix THEN 1
                    WHEN subject LIKE :query THEN 2
                    WHEN filename LIKE :query THEN 2
                    WHEN semester LIKE :query THEN 3
                    WHEN session LIKE :query THEN 4
                    WHEN display_branch LIKE :query THEN 5
                    WHEN branch LIKE :query THEN 5
                    WHEN ftp_path LIKE :query THEN 6
                    ELSE 7
                END,
                year DESC,
                course,
                branch,
                semester,
                filename
            LIMIT :limit OFFSET :offset
            """,
            params,
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def count_search_papers(
    query: str,
    course: FilterValue = None,
    branch: FilterValue = None,
    year: FilterValue = None,
    exam_category: FilterValue = None,
) -> int:
    filter_where, filter_params = paper_filter_clause(
        course=course,
        branch=branch,
        year=year,
        exam_category=exam_category,
    )
    search_where, search_params = search_clause(query)
    clauses = [search_where]
    if filter_where:
        clauses.append(filter_where.removeprefix("WHERE "))
    where = f"WHERE {' AND '.join(clauses)}"
    params = {**filter_params, **search_params}

    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS total FROM papers
            {where}
            """,
            params,
        ).fetchone()
    return int(row["total"])


def get_paper(paper_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    return row_to_dict(row) if row else None


def distinct_values(column: str, filters: dict[str, FilterValue] | None = None) -> list[str]:
    allowed = {
        "course",
        "branch",
        "display_branch",
        "department",
        "subject",
        "year",
        "season",
        "session",
        "semester",
        "exam_category",
        "exam_type",
    }
    if column not in allowed:
        raise ValueError(f"Unsupported column: {column}")

    filters = filters or {}
    clauses = [f"{column} IS NOT NULL", f"{column} != ''"]
    params: dict[str, Any] = {}
    for key, value in filters.items():
        if key in allowed:
            add_filter(clauses, params, key, value)

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT DISTINCT {column} AS value
            FROM papers
            WHERE {' AND '.join(clauses)}
            ORDER BY value
            """,
            params,
        ).fetchall()
    return [row["value"] for row in rows]


def branch_options(course: FilterValue = None) -> list[dict[str, str]]:
    where, params = paper_filter_clause(course=course)
    prefix = "WHERE" if not where else f"{where} AND"
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT branch AS value, COALESCE(display_branch, branch) AS label
            FROM papers
            {prefix} branch IS NOT NULL AND branch != ''
            GROUP BY branch, display_branch
            ORDER BY label
            """,
            params,
        ).fetchall()
    return [row_to_dict(row) for row in rows]
