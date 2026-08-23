import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Iterable, List

from flask import Flask, jsonify, render_template, request, send_from_directory, url_for

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mitacs_scraper.scraper.final_ui_scraper import count_keyword, scrape_keyword

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


def parse_keyword_list(payload: Dict[str, Any]) -> List[str]:
    raw_keywords = payload.get("keywords")
    if isinstance(raw_keywords, list):
        values = [str(item).strip() for item in raw_keywords if str(item).strip()]
        return values[:10]

    if isinstance(raw_keywords, str) and raw_keywords.strip():
        return [raw_keywords.strip()]

    fallback = str(payload.get("keyword", "")).strip()
    if fallback:
        return [fallback]
    return []


def parse_filters(values: Dict[str, Any]) -> Dict[str, str]:
    filters: Dict[str, str] = {}
    for key in FILTER_KEYS:
        value = values.get(key)
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            filters[key] = normalized
    return filters


def parse_max_pages(raw_value: Any) -> int:
    try:
        value = int(str(raw_value).strip()) if raw_value is not None else 0
    except ValueError:
        value = 0
    if value < 0:
        return 0
    return value


def run_batch_scrape(
    keywords: List[str],
    max_pages: int,
    export_format: str,
    filters: Dict[str, str],
) -> List[Dict[str, Any]]:
    def fetch_one(keyword: str) -> Dict[str, Any]:
        label = build_export_label(keyword, max_pages)
        csv_path = EXPORT_DIR / f"{label}.csv"
        md_path = EXPORT_DIR / f"{label}.md"
        try:
            records = scrape_keyword(
                keyword,
                max_pages=max_pages,
                output_path=str(csv_path),
                filters=filters,
            )
            if export_format in {"md", "both"}:
                export_markdown(records, keyword, md_path)
            return {
                "keyword": keyword,
                "records": records,
                "csv_path": csv_path,
                "md_path": md_path if export_format in {"md", "both"} else None,
                "error": None,
            }
        except Exception as exc:
            return {
                "keyword": keyword,
                "records": [],
                "csv_path": csv_path,
                "md_path": None,
                "error": str(exc),
            }

    with ThreadPoolExecutor(max_workers=min(4, len(keywords))) as executor:
        return list(executor.map(fetch_one, keywords))


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
    app.config["SECRET_KEY"] = os.environ.get("MITACS_SECRET_KEY", "mitacs-dev-secret")

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.route("/health")
    @app.route("/api/health")
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
        max_pages = parse_max_pages(request.form.get("max_pages"))
        filters = parse_filters(request.form)

        if not keyword_values:
            return render_template(
                "index.html",
                keyword_count=1,
                keyword_values=[""],
                max_pages=max_pages,
                export_format=export_format,
                preview_rows=[],
                summary="",
                download_links=[],
                error="Please enter at least one keyword before running the search.",
            )

        results = run_batch_scrape(keyword_values, max_pages, export_format, filters)

        download_links: List[Dict[str, str]] = []
        preview_rows: List[Dict[str, str]] = []
        total_records = 0
        errors: List[str] = []

        for item in results:
            if item["error"]:
                errors.append(f"{item['keyword']}: {item['error']}")
                continue

            total_records += len(item["records"])
            if not preview_rows and item["records"]:
                preview_rows = item["records"][:5]

            if export_format in {"csv", "both"}:
                download_links.append({
                    "label": f"{item['keyword']} CSV",
                    "url": url_for("download_file", filename=item["csv_path"].name),
                })
            if export_format in {"md", "both"} and item["md_path"] is not None:
                download_links.append({
                    "label": f"{item['keyword']} Markdown",
                    "url": url_for("download_file", filename=item["md_path"].name),
                })

        summary = f"Scraped {total_records} project(s) across {len(keyword_values)} keyword batch."
        if errors:
            summary = summary + " Failures: " + "; ".join(errors)

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

    @app.route("/api/scrape", methods=["POST", "OPTIONS"])
    def api_scrape():
        if request.method == "OPTIONS":
            return ("", 204)

        if not request.is_json:
            return jsonify({"error": "JSON body required."}), 400

        payload = request.get_json()
        keywords = parse_keyword_list(payload or {})
        if not keywords:
            return jsonify({"error": "Provide at least one keyword in 'keywords' or 'keyword'."}), 400

        export_format = str((payload or {}).get("export_format", "csv")).lower()
        if export_format not in {"csv", "md", "both"}:
            return jsonify({"error": "export_format must be one of: csv, md, both."}), 400

        max_pages = parse_max_pages((payload or {}).get("max_pages", 0))
        filters = parse_filters(payload or {})

        results = run_batch_scrape(keywords, max_pages, export_format, filters)
        files: List[Dict[str, str]] = []
        response_items: List[Dict[str, Any]] = []
        total_records = 0

        for item in results:
            if item["error"]:
                response_items.append({
                    "keyword": item["keyword"],
                    "count": 0,
                    "error": item["error"],
                    "files": [],
                })
                continue

            total_records += len(item["records"])
            current_files: List[Dict[str, str]] = []
            if export_format in {"csv", "both"}:
                csv_name = item["csv_path"].name
                csv_url = url_for("download_file", filename=csv_name, _external=True)
                current_files.append({"type": "csv", "name": csv_name, "url": csv_url})
                files.append({"type": "csv", "name": csv_name, "url": csv_url})
            if export_format in {"md", "both"} and item["md_path"] is not None:
                md_name = item["md_path"].name
                md_url = url_for("download_file", filename=md_name, _external=True)
                current_files.append({"type": "md", "name": md_name, "url": md_url})
                files.append({"type": "md", "name": md_name, "url": md_url})

            response_items.append({
                "keyword": item["keyword"],
                "count": len(item["records"]),
                "preview": item["records"][:5],
                "files": current_files,
                "error": None,
            })

        return jsonify({
            "total_keywords": len(keywords),
            "total_records": total_records,
            "export_format": export_format,
            "results": response_items,
            "files": files,
        })

    @app.route("/api/count", methods=["POST", "OPTIONS"])
    def api_count():
        if request.method == "OPTIONS":
            return ("", 204)

        if not request.is_json:
            return jsonify({"error": "JSON body required."}), 400

        payload = request.get_json() or {}
        keywords = parse_keyword_list(payload)
        if not keywords:
            return jsonify({"error": "Provide at least one keyword in 'keywords' or 'keyword'."}), 400

        filters = parse_filters(payload)

        def count_one(keyword: str) -> Dict[str, Any]:
            try:
                info = count_keyword(keyword, filters=filters)
                return {
                    "keyword": keyword,
                    "total_projects": info.get("total_projects", 0),
                    "per_page": info.get("per_page", 0),
                    "total_pages": info.get("total_pages", 0),
                    "error": None,
                }
            except Exception as exc:
                return {
                    "keyword": keyword,
                    "total_projects": 0,
                    "per_page": 0,
                    "total_pages": 0,
                    "error": str(exc),
                }

        with ThreadPoolExecutor(max_workers=min(4, len(keywords))) as executor:
            results = list(executor.map(count_one, keywords))

        return jsonify({
            "total_keywords": len(keywords),
            "results": results,
        })

    @app.route("/download/<path:filename>")
    def download_file(filename: str):
        return send_from_directory(EXPORT_DIR, filename, as_attachment=True)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
