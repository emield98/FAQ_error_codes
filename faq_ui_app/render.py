from __future__ import annotations

import html
import re
from urllib.parse import urlencode

from .config import DB_BY_TURBINE


BOLD_MARKER_REGEX = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


def format_field_value(value: object | None) -> str:
  text = str(value) if value is not None else ""
  escaped = html.escape(text)
  return BOLD_MARKER_REGEX.sub(r"<strong>\1</strong>", escaped)


def render_page(
    turbine_type: str,
    alarm_code: str,
    error_message: str,
    notice_message: str,
    entry: dict[str, object] | None,
    links: list[dict[str, object]],
    images: list[dict[str, object]],
    comments: list[dict[str, object]],
) -> str:
    options_html = "".join(
        f"<option value='{html.escape(name)}' {'selected' if name == turbine_type else ''}>{html.escape(name)}</option>"
        for name in DB_BY_TURBINE
    )

    result_html = ""
    if entry is not None:
        rows = [
            ("Alarm code", entry.get("alarm_code")),
            ("Comment", entry.get("comment")),
            ("Description", entry.get("description")),
            ("Vestas Alarm suggestion", entry.get("vestas_alarm_suggestion")),
            ("On-Site suggestion", entry.get("onsite_suggestion")),
        ]

        fields_html = "".join(
          f"<tr><th>{html.escape(str(label))}</th><td class='field-value'>{format_field_value(value)}</td></tr>"
            for label, value in rows
        )

        links_html = ""
        if links:
            link_items = []
            for link in links:
                link_text = str(link.get("link_text") or link.get("href") or "")
                exists = bool(link.get("exists_on_disk"))
                link_id = int(link["id"])
                href = "/doc?" + urlencode({"turbine_type": turbine_type, "link_id": link_id}) if exists else "#"
                target_attr = " target='_blank'" if exists else ""
                disabled = " (missing)" if not exists else ""
                link_items.append(
                    f"<li><a href='{html.escape(href)}'{target_attr}>{html.escape(link_text)}</a>{html.escape(disabled)}</li>"
                )
            links_html = "<h3>Document links</h3><ul>" + "".join(link_items) + "</ul>"

        images_html = ""
        if images:
            image_items = []
            for image_row in images:
                image_id = int(image_row["id"])
                exists = bool(image_row.get("exists_on_disk"))
                src = str(image_row.get("src") or "")
                image_url = "/image?" + urlencode({"turbine_type": turbine_type, "image_id": image_id})
                if exists:
                    image_items.append(
                        "<div class='img-card'>"
                        f"<p>{html.escape(src)}</p>"
                        f"<img src='{html.escape(image_url)}' alt='{html.escape(src)}'>"
                        "</div>"
                    )
                else:
                    image_items.append(
                        "<div class='img-card'>"
                        f"<p>{html.escape(src)} (missing)</p>"
                        "</div>"
                    )
            images_html = "<h3>Images</h3><div class='img-grid'>" + "".join(image_items) + "</div>"

        comments_items = []
        for comment_row in comments:
            comment_date = str(comment_row.get("date") or "")
            comment_text = str(comment_row.get("comment_text") or "")
            comments_items.append(
                "<li class='comment-item'>"
                f"<p class='comment-meta'>{html.escape(comment_date)}</p>"
                f"<p class='comment-text'>{html.escape(comment_text)}</p>"
                "</li>"
            )

        comments_list_html = (
            "<ul class='comment-list'>" + "".join(comments_items) + "</ul>"
            if comments_items
            else "<p>Nog geen comments.</p>"
        )
        comments_form_html = (
            "<h3>Comments</h3>"
            "<form class='comment-form' method='post' action='/comment'>"
            f"<input type='hidden' name='turbine_type' value='{html.escape(turbine_type)}'>"
            f"<input type='hidden' name='alarm_code' value='{html.escape(str(entry.get('alarm_code_id') or ''))}'>"
            "<label for='comment_text'>Nieuwe comment</label>"
            "<textarea id='comment_text' name='comment_text' rows='4' style='width: 100%;' placeholder='Typ hier je comment'></textarea>"
            "<button type='submit'>Opslaan</button>"
            "</form>"
            f"{comments_list_html}"
        )

        result_html = (
            "<section class='result'>"
            "<h2>Result</h2>"
            "<table>"
            f"{fields_html}"
            "</table>"
            f"{links_html}"
            f"{images_html}"
            f"{comments_form_html}"
            "</section>"
        )

    error_html = f"<p class='error'>{html.escape(error_message)}</p>" if error_message else ""
    notice_html = f"<p class='notice'>{html.escape(notice_message)}</p>" if notice_message else ""

    return f"""
<!doctype html>
<html lang='nl'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>FAQ Alarm Lookup</title>
<style>
:root {{
  --bg: #f3f4f6;
  --panel: #ffffff;
  --text: #111827;
  --accent: #0f766e;
  --border: #d1d5db;
  --error: #b91c1c;
}}
body {{
  margin: 0;
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  background: #f8fafc;
  color: var(--text);
}}
main {{
  max-width: 980px;
  margin: 0 auto;
  padding: 24px;
}}
.card {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}}
h1 {{ margin-top: 0; }}
form {{
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 10px;
}}
label {{
  display: block;
  font-size: 14px;
  margin-bottom: 6px;
}}
input, select, button {{
  width: 100%;
  box-sizing: border-box;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
}}
button {{
  background: var(--accent);
  color: white;
  border: none;
  cursor: pointer;
  margin-top: 22px;
}}
.error {{ color: var(--error); }}
.notice {{ color: var(--accent); }}
.result {{ margin-top: 20px; }}
table {{
  width: 100%;
  border-collapse: collapse;
  margin-top: 10px;
}}
th, td {{
  border: 1px solid var(--border);
  padding: 8px;
  text-align: left;
  vertical-align: top;
}}
.field-value {{
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}}
th {{ width: 220px; background: #f9fafb; }}
.img-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}}
.img-card {{
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px;
  background: #fcfcfd;
}}
.img-card img {{
  width: 100%;
  height: auto;
  max-height: 400px;
  object-fit: contain;
  border-radius: 8px;
  background: #f3f4f6;
}}
.comment-form {{
    margin-top: 16px;
    display: block;
}}
.comment-form button {{
    width: auto;
    margin-top: 10px;
    padding: 10px 14px;
}}
.comment-list {{
    list-style: none;
    padding: 0;
    margin: 14px 0 0;
}}
.comment-item {{
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px;
    margin-bottom: 10px;
    background: #f9fafb;
    max-width: 100%;
    overflow: hidden;
}}
.comment-meta {{
    margin: 0 0 6px;
    font-size: 12px;
    color: #4b5563;
}}
.comment-text {{
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    word-break: break-word;
    max-width: 100%;
}}
@media (max-width: 800px) {{
  form {{ grid-template-columns: 1fr; }}
  button {{ margin-top: 0; }}
}}
</style>
</head>
<body>
<main>
  <div class='card'>
    <h1>Alarm code Lookup</h1>
    <form method='get' action='/'>
      <div>
        <label for='turbine_type'>Type</label>
        <select id='turbine_type' name='turbine_type'>{options_html}</select>
      </div>
      <div>
        <label for='alarm_code'>Alarm code</label>
        <input id='alarm_code' name='alarm_code' value='{html.escape(alarm_code)}' placeholder='Bijv. 100'>
      </div>
      <div>
        <button type='submit'>Zoek</button>
      </div>
    </form>
    {error_html}
    {notice_html}
    {result_html}
  </div>
</main>
</body>
</html>
"""
