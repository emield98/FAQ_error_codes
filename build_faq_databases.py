from __future__ import annotations

from pathlib import Path
import hashlib
import html
import json
import re
import sqlite3


BASE_DIR = Path(__file__).resolve().parent
LINKED_DOCS_DIR = (BASE_DIR / "Vestas FAQ en SW/FAQ/LinkedDocuments").resolve()
DB_TARGETS = (
	{
		"label": "VMP5000",
		"prefix": "VMP5000_",
		"db_path": BASE_DIR / "database/faq_vmp5000.db",
	},
	{
		"label": "VMP5000.2",
		"prefix": "VMP5000.2_",
		"db_path": BASE_DIR / "database/faq_vmp5000_2.db",
	},
)

# Zet op True als je ook de image-bytes als BLOB in SQLite wilt opslaan.
EMBED_IMAGE_BLOBS = False


ROW_REGEX = re.compile(r"<tr>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>", re.IGNORECASE | re.DOTALL)
IMG_REGEX = re.compile(r"<img[^>]*src=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)
HREF_REGEX = re.compile(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
BR_REGEX = re.compile(r"<br\s*/?>", re.IGNORECASE)
BLOCK_TAG_REGEX = re.compile(r"</?(?:p|div|li|ul|ol|h[1-6]|tr|td|table)\b[^>]*>", re.IGNORECASE)
BOLD_TAG_REGEX = re.compile(r"</?(?:b|strong)\b[^>]*>", re.IGNORECASE)
TAG_REGEX = re.compile(r"<[^>]+>")
MULTI_NEWLINE_REGEX = re.compile(r"\n{3,}")
ALARM_CODE_ID_REGEX = re.compile(r"^\s*(\d+)")
FILENAME_CODE_REGEX = re.compile(r"_(\d+)\.html$", re.IGNORECASE)


def normalize_text(value: str) -> str:
	value = BR_REGEX.sub("\n", value)
	value = BLOCK_TAG_REGEX.sub("\n", value)
	value = BOLD_TAG_REGEX.sub("**", value)
	value = TAG_REGEX.sub("", value)
	value = html.unescape(value)
	value = value.replace("\xa0", " ")
	value = value.replace("\r\n", "\n").replace("\r", "\n")
	value = MULTI_NEWLINE_REGEX.sub("\n\n", value)
	return value.strip()


def extract_rows(html_text: str) -> dict[str, str]:
	rows: dict[str, str] = {}
	for key_raw, value_raw in ROW_REGEX.findall(html_text):
		key = normalize_text(key_raw)
		value = normalize_text(value_raw)
		if key:
			rows[key] = value
	return rows


def extract_images(html_text: str) -> list[str]:
	return [m.strip() for m in IMG_REGEX.findall(html_text) if m.strip()]


def extract_links(html_text: str) -> list[tuple[str, str]]:
	links: list[tuple[str, str]] = []
	for href, text in HREF_REGEX.findall(html_text):
		clean_href = href.strip()
		clean_text = normalize_text(text)
		if clean_href:
			links.append((clean_href, clean_text))
	return links


def parse_alarm_code_id(alarm_code: str | None) -> int | None:
	if not alarm_code:
		return None
	match = ALARM_CODE_ID_REGEX.match(alarm_code)
	if not match:
		return None
	return int(match.group(1))


def parse_alarm_code_id_from_filename(file_name: str) -> int | None:
	match = FILENAME_CODE_REGEX.search(file_name)
	if not match:
		return None
	return int(match.group(1))


def resolve_relative_path(source_html: Path, relative_path: str) -> Path:
	clean = relative_path.replace("\\", "/").strip()
	return (source_html.parent / clean).resolve()


def to_db_path(path: Path) -> str:
	try:
		return path.relative_to(BASE_DIR).as_posix()
	except ValueError:
		# Buiten de projectmap: bewaar als absolute fallback.
		return path.as_posix()


def sha256_of_file(path: Path) -> str | None:
	if not path.exists() or not path.is_file():
		return None
	hasher = hashlib.sha256()
	with path.open("rb") as f:
		for chunk in iter(lambda: f.read(65536), b""):
			hasher.update(chunk)
	return hasher.hexdigest()


def create_schema(conn: sqlite3.Connection) -> None:
	conn.executescript(
		"""
		CREATE TABLE IF NOT EXISTS faq_entries (
			alarm_code_id INTEGER PRIMARY KEY,
			source_file TEXT NOT NULL UNIQUE,
			control_manufacturer TEXT,
			turbine_manufacturer TEXT,
			turbine_type TEXT,
			alarm_code TEXT,
			comment TEXT,
			description TEXT,
			vestas_alarm_suggestion TEXT,
			onsite_suggestion TEXT,
			link_to_document_raw TEXT,
			status TEXT,
			raw_fields_json TEXT NOT NULL
		);

		CREATE TABLE IF NOT EXISTS faq_links (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			entry_alarm_code_id INTEGER NOT NULL,
			href TEXT NOT NULL,
			link_text TEXT,
			resolved_path TEXT NOT NULL,
			exists_on_disk INTEGER NOT NULL,
			FOREIGN KEY(entry_alarm_code_id) REFERENCES faq_entries(alarm_code_id) ON DELETE CASCADE
		);

		CREATE TABLE IF NOT EXISTS faq_images (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			entry_alarm_code_id INTEGER NOT NULL,
			src TEXT NOT NULL,
			resolved_path TEXT NOT NULL,
			exists_on_disk INTEGER NOT NULL,
			sha256 TEXT,
			image_blob BLOB,
			FOREIGN KEY(entry_alarm_code_id) REFERENCES faq_entries(alarm_code_id) ON DELETE CASCADE
		);

		CREATE TABLE IF NOT EXISTS faq_comments (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			entry_alarm_code_id INTEGER NOT NULL,
			date DATETIME DEFAULT CURRENT_TIMESTAMP,
			comment_text TEXT NOT NULL,
			FOREIGN KEY(entry_alarm_code_id) REFERENCES faq_entries(alarm_code_id) ON DELETE CASCADE
		);
		"""
	)


def insert_entry(conn: sqlite3.Connection, html_file: Path) -> tuple[int, int, int]:
	html_text = html_file.read_text(encoding="utf-8", errors="replace")
	rows = extract_rows(html_text)
	links = extract_links(html_text)
	images = extract_images(html_text)
	alarm_code = rows.get("Alarm code")
	alarm_code_id = parse_alarm_code_id(alarm_code)
	if alarm_code_id is None:
		alarm_code_id = parse_alarm_code_id_from_filename(html_file.name)
	if alarm_code_id is None:
		raise ValueError(f"Geen alarm_code_id gevonden voor {html_file.name}")

	conn.execute(
		"""
		INSERT INTO faq_entries (
			alarm_code_id,
			source_file,
			control_manufacturer,
			turbine_manufacturer,
			turbine_type,
			alarm_code,
			comment,
			description,
			vestas_alarm_suggestion,
			onsite_suggestion,
			link_to_document_raw,
			status,
			raw_fields_json
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		""",
		(
			alarm_code_id,
			html_file.name,
			rows.get("Control manufacturer"),
			rows.get("Turbine manufacturer"),
			rows.get("Type"),
			alarm_code,
			rows.get("Comment"),
			rows.get("Description"),
			rows.get("Vestas Alarm suggestion"),
			rows.get("On-Site suggestion"),
			rows.get("Link to document"),
			rows.get("Status"),
			json.dumps(rows, ensure_ascii=True),
		),
	)

	for href, text in links:
		resolved = resolve_relative_path(html_file, href)
		stored_path = to_db_path(resolved)
		conn.execute(
			"""
			INSERT INTO faq_links (entry_alarm_code_id, href, link_text, resolved_path, exists_on_disk)
			VALUES (?, ?, ?, ?, ?)
			""",
			(alarm_code_id, href, text, stored_path, int(resolved.exists())),
		)

	for src in images:
		resolved = resolve_relative_path(html_file, src)
		stored_path = to_db_path(resolved)
		exists = resolved.exists() and resolved.is_file()
		sha = sha256_of_file(resolved) if exists else None
		blob_data = resolved.read_bytes() if exists and EMBED_IMAGE_BLOBS else None
		conn.execute(
			"""
			INSERT INTO faq_images (entry_alarm_code_id, src, resolved_path, exists_on_disk, sha256, image_blob)
			VALUES (?, ?, ?, ?, ?, ?)
			""",
			(alarm_code_id, src, stored_path, int(exists), sha, blob_data),
		)

	return 1, len(links), len(images)


def build_database(label: str, prefix: str, db_path: Path) -> None:
	html_files = sorted(
		path
		for path in LINKED_DOCS_DIR.glob(f"{prefix}*.html")
		if path.name.startswith(prefix)
	)

	if not html_files:
		print(f"[{label}] Geen bestanden gevonden voor prefix {prefix}")
		return

	if db_path.exists():
		db_path.unlink()

	with sqlite3.connect(db_path) as conn:
		conn.execute("PRAGMA foreign_keys = ON")
		create_schema(conn)

		entry_count = 0
		link_count = 0
		image_count = 0

		for html_file in html_files:
			e, l, i = insert_entry(conn, html_file)
			entry_count += e
			link_count += l
			image_count += i

	print(f"[{label}] Klaar. Database: {db_path}")
	print(f"[{label}] Entries: {entry_count}")
	print(f"[{label}] Links: {link_count}")
	print(f"[{label}] Images: {image_count}")


def main() -> None:
	if not LINKED_DOCS_DIR.exists() or not LINKED_DOCS_DIR.is_dir():
		print(f"Map niet gevonden: {LINKED_DOCS_DIR}")
		raise SystemExit(1)

	for target in DB_TARGETS:
		build_database(
			label=target["label"],
			prefix=target["prefix"],
			db_path=target["db_path"],
		)

	if EMBED_IMAGE_BLOBS:
		print("Afbeeldingen zijn ook als BLOB opgeslagen.")
	else:
		print("Afbeeldingen zijn als pad+metadata opgeslagen (geen BLOB).")


if __name__ == "__main__":
	main()
