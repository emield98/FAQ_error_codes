from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlencode, urlparse

from .config import DB_BY_TURBINE
from .data import (
    fetch_comments,
    fetch_document_data,
    fetch_entry,
    fetch_image_data,
    insert_comment,
)
from .render import render_page


class FAQRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/image":
            self.handle_image(parsed)
            return

        if parsed.path == "/doc":
            self.handle_document(parsed)
            return

        if parsed.path == "/":
            self.handle_index(parsed)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/comment":
            self.handle_add_comment()
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def handle_index(self, parsed) -> None:
        params = parse_qs(parsed.query)
        turbine_type = params.get("turbine_type", ["VMP5000"])[0]
        alarm_code_raw = params.get("alarm_code", [""])[0].strip()
        notice = params.get("notice", [""])[0].strip()

        error_message = ""
        notice_message = ""
        entry = None
        links: list[dict[str, object]] = []
        images: list[dict[str, object]] = []
        comments: list[dict[str, object]] = []

        if turbine_type not in DB_BY_TURBINE:
            turbine_type = "VMP5000"

        if alarm_code_raw:
            if not alarm_code_raw.isdigit():
                error_message = "Alarm code moet een heel getal zijn."
            else:
                alarm_code_id = int(alarm_code_raw)
                entry, links, images = fetch_entry(turbine_type, alarm_code_id)
                if entry is None:
                    error_message = f"Geen resultaat gevonden voor {turbine_type} met alarm code {alarm_code_id}."
                else:
                    comments = fetch_comments(turbine_type, alarm_code_id)

        if notice == "comment_saved":
            notice_message = "Comment opgeslagen."
        elif notice == "comment_empty":
            error_message = "Comment mag niet leeg zijn."
        elif notice == "comment_invalid":
            error_message = "Ongeldige comment-aanvraag."
        elif notice == "comment_notfound":
            error_message = "Kan geen comment opslaan: alarm code niet gevonden."

        content = render_page(
            turbine_type=turbine_type,
            alarm_code=alarm_code_raw,
            error_message=error_message,
            notice_message=notice_message,
            entry=entry,
            links=links,
            images=images,
            comments=comments,
        )

        encoded = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def handle_add_comment(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        params = parse_qs(raw_body.decode("utf-8", errors="replace"))

        turbine_type = params.get("turbine_type", [""])[0].strip()
        alarm_code_raw = params.get("alarm_code", [""])[0].strip()
        comment_text = params.get("comment_text", [""])[0].strip()

        if turbine_type not in DB_BY_TURBINE or not alarm_code_raw.isdigit():
            self.redirect_to_index(turbine_type, alarm_code_raw, notice="comment_invalid")
            return

        if not comment_text:
            self.redirect_to_index(turbine_type, alarm_code_raw, notice="comment_empty")
            return

        alarm_code_id = int(alarm_code_raw)
        entry, _, _ = fetch_entry(turbine_type, alarm_code_id)
        if entry is None:
            self.redirect_to_index(turbine_type, alarm_code_raw, notice="comment_notfound")
            return

        insert_comment(turbine_type, alarm_code_id, comment_text)
        self.redirect_to_index(turbine_type, alarm_code_raw, notice="comment_saved")

    def redirect_to_index(self, turbine_type: str, alarm_code: str, notice: str) -> None:
        target = "/?" + urlencode(
            {
                "turbine_type": turbine_type,
                "alarm_code": alarm_code,
                "notice": notice,
            }
        )
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", target)
        self.end_headers()

    def handle_image(self, parsed) -> None:
        params = parse_qs(parsed.query)
        turbine_type = params.get("turbine_type", [""])[0]
        image_id_raw = params.get("image_id", [""])[0]

        if turbine_type not in DB_BY_TURBINE or not image_id_raw.isdigit():
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid image request")
            return

        image_data, content_type = fetch_image_data(turbine_type, int(image_id_raw))
        if image_data is None or content_type is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Image not found")
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(image_data)))
        self.end_headers()
        self.wfile.write(image_data)

    def handle_document(self, parsed) -> None:
        params = parse_qs(parsed.query)
        turbine_type = params.get("turbine_type", [""])[0]
        link_id_raw = params.get("link_id", [""])[0]

        if turbine_type not in DB_BY_TURBINE or not link_id_raw.isdigit():
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid document request")
            return

        doc_data, content_type, filename = fetch_document_data(turbine_type, int(link_id_raw))
        if doc_data is None or content_type is None or filename is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Document not found")
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f"inline; filename=\"{filename}\"")
        self.send_header("Content-Length", str(len(doc_data)))
        self.end_headers()
        self.wfile.write(doc_data)
