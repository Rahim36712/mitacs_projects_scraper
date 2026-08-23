"""
High-level spider orchestration. This is a small, testable orchestration that will be
expanded after discovery identifies the canonical list pages / API endpoints.
"""
from typing import Iterable, List
import logging
from .discovery import discover_list_page
from .fetcher import Fetcher
from .parser import parse_project_from_html

logger = logging.getLogger(__name__)


class Spider:
    def __init__(self, rate_limit: float = 0.5):
        self.fetcher = Fetcher(rate_limit=rate_limit)

    def run_discovery(self, url: str, use_dynamic_probe: bool = False) -> dict:
        return discover_list_page(url, use_dynamic_probe=use_dynamic_probe)

    def crawl_sample(self, url: str, sample_limit: int = 5) -> List[dict]:
        """
        Fetch the provided URL, find a few links to project pages, and parse them.
        This method uses naive heuristics — refine after discovery.
        """
        res = self.fetcher.fetch(url)
        html = res.text
        # find candidate links
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        links = [a.get('href') for a in soup.find_all('a', href=True)]
        # Naive filter: keep ones containing 'project' or '/projects/'
        candidates = [l for l in links if l and ('project' in l.lower() or '/projects/' in l.lower())]
        results = []
        for link in candidates[:sample_limit]:
            if not link.startswith('http'):
                # relative
                from urllib.parse import urljoin
                link = urljoin(url, link)
            try:
                logger.info('Fetching candidate %s', link)
                fetched = self.fetcher.fetch(link)
                record = parse_project_from_html(fetched.text, fetched.url)
                results.append(record)
            except Exception:
                logger.exception('Failed to fetch/parse %s', link)
        return results
