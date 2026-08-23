# MITACS Research Project Scraper

Overview
- Browser-driven scraper for MITACS Globalink project listings using the live UI.
- Exports the key fields to CSV and optionally to attractive Markdown.
- Includes a lightweight web UI with multi-keyword batch scraping and optional filters.

One-click run on Windows
1. Open the project folder.
2. Double-click: run_ui.bat
3. Browser opens at http://127.0.0.1:5001

Manual launch
1. Create and activate a Python environment.
2. Install requirements: pip install -r mitacs_scraper/requirements.txt
3. Launch the UI: python mitacs_scraper\main.py ui --host 127.0.0.1 --port 5001
4. Open http://127.0.0.1:5001 in your browser.

Web UI features
- Enter how many keywords you want to scrape at once.
- Enter each keyword in its own box.
- Optional filters: language, faculty province, university, campus, first name, last name, academic achievement.
- Choose CSV, Markdown, or both.
- Scrape multiple keywords in parallel and create one output file per keyword.

Command-line example
- Run a keyword search and export CSV:
  python mitacs_scraper\main.py crawl-keyword "microfluidics" --max-pages 2

Notes
- The scraper uses Playwright to interact with the live site and capture the actual filtered result list.
- Supported output fields are: id, title, description, start_date, language.
- CSV and Markdown files are saved under mitacs_scraper/data/ui_exports/ when generated via the web UI.
