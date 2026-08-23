# MITACS scraper plan

Status: current work is in good shape and the batch UI has been added.

Current state:
- The browser-driven MITACS search flow is working for keyword-based scraping and CSV export.
- The scraper can export the expected fields: id, title, description, start_date, language.
- A polished web UI now exists, including multi-keyword batch search and optional filter inputs.
- Markdown export is available in addition to CSV.
- Windows one-click launch is supported through run_ui.bat.

What is now implemented:
1. Live UI + page navigation for keyword search.
2. Pagination handling for max-pages or full crawl mode.
3. CSV export for each keyword run.
4. Optional Markdown export for attractive results summaries.
5. Parallel processing for keyword batches.
6. A simple, user-friendly browser interface with multiple keyword inputs and filter fields.

Next action:
- Use the UI to run keyword batches and verify output files in mitacs_scraper/data/ui_exports.
- As needed, extend the optional filters to match additional live fields on the MITACS site.

Deployment update:
- Added a Vercel-compatible static frontend (`index.html`, `vercel.json`).
- Added backend API endpoints for cloud use (`/api/health`, `/api/scrape`).
- Added Docker-based backend deployment files for Render (`Dockerfile`, `render.yaml`).
