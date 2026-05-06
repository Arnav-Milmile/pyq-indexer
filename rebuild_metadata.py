from app.database import connect, init_db
from app.sync.ftp_sync import infer_metadata


def main() -> None:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT filename, filepath, ftp_path, file_size FROM papers ORDER BY id"
        ).fetchall()

    updates = []
    for row in rows:
        metadata = infer_metadata(row["ftp_path"], row["file_size"])
        updates.append(
            {
                "ftp_path": row["ftp_path"],
                "course": metadata["course"],
                "branch": metadata["branch"],
                "display_branch": metadata["display_branch"],
                "department": metadata["department"],
                "subject": metadata["subject"],
                "year": metadata["year"],
                "season": metadata["season"],
                "session": metadata["session"],
                "semester": metadata["semester"],
                "exam_category": metadata["exam_category"],
                "exam_type": metadata["exam_type"],
            }
        )

    with connect() as conn:
        conn.executemany(
            """
            UPDATE papers
            SET course = :course,
                branch = :branch,
                display_branch = :display_branch,
                department = :department,
                subject = :subject,
                year = :year,
                season = :season,
                session = :session,
                semester = :semester,
                exam_category = :exam_category,
                exam_type = :exam_type,
                synced_at = CURRENT_TIMESTAMP
            WHERE ftp_path = :ftp_path
            """,
            updates,
        )

    print(f"Rebuilt metadata for {len(rows)} paper(s).")


if __name__ == "__main__":
    main()
