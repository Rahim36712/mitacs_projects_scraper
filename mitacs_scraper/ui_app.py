import atexit
import os
import re
import subprocess
import sys
import threading
import time
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

START_MONOTONIC = time.monotonic()
WATCHDOG_STATE = {"last_beat": 0.0, "jobs": 0, "stopping": False}
STATE_LOCK = threading.Lock()
HEARTBEAT_TIMEOUT_S = float(os.environ.get("MITACS_BEAT_TIMEOUT", "80"))
WARMUP_S = float(os.environ.get("MITACS_WARMUP", "25"))


def kill_leftover_browsers() -> None:
    token = f"x-mitacs-owner={os.getpid()}"
    venv_path = str(PROJECT_ROOT / ".venv")
    wql_filters = [
        f"Name='chrome.exe' AND CommandLine LIKE '%{token}%'",
        f"Name='node.exe' AND CommandLine LIKE '%{venv_path}%playwright%driver%'",
    ]
    for wql in wql_filters:
        ps_command = (
            "$ErrorActionPreference='SilentlyContinue';"
            f"$ids = Get-CimInstance Win32_Process -Filter \"{wql}\" | "
            "Select-Object -ExpandProperty ProcessId;"
            "if ($ids) { $ids | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
                capture_output=True,
                timeout=20,
            )
        except Exception:
            pass


atexit.register(kill_leftover_browsers)


def _shutdown() -> None:
    with STATE_LOCK:
        if WATCHDOG_STATE["stopping"]:
            return
        WATCHDOG_STATE["stopping"] = True
    print("\n[i] UI closed — stopping server and cleaning up browser processes...")
    sys.stdout.flush()
    kill_leftover_browsers()
    os._exit(0)


def _watchdog_loop() -> None:
    while True:
        time.sleep(2)
        try:
            with STATE_LOCK:
                if WATCHDOG_STATE["stopping"]:
                    return
                beat = WATCHDOG_STATE["last_beat"]
                jobs = WATCHDOG_STATE["jobs"]
            idle_too_long = (
                beat > 0
                and jobs == 0
                and (time.time() - beat) > HEARTBEAT_TIMEOUT_S
                and (time.monotonic() - START_MONOTONIC) > WARMUP_S
            )
            if idle_too_long:
                _shutdown()
                return
        except Exception:
            pass

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
    app.config["TEMPLATES_AUTO_RELOAD"] = True

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

    @app.route("/api/heartbeat", methods=["GET", "POST"])
    def heartbeat():
        with STATE_LOCK:
            WATCHDOG_STATE["last_beat"] = time.time()
            WATCHDOG_STATE["stopping"] = False
        return {"status": "ok"}

    @app.route("/")
    def index():
        return render_template("index.html")

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

        with STATE_LOCK:
            WATCHDOG_STATE["last_beat"] = time.time()
            WATCHDOG_STATE["jobs"] += 1
        try:
            results = run_batch_scrape(keywords, max_pages, export_format, filters)
        finally:
            with STATE_LOCK:
                WATCHDOG_STATE["jobs"] -= 1
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

        with STATE_LOCK:
            WATCHDOG_STATE["last_beat"] = time.time()
            WATCHDOG_STATE["jobs"] += 1
        try:
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
        finally:
            with STATE_LOCK:
                WATCHDOG_STATE["jobs"] -= 1

        return jsonify({
            "total_keywords": len(keywords),
            "results": results,
        })

    @app.route("/api/exports", methods=["GET"])
    def api_exports():
        items: List[Dict[str, Any]] = []
        try:
            paths = [p for p in EXPORT_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".csv", ".md"}]
            for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True):
                stat = path.stat()
                items.append({
                    "name": path.name,
                    "size": stat.st_size,
                    "modified": int(stat.st_mtime),
                    "url": url_for("download_file", filename=path.name, _external=True),
                })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
        return jsonify({"count": len(items), "files": items})

    @app.route("/download/<path:filename>")
    def download_file(filename: str):
        return send_from_directory(EXPORT_DIR, filename, as_attachment=True)

    threading.Thread(target=_watchdog_loop, name="mitacs-watchdog", daemon=True).start()
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False, threaded=True)
