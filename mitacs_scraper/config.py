"""
Project configuration constants and defaults.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_CSV = DATA_DIR / "mitacs_projects.csv"
OUTPUT_JSON = DATA_DIR / "mitacs_projects.json"
DB_PATH = DATA_DIR / "mitacs_projects.sqlite"

# Networking
USER_AGENT = "mitacs-scraper/0 (+https://example.com)"
RATE_LIMIT = 0.5  # seconds between requests by default
