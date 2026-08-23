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

Architecture: **Vercel** hosts the UI + API proxies → **Oracle Cloud Always-Free VM** runs the Playwright scraper API. (Render/Railway also work — see `Dockerfile` / `render.yaml`.)

### 1) Deploy backend API on an Oracle Free VM (Ubuntu 22.04/24.04)

1. Create your Always-Free instance (VM.Standard.A1.Flex ARM or E2.1.Micro AMD), Ubuntu image
2. SSH in and run the one-shot setup script:

```bash
git clone https://github.com/Rahim36712/mitacs_projects_scraper.git
cd mitacs_projects_scraper
sudo bash deploy/oracle/setup_server.sh
```

The script installs Python + Playwright Chromium, registers a **systemd service** (`mitacs-scraper`) on port `8000`, and opens the port in the local firewall.

3. **Manual step (required):** open TCP `8000` in the Oracle Cloud console:
   - Networking → Virtual Cloud Networks → *your VCN* → Security Lists → Default Security List → **Add Ingress Rule**
   - Source CIDR `0.0.0.0/0`, IP Protocol `TCP`, Destination Port Range `8000`
4. Verify from your laptop: `curl http://<VM_PUBLIC_IP>:8000/api/health`

Useful commands on the VM:

```bash
journalctl -u mitacs-scraper -f     # logs
systemctl restart mitacs-scraper    # restart
```

To update the backend after code changes:

```bash
sudo bash deploy/oracle/setup_server.sh   # safe to re-run, pulls latest main
```

### 2) Deploy frontend UI on Vercel

This repo includes:
- `index.html` (Vercel frontend)
- `vercel.json`
- `api/scrape-proxy.js` (proxy to backend API)
- `api/backend-health.js` (backend connectivity check)

Steps:
1. In Vercel, import this same GitHub repo
2. In **Project Settings → Environment Variables**, add:
   - `SCRAPER_BACKEND_URL = http://<VM_PUBLIC_IP>:8000`
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

### Page count endpoint

`POST /api/count`

Returns available pages/projects per keyword **without** scraping them, so the UI can show you how many pages exist before you choose how many to scrape:

```json
{ "keywords": ["biomedical"] }
```

```json
{
  "results": [
    { "keyword": "biomedical", "total_projects": 265, "per_page": 10, "total_pages": 27 }
  ]
}
```

## Vercel proxy endpoints

- `GET /api/backend-health` → checks if Vercel can reach your backend
- `POST /api/scrape-proxy` → forwards scraping requests from UI to backend
- `POST /api/count-proxy` → forwards page-count checks from UI to backend

## Output

Generated files are saved in:
- `mitacs_scraper/data/ui_exports/`

## Notes

- Playwright is required because MITACS project search is dynamic.
- Vercel serverless is not used for scraping itself due browser/runtime limits; scraping runs in backend service (Render/Railway style).

## License

Educational and research use.
