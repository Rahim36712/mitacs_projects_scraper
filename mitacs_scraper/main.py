"""
CLI entrypoint for discovery and small sample crawls.
"""
import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mitacs_scraper.scraper.spider import Spider
from mitacs_scraper.storage.csv_exporter import export_csv, export_json
from mitacs_scraper.storage.database import Database
from mitacs_scraper import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cmd_discover(args):
    s = Spider(rate_limit=config.RATE_LIMIT)
    info = s.run_discovery(args.url, use_dynamic_probe=args.dynamic)
    print(info)


def cmd_crawl_sample(args):
    s = Spider(rate_limit=config.RATE_LIMIT)
    records = s.crawl_sample(args.url, sample_limit=args.limit)
    # persist to sqlite and exports
    db = Database(str(config.DB_PATH))
    for r in records:
        db.save_project(r)
    export_csv(records, str(config.OUTPUT_CSV))
    export_json(records, str(config.OUTPUT_JSON))
    print(f"Exported {len(records)} records to {config.OUTPUT_CSV} and {config.OUTPUT_JSON}")


def cmd_ui(args):
    from mitacs_scraper.ui_app import app
    app.run(host=args.host, port=args.port, debug=args.debug)


def main(argv=None):
    p = argparse.ArgumentParser(prog="mitacs-scraper")
    sub = p.add_subparsers(dest="cmd")

    d = sub.add_parser("discover")
    d.add_argument("url")
    d.add_argument("--dynamic", action="store_true", help="Probe XHRs with dynamic rendering (if available)")
    d.set_defaults(func=cmd_discover)

    c = sub.add_parser("crawl-sample")
    c.add_argument("url")
    c.add_argument("--limit", type=int, default=5)
    c.set_defaults(func=cmd_crawl_sample)

    k = sub.add_parser("crawl-keyword", help="Crawl projects for a keyword and export CSV (id,title,description,start_date,language)")
    k.add_argument("keyword", help="Keyword to enter into the site's keyword search")
    k.add_argument("--out", default=str(config.OUTPUT_CSV), help="Output CSV path")
    k.add_argument("--max-pages", type=int, default=0, help="Optional max pages to collect (0 = all)")
    import importlib as _il
    k.set_defaults(func=lambda args: _il.import_module('mitacs_scraper.scraper.crawl_keyword').crawl_keyword_to_csv(args.keyword, args.out, args.max_pages))

    u = sub.add_parser("ui", help="Launch the browser-based MITACS scraper UI")
    u.add_argument("--host", default="0.0.0.0")
    u.add_argument("--port", type=int, default=5000)
    u.add_argument("--debug", action="store_true")
    u.set_defaults(func=cmd_ui)

    args = p.parse_args(argv)
    if not hasattr(args, "func"):
        p.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
