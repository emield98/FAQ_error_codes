from __future__ import annotations

from http.server import ThreadingHTTPServer
import argparse

from .config import DB_BY_TURBINE
from .handlers import FAQRequestHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Start lokale FAQ webinterface")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument("--port", default=8000, type=int, help="Poort (default: 8000)")
    args = parser.parse_args()

    missing = [name for name, path in DB_BY_TURBINE.items() if not path.exists()]
    if missing:
        names = ", ".join(missing)
        raise SystemExit(f"Database ontbreekt voor: {names}. Run eerst build_faq_databases.py")

    server = ThreadingHTTPServer((args.host, args.port), FAQRequestHandler)
    print(f"Server draait op http://{args.host}:{args.port}")
    server.serve_forever()
