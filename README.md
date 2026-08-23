# MITACS Project Scraper

A user-friendly web app for scraping MITACS Globalink project listings by keyword, exporting the results to CSV or Markdown, and running multiple keywords in parallel.

## Highlights

- Search MITACS projects with a live browser-driven scraper
- Export results as CSV, Markdown, or both
- Run several keywords at once in parallel
- Optional filters for language, faculty province, university, campus, and more
- Easy one-click launch on Windows
- Clean desktop-style UI for a smoother user experience

## Project structure

- `mitacs_scraper/` — core scraper and Flask UI
- `mitacs_scraper/data/` — exported CSV/Markdown outputs
- `mitacs_scraper/scraper/` — browser-driven scraping logic
- `run_ui.bat` — one-click launcher for Windows

## Quick start

### One-click run (Windows)

1. Open the project folder
2. Double-click `run_ui.bat`
3. Visit: http://127.0.0.1:5001

### Manual run

```bash
pip install -r mitacs_scraper/requirements.txt
python mitacs_scraper\main.py ui --host 127.0.0.1 --port 5001
```

Then open:

```text
http://127.0.0.1:5001
```

## Usage

From the web UI:

- Set how many keywords you want to scrape
- Enter each keyword in its own field
- Choose the max pages to crawl
- Select export format: CSV, Markdown, or both
- Optionally add filters like language or faculty details
- Click `Run scraper`

## Output

Each keyword creates its own output file in the `mitacs_scraper/data/ui_exports/` folder.

## Notes

This project uses Playwright to interact with the live MITACS website and extract the project data visible after filtering.

## License

This project is provided for educational and research purposes.
