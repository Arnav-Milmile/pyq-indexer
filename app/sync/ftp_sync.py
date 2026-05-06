from __future__ import annotations

import re
from dataclasses import dataclass
from ftplib import FTP, error_perm
from pathlib import PurePosixPath

from app.config import Settings, get_settings
from app.database import bulk_upsert_papers, init_db


PDF_SUFFIX = ".pdf"
YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2}|\d{2})\b")
SESSION_RE = re.compile(r"\b(SUMMER|WINTER)\s*[- ]*\s*(20\d{2}|19\d{2}|\d{2})\b", re.IGNORECASE)
SEMESTER_RE = re.compile(
    r"\b(1st|2nd|3rd|4th|5th|6th|7th|8th|first|second|third|thrid|thirth|fourth|fifth|sixth|seven|seventh|eight|eigth|eighth|iit?ht)\s+sem",
    re.IGNORECASE,
)
SEMESTER_LABELS = {
    "1st": "1st Semester",
    "first": "1st Semester",
    "2nd": "2nd Semester",
    "second": "2nd Semester",
    "3rd": "3rd Semester",
    "third": "3rd Semester",
    "thrid": "3rd Semester",
    "thirth": "3rd Semester",
    "4th": "4th Semester",
    "fourth": "4th Semester",
    "5th": "5th Semester",
    "fifth": "5th Semester",
    "6th": "6th Semester",
    "sixth": "6th Semester",
    "7th": "7th Semester",
    "seven": "7th Semester",
    "seventh": "7th Semester",
    "8th": "8th Semester",
    "eight": "8th Semester",
    "eigth": "8th Semester",
    "eighth": "8th Semester",
    "iit": "8th Semester",
    "iith": "8th Semester",
}
EXAM_PATTERNS = {
    "regular": "Regular",
    "make-up": "Make-Up",
    "make up": "Make-Up",
    "makeup": "Make-Up",
}

BRANCH_REPLACEMENTS = (
    (re.compile(r"\bARTIFICIAL\s+INTELLGENCE\b"), "ARTIFICIAL INTELLIGENCE"),
    (re.compile(r"\bEIECTRONICS\b"), "ELECTRONICS"),
    (re.compile(r"\bENGG\.?\b"), "ENGINEERING"),
    (re.compile(r"\bTECH\.?\b"), "TECHNOLOGY"),
)


@dataclass(frozen=True)
class FtpEntry:
    path: str
    is_dir: bool
    size: int | None = None


class FtpListError(RuntimeError):
    def __init__(self, path: str, original: Exception):
        super().__init__(f"Could not list FTP folder {path!r}: {original}")
        self.path = path
        self.original = original


def connect_ftp(settings: Settings | None = None, passive: bool | None = None) -> FTP:
    settings = settings or get_settings()
    ftp = FTP(encoding=settings.ftp_encoding)
    ftp.connect(settings.ftp_host, settings.ftp_port, timeout=settings.ftp_timeout)
    ftp.login(settings.ftp_user, settings.ftp_password)
    ftp.set_pasv(settings.ftp_passive if passive is None else passive)
    return ftp


def clean_label(value: str) -> str:
    label = re.sub(r"[_\-]+", " ", value)
    label = re.sub(r"\.pdf$", "", label, flags=re.IGNORECASE)
    label = re.sub(r"\s+", " ", label).strip()
    return label or value


def title_label(value: str | None) -> str | None:
    if not value:
        return None
    words = []
    for word in clean_label(value).split(" "):
        if word in {"BBA", "BCA", "MCA", "MBA"}:
            words.append(word)
        elif word in {"AND", "OF", "IN", "FOR", "II", "III", "IV"}:
            words.append(word.lower())
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)


def normalize_branch_name(branch: str | None) -> str | None:
    if not branch:
        return None

    value = clean_label(branch).upper()
    value = re.sub(r"\bII\s*,?\s*III\s*&\s*IV\s*YEAR\b", "", value)
    value = re.sub(r"\bI{1,3}\s*&\s*IV\s*YEAR\b", "", value)
    value = re.sub(r"\bYEAR\b", "", value)
    for pattern, replacement in BRANCH_REPLACEMENTS:
        value = pattern.sub(replacement, value)
    value = re.sub(r"\s+", " ", value).strip(" .,-")
    return title_label(value)


def normalize_year(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) == 2:
        return f"20{value}" if int(value) < 70 else f"19{value}"
    return value


def normalize_session(value: str) -> tuple[str | None, str | None, str | None]:
    match = SESSION_RE.search(value)
    if not match:
        return None, None, None
    season = match.group(1).title()
    year = normalize_year(match.group(2))
    return season, year, f"{season} {year}"


def normalize_semester(value: str) -> str | None:
    match = SEMESTER_RE.search(value)
    if not match:
        return None
    key = match.group(1).lower()
    return SEMESTER_LABELS.get(key)


def infer_category(parts: list[str]) -> str | None:
    searchable = " ".join(parts).lower()
    for pattern, label in EXAM_PATTERNS.items():
        if pattern in searchable:
            return label
    return None


def infer_metadata(ftp_path: str, size: int | None = None) -> dict[str, str | int | None]:
    path = PurePosixPath(ftp_path)
    filename = path.name
    parts = [clean_label(part) for part in path.parts if part not in ("", "/")]
    folders = parts[:-1]

    course = folders[0] if len(folders) >= 1 else None
    branch = folders[1] if len(folders) >= 2 else None
    category = infer_category(folders)

    year = None
    season = None
    session = None
    for part in folders:
        found_season, found_year, found_session = normalize_session(part)
        if found_session:
            season = found_season
            year = found_year
            session = found_session
            break

    if not year:
        for part in reversed(parts):
            match = YEAR_RE.search(part)
            if match:
                year = normalize_year(match.group(1))
                break

    semester = None
    for part in reversed(folders):
        semester = normalize_semester(part)
        if semester:
            break

    subject = clean_label(filename)

    legacy_exam_type = category
    if not legacy_exam_type:
        for part in parts:
            found_semester = normalize_semester(part)
            if found_semester:
                legacy_exam_type = "Semester"
                break

    if not branch and folders:
        branch = folders[-1]

    return {
        "filename": filename,
        "filepath": None,
        "ftp_path": ftp_path,
        "course": course,
        "branch": branch,
        "display_branch": normalize_branch_name(branch),
        "department": branch,
        "subject": subject,
        "year": year,
        "season": season,
        "session": session,
        "semester": semester,
        "exam_category": category,
        "exam_type": legacy_exam_type,
        "file_size": size,
    }


def _entry_from_mlsd(parent: str, name: str, facts: dict[str, str]) -> FtpEntry:
    ftp_path = str(PurePosixPath(parent) / name)
    return FtpEntry(
        path=ftp_path,
        is_dir=facts.get("type") == "dir",
        size=int(facts["size"]) if facts.get("size", "").isdigit() else None,
    )


def list_entries(ftp: FTP, path: str, use_mlsd: bool = False) -> list[FtpEntry]:
    if use_mlsd:
        try:
            entries = []
            for name, facts in ftp.mlsd(path):
                if name in {".", ".."}:
                    continue
                entries.append(_entry_from_mlsd(path, name, facts))
            return entries
        except (error_perm, AttributeError, UnicodeDecodeError):
            pass

    return _list_entries_fallback(ftp, path)


def list_entries_resilient(settings: Settings, path: str) -> list[FtpEntry]:
    modes = [settings.ftp_passive]
    alternate = not settings.ftp_passive
    if settings.ftp_try_alternate_mode and alternate not in modes:
        modes.append(alternate)

    last_error: Exception | None = None
    for _attempt in range(max(settings.ftp_retries, 1)):
        for passive in modes:
            try:
                with connect_ftp(settings, passive=passive) as ftp:
                    return list_entries(ftp, path, settings.ftp_use_mlsd)
            except (OSError, error_perm, UnicodeDecodeError) as exc:
                last_error = exc

    raise FtpListError(path, last_error or RuntimeError("unknown FTP listing error"))


def _list_entries_fallback(ftp: FTP, path: str) -> list[FtpEntry]:
    original = ftp.pwd()
    entries: list[FtpEntry] = []
    try:
        ftp.cwd(path)
        names = ftp.nlst()
        for raw_name in names:
            name = PurePosixPath(raw_name).name
            if name in {".", ".."}:
                continue
            child_path = str(PurePosixPath(path) / name)
            is_dir = False
            size = None
            try:
                ftp.cwd(child_path)
                is_dir = True
                ftp.cwd(path)
            except error_perm:
                try:
                    size = ftp.size(child_path)
                except error_perm:
                    size = None
            entries.append(FtpEntry(child_path, is_dir, size))
    finally:
        ftp.cwd(original)
    return entries


def walk_pdfs(settings: Settings, root: str = "/", verbose: bool = False) -> list[FtpEntry]:
    stack = [root]
    pdfs: list[FtpEntry] = []

    while stack:
        current = stack.pop()
        if verbose:
            print(f"Scanning {current}", flush=True)
        for entry in list_entries_resilient(settings, current):
            if entry.is_dir:
                stack.append(entry.path)
            elif entry.path.lower().endswith(PDF_SUFFIX):
                pdfs.append(entry)

    return sorted(pdfs, key=lambda item: item.path.lower())


def sync_ftp_index(settings: Settings | None = None, verbose: bool = False) -> int:
    settings = settings or get_settings()
    init_db()
    papers = [
        infer_metadata(entry.path, entry.size)
        for entry in walk_pdfs(settings, settings.ftp_root, verbose)
    ]
    return bulk_upsert_papers(papers)


def fetch_ftp_file(ftp_path: str, settings: Settings | None = None) -> bytes:
    settings = settings or get_settings()
    chunks: list[bytes] = []
    with connect_ftp(settings) as ftp:
        ftp.retrbinary(f"RETR {ftp_path}", chunks.append)
    return b"".join(chunks)
