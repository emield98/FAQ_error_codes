from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_BY_TURBINE = {
    "VMP5000": BASE_DIR / "database/faq_vmp5000.db",
    "VMP5000.2": BASE_DIR / "database/faq_vmp5000_2.db",
}
