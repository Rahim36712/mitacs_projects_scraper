# MITACS Project Scraper

A user-friendly scraper for MITACS Globalink projects that runs **entirely on your own PC**:

- multi-keyword parallel scraping (up to 10 keywords)
- **page-count preview** — see how many pages exist per keyword *before* choosing how many to scrape
- CSV / Markdown exports
- optional filters (language, province, university, campus, faculty names, academic achievement)
- soft animated browser UI served locally by Flask

## Quick start (Windows)

1. Install [Python 3.11+](https://www.python.org/downloads/) once (tick **Add Python to PATH**).
2. Double-click `run_ui.bat`
   - first run creates the environment and installs the browser automatically
3. Your browser opens at `http://127.0.0.1:5001`

## How to use

1. **Keywords** — enter up to 10 keywords, then click **Check available pages**
2. **Depth** — each keyword shows a badge like `📄 27 pages · ~265 projects`; pick how many pages to scrape until (or all)
3. **Export** — click **Start scraping**, watch the progress bar, then download your files

## API endpoints (local)

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/health` | GET | health check |
| `/api/count` | POST | pages/projects available per keyword (no scraping) |
| `/api/scrape` | POST | run scraping + generate export files |
| `/download/<file>` | GET | download an exported file |

Example page-count request:

```json
POST /api/count
{ "keywords": ["biomedical"] }

{
  "results": [
    { "keyword": "biomedical", "total_projects": 265, "per_page": 10, "total_pages": 27 }
  ]
}
```

## Output

Generated files are saved in `mitacs_scraper/data/ui_exports/`.

## Notes

- Playwright drives a headless Chromium because the MITACS project search is dynamic.
- Scraping many pages can take a while — the UI keeps you posted.
- For educational and research use only.

## License

Educational and research use.
