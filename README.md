# FAQ Error Codes

Local tool for browsing Vestas turbine FAQ/alarm-code documentation. It parses
the restricted `Vestas FAQ en SW/` HTML sources into SQLite databases and
serves them through a small local web UI.

## Project layout

```
FAQ_error_codes/
├── build_faq_databases.py   # Parses HTML FAQ files into SQLite
├── faq_ui.py                # Entry point for the local web UI
├── faq_ui_app/              # Web UI package (server, handlers, rendering)
│   ├── config.py
│   ├── server.py
│   ├── handlers.py
│   ├── render.py
│   └── data.py
├── database/                # Generated SQLite databases (git-ignored)
└── Vestas FAQ en SW/        # Source HTML documentation (git-ignored, restricted)
```

The `Vestas FAQ en SW/` folder and the `database/` folder are excluded from
git because the Vestas material is restricted and the databases are
generated artifacts.

## Requirements

- Python 3.10+
- Only the Python standard library is used (`sqlite3`, `http.server`, etc.)

## Usage

### 1. Build the databases

The source HTML lives in `Vestas FAQ en SW/FAQ/LinkedDocuments/`. Run:

```bash
python build_faq_databases.py
```

This creates two SQLite files in `database/`:

- `faq_vmp5000.db`   — entries with prefix `VMP5000_`
- `faq_vmp5000_2.db` — entries with prefix `VMP5000.2_`

Each database contains:

- `faq_entries`  — one row per alarm code (description, suggestions, status, …)
- `faq_links`    — outgoing document links per entry
- `faq_images`   — referenced images (path + sha256, optionally the blob)
- `faq_comments` — user comments per entry

Set `EMBED_IMAGE_BLOBS = True` in `build_faq_databases.py` if you want the
image bytes stored inside SQLite instead of just path + hash.

### 2. Start the web UI

```bash
python faq_ui.py
```

Optional flags:

```bash
python faq_ui.py --host 127.0.0.1 --port 8000
```

Then open <http://127.0.0.1:8000> in your browser. The UI will refuse to start
if the databases in `database/` are missing — run step 1 first.
