from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import mimetypes
import sqlite3

from .config import BASE_DIR, DB_BY_TURBINE


def ensure_comments_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS faq_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_alarm_code_id INTEGER NOT NULL,
            date DATETIME DEFAULT CURRENT_TIMESTAMP,
            comment_text TEXT NOT NULL,
            FOREIGN KEY(entry_alarm_code_id) REFERENCES faq_entries(alarm_code_id) ON DELETE CASCADE
        )
        """
    )


def fetch_entry(turbine_type: str, alarm_code_id: int) -> tuple[dict[str, object] | None, list[dict[str, object]], list[dict[str, object]]]:
    db_path = DB_BY_TURBINE[turbine_type]
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        entry_row = conn.execute(
            """
            SELECT alarm_code_id, source_file, turbine_type, alarm_code, comment,
                   description, vestas_alarm_suggestion, onsite_suggestion,
                   link_to_document_raw, status
            FROM faq_entries
            WHERE alarm_code_id = ?
            """,
            (alarm_code_id,),
        ).fetchone()

        if entry_row is None:
            return None, [], []

        links = conn.execute(
            """
            SELECT id, href, link_text, resolved_path, exists_on_disk
            FROM faq_links
            WHERE entry_alarm_code_id = ?
            ORDER BY id
            """,
            (alarm_code_id,),
        ).fetchall()

        images = conn.execute(
            """
            SELECT id, src, resolved_path, exists_on_disk
            FROM faq_images
            WHERE entry_alarm_code_id = ?
            ORDER BY id
            """,
            (alarm_code_id,),
        ).fetchall()

    return dict(entry_row), [dict(r) for r in links], [dict(r) for r in images]


def fetch_comments(turbine_type: str, alarm_code_id: int) -> list[dict[str, object]]:
    db_path = DB_BY_TURBINE[turbine_type]
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_comments_table(conn)
        rows = conn.execute(
            """
            SELECT id, entry_alarm_code_id, date, comment_text
            FROM faq_comments
            WHERE entry_alarm_code_id = ?
            ORDER BY date DESC, id DESC
            """,
            (alarm_code_id,),
        ).fetchall()

    return [dict(r) for r in rows]


def get_nl_timestamp() -> str:
    try:
        return datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%Y-%m-%d %H:%M:%S")
    except ZoneInfoNotFoundError:
        return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def insert_comment(turbine_type: str, alarm_code_id: int, comment_text: str) -> None:
    nl_now = get_nl_timestamp()
    db_path = DB_BY_TURBINE[turbine_type]
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        ensure_comments_table(conn)
        conn.execute(
            """
            INSERT INTO faq_comments (entry_alarm_code_id, date, comment_text)
            VALUES (?, ?, ?)
            """,
            (alarm_code_id, nl_now, comment_text),
        )


def resolve_db_path(stored_path: str) -> Path:
    path = Path(stored_path)
    if path.is_absolute():
        return path
    return (BASE_DIR / path).resolve()


def fetch_image_data(turbine_type: str, image_id: int) -> tuple[bytes | None, str | None]:
    db_path = DB_BY_TURBINE[turbine_type]
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT image_blob, resolved_path, exists_on_disk
            FROM faq_images
            WHERE id = ?
            """,
            (image_id,),
        ).fetchone()

    if row is None:
        return None, None

    blob = row["image_blob"]
    resolved_path = resolve_db_path(str(row["resolved_path"]))
    mime_type, _ = mimetypes.guess_type(resolved_path.name)
    content_type = mime_type or "application/octet-stream"

    if blob is not None:
        return bytes(blob), content_type

    if row["exists_on_disk"] and resolved_path.exists() and resolved_path.is_file():
        return resolved_path.read_bytes(), content_type

    return None, None


def fetch_document_data(turbine_type: str, link_id: int) -> tuple[bytes | None, str | None, str | None]:
    db_path = DB_BY_TURBINE[turbine_type]
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT resolved_path, exists_on_disk
            FROM faq_links
            WHERE id = ?
            """,
            (link_id,),
        ).fetchone()

    if row is None:
        return None, None, None

    resolved_path = resolve_db_path(str(row["resolved_path"]))
    if not row["exists_on_disk"] or not resolved_path.exists() or not resolved_path.is_file():
        return None, None, None

    mime_type, _ = mimetypes.guess_type(resolved_path.name)
    content_type = mime_type or "application/octet-stream"
    return resolved_path.read_bytes(), content_type, resolved_path.name
