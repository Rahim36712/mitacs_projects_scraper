import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Iterable, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, send_from_directory, render_template, request, url_for

from mitacs_scraper.scraper.final_ui_scraper import scrape_keyword

BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "data" / "ui_exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

FILTER_KEYS = [
    "language",
    "faculty_province",
    "faculty_university",
    "faculty_campus",
    "faculty_first_name",
    "faculty_last_name",
    "academic_achievement",
]


def slugify_keyword(keyword: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-")
    return cleaned or "projects"


def build_export_label(keyword: str, max_pages: int) -> str:
    return f"{slugify_keyword(keyword)}_{'all' if max_pages == 0 else max_pages}pages"


def export_markdown(records: Iterable[Dict[str, Any]], keyword: str, destination: Path) -> None:
    rows = list(records)
    lines: List[str] = [
        "# MITACS Projects",
        "",
        f"**Keyword:** {keyword}",
        f"**Total records:** {len(rows)}",
        "",
    ]

    if not rows:
        lines.append("No projects matched the selected keyword.")
    else:
        lines.extend([
            "| ID | Title | Start Date | Language |",
            "| --- | --- | --- | --- |",
        ])
        for row in rows:
            project_id = str(row.get("id", "")).replace("|", "\\|")
            title = str(row.get("title", "")).replace("|", "\\|")
            start_date = str(row.get("start_date", "N/A")).replace("|", "\\|")
            language = str(row.get("language", "N/A")).replace("|", "\\|")
            lines.append(f"| {project_id} | {title} | {start_date} | {language} |")

        lines.extend(["", "---", ""])
        for row in rows:
            project_id = str(row.get("id", ""))
            title = str(row.get("title", "")).strip()
            description = str(row.get("description", "")).strip() or "No description available."
            start_date = str(row.get("start_date", "N/A")).strip() or "N/A"
            language = str(row.get("language", "N/A")).strip() or "N/A"
            lines.extend([
                f"## {title} ({project_id})",
                "",
                f"- Start date: {start_date}",
                f"- Language: {language}",
                "",
                description,
                "",
                "---",
                "",
            ])

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def parse_keyword_batch(form: Dict[str, Any]) -> List[str]:
    batch_count = form.get("keyword_count")
    try:
        count = int((batch_count or "1").strip() or "1")
    except ValueError:
        count = 1
    count = max(1, min(count, 10))

    keywords: List[str] = []
    for index in range(1, count + 1):
        keyword = (form.get(f"keyword_{index}") or "").strip()
        if keyword:
            keywords.append(keyword)

    fallback = (form.get("keyword") or "").strip()
    if fallback and not keywords:
        keywords.append(fallback)
    return keywords


def parse_filters(form: Dict[str, Any]) -> Dict[str, str]:
    filters: Dict[str, str] = {}
    for key in FILTER_KEYS:
        value = (form.get(key) or "").strip()
        if value:
            filters[key] = value
    return filters


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
    app.config["SECRET_KEY"] = os.environ.get("MITACS_SECRET_KEY", "mitacs-dev-secret")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            keyword_count=1,
            keyword_values=[""],
            max_pages=0,
            export_format="csv",
            preview_rows=[],
            summary="",
            download_links=[],
            error=None,
        )

    @app.route("/run", methods=["POST"])
    def run_scraper():
        keyword_values = parse_keyword_batch(request.form)
        export_format = (request.form.get("export_format") or "csv").lower()
        raw_pages = (request.form.get("max_pages") or "0").strip()
        filters = parse_filters(request.form)

        if not keyword_values:
            return render_template(
                "index.html",
                keyword_count=1,
                keyword_values=[""],
                max_pages=int(raw_pages) if raw_pages.isdigit() else 0,
                export_format=export_format,
                preview_rows=[],
                summary="",
                download_links=[],
                error="Please enter at least one keyword before running the search.",
            )

        try:
            max_pages = int(raw_pages) if raw_pages else 0
        except ValueError:
            max_pages = 0
        if max_pages < 0:
            max_pages = 0

        def fetch_one(keyword: str):
            label = build_export_label(keyword, max_pages)
            csv_path = EXPORT_DIR / f"{label}.csv"
            try:
                records = scrape_keyword(keyword, max_pages=max_pages, output_path=str(csv_path), filters=filters)
                if export_format in {"md", "both"}:
                    export_markdown(records, keyword, EXPORT_DIR / f"{label}.md")
                return {
                    "keyword": keyword,
                    "records": records,
                    "csv_path": csv_path,
                    "md_path": EXPORT_DIR / f"{label}.md" if export_format in {"md", "both"} else None,
                }
            except Exception as exc:  # pragma: no cover - surfaced in UI
                return {
                    "keyword": keyword,
                    "records": [],
                    "csv_path": csv_path,
                    "md_path": None,
                    "error": str(exc),
                }

        with ThreadPoolExecutor(max_workers=min(4, len(keyword_values))) as executor:
            results = list(executor.map(fetch_one, keyword_values))

        valid_results = [r for r in results if r.get("records") or r.get("error")]
        download_links: List[Dict[str, str]] = []
        for item in valid_results:
            if item.get("error"):
                continue
            if export_format in {"csv", "both"}:
                download_links.append({
                    "label": f"{item['keyword']} CSV",
                    "url": url_for("download_file", filename=item["csv_path"].name),
                })
            if export_format in {"md", "both"} and item.get("md_path"):
                download_links.append({
                    "label": f"{item['keyword']} Markdown",
                    "url": url_for("download_file", filename=item["md_path"].name),
                })

        preview_rows = []
        total_records = 0
        for item in valid_results:
            total_records += len(item.get("records") or [])
            if not preview_rows and item.get("records"):
                preview_rows = item["records"][:5]

        summary = f"Scraped {total_records} project(s) across {len(keyword_values)} keyword batch."
        if any(item.get("error") for item in valid_results):
            error_summary = "; ".join(item["error"] for item in valid_results if item.get("error"))
            summary = summary + f" Some keywords failed: {error_summary}"

        return render_template(
            "index.html",
            keyword_count=len(keyword_values),
            keyword_values=keyword_values,
            max_pages=max_pages,
            export_format=export_format,
            preview_rows=preview_rows,
            summary=summary,
            download_links=download_links,
            error=None,
        )

    @app.route("/download/<path:filename>")
    def download_file(filename: str):
        return send_from_directory(EXPORT_DIR, filename, as_attachment=True)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
