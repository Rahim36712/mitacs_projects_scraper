"""
Fetcher adapters for mitacs_scraper.
Provides a safe wrapper around requests and (optionally) Scrapling fetchers.
The code intentionally avoids failing hard if Scrapling is not installed — it will fall back to requests.
"""
from typing import Tuple, Optional
import time
import logging

try:
    # Scrapling imports are optional — use them when available
    from scrapling.fetchers import DynamicFetcher, StealthyFetcher  # type: ignore
    HAS_SCRAPLING = True
except Exception:
    HAS_SCRAPLING = False

import requests

logger = logging.getLogger(__name__)


class FetchResult:
    def __init__(self, url: str, text: str, headers: dict):
        self.url = url
        self.text = text
        self.headers = headers


class Fetcher:
    def __init__(self, user_agent: str = None, rate_limit: float = 0.5):
        self.user_agent = user_agent or "mitacs-scraper/0 (+https://example.com)"
        self.rate_limit = rate_limit
        self._last_request = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

    def fetch(self, url: str, use_dynamic: bool = False, timeout: int = 15) -> FetchResult:
        """
        Fetch a URL and return a FetchResult.
        If use_dynamic=True and Scrapling is available, attempt a DynamicFetcher-based render.
        Falls back to requests otherwise.
        """
        self._throttle()
        headers = {"User-Agent": self.user_agent}

        if use_dynamic and HAS_SCRAPLING:
            try:
                logger.debug("Using Scrapling DynamicFetcher.fetch for %s", url)
                # Scrapling's DynamicFetcher provides a classmethod `fetch` which launches a browser
                # and returns a Response-like object. Pass sensible defaults for DOM loading and waits.
                rendered = DynamicFetcher.fetch(
                    url,
                    headless=True,
                    load_dom=True,
                    network_idle=True,
                    timeout=30000,  # milliseconds
                    wait=500,
                )
                # Response may expose `text` or `content`/`body`. Fallback to str(rendered).
                text = getattr(rendered, "text", None) or getattr(rendered, "content", None) or str(rendered)
                self._last_request = time.time()
                # Some Response-like objects expose headers and url
                headers = getattr(rendered, "headers", {})
                try:
                    resp_url = getattr(rendered, "url", url)
                except Exception:
                    resp_url = url
                return FetchResult(url=resp_url, text=text, headers=headers)
            except Exception as e:
                logger.warning("Dynamic fetch failed for %s: %s — falling back to requests", url, e)

        # Fallback: plain requests
        resp = requests.get(url, headers=headers, timeout=timeout)
        self._last_request = time.time()
        resp.raise_for_status()
        return FetchResult(url=resp.url, text=resp.text, headers=resp.headers)

    def capture_xhr(self, url: str, timeout: int = 20) -> list:
        """
        Placeholder for XHR capture. When Scrapling or other tooling is available, implement
        a capture that records backend API calls executed while rendering the page.
        Returns a list of discovered request URLs (may be empty).
        """
        if not HAS_SCRAPLING:
            logger.debug("XHR capture requested but Scrapling not available")
            return []
        try:
            # Hypothetical API; real code depends on Scrapling version
            df = DynamicFetcher()
            captures = df.capture_xhr(url, timeout=timeout)
            return captures
        except Exception:
            logger.exception("XHR capture failed")
            return []
