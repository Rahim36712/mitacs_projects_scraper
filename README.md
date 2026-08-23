# MITACS Project Scraper

A user-friendly scraper for MITACS Globalink projects with:
- multi-keyword parallel scraping,
- CSV / Markdown exports,
- optional filters,
- local UI and cloud deployment (Vercel + Render).

## Highlights

- Live browser-driven scraping with Playwright
- Parallel scraping for 2-10 keywords in one run
- Export format: CSV, Markdown, or both
- Optional filters: language, province, university, campus, faculty names, academic achievement
- One-click local run (`run_ui.bat`)
- Cloud setup: Vercel frontend + Render backend API

## Local run (Windows)

1. Open the project folder
2. Double-click `run_ui.bat`
3. Open `http://127.0.0.1:5001`

## Cloud deployment (recommended)

### 1) Deploy backend API on Render

This repo includes:
- `Dockerfile`
- `render.yaml`

Steps:
1. Push this repo to GitHub
2. In Render, create **New Web Service** from this repo
3. Choose Docker deploy (Render auto-detects `Dockerfile`)
4. Deploy and copy backend URL, e.g. `https://mitacs-scraper-api.onrender.com`
5. Verify: `https://<your-render-url>/api/health`

### 2) Deploy frontend UI on Vercel

This repo includes:
- `index.html` (Vercel frontend)
- `vercel.json`
- `api/scrape-proxy.js` (proxy to backend API)
- `api/backend-health.js` (backend connectivity check)

Steps:
1. In Vercel, import this same GitHub repo
2. In **Project Settings → Environment Variables**, add:
   - `SCRAPER_BACKEND_URL = https://<your-render-url>`
3. Redeploy Vercel
4. Open Vercel URL
5. Click **Check Backend Connection**
6. Run scraping from browser

Optional:
- You can still override backend URL manually in the UI for testing.

## API endpoint

`POST /api/scrape`

Example JSON body:

```json
{
  "keywords": ["microfluidics", "biomedical", "machine learning"],
  "max_pages": 2,
  "export_format": "both",
  "language": "English"
}
```

The API returns:
- record counts
- preview rows
- downloadable file URLs

## Vercel proxy endpoints

- `GET /api/backend-health` → checks if Vercel can reach your backend
- `POST /api/scrape-proxy` → forwards scraping requests from UI to backend

## Output

Generated files are saved in:
- `mitacs_scraper/data/ui_exports/`

## Notes

- Playwright is required because MITACS project search is dynamic.
- Vercel serverless is not used for scraping itself due browser/runtime limits; scraping runs in backend service (Render/Railway style).

## License

Educational and research use.
