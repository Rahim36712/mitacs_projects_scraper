"""
Discovery helpers to inspect MITACS project listing pages and identify API endpoints, pagination,
and whether pages require JavaScript rendering.
"""
from typing import Dict, Any, List
import re
import logging
from .fetcher import Fetcher

logger = logging.getLogger(__name__)


API_CANDIDATE_RE = re.compile(r"/api/|/projects/|/search|\bfetch\(|XMLHttpRequest", re.I)
URL_RE = re.compile(r"https?://[\w\-\./?=&%]+", re.I)


def analyze_html_for_api(html: str) -> Dict[str, Any]:
    """Return heuristics about whether the page embeds API calls or JSON payloads."""
    flags: Dict[str, Any] = {
        "has_api_candidate": False,
        "found_endpoints": [],
        "likely_json_inline": False,
        "has_script_tags": False,
    }
    if not html:
        return flags

    if "<script" in html.lower():
        flags["has_script_tags"] = True

    # Heuristic: inline JSON blobs (window.__INITIAL_STATE__ or similar)
    if re.search(r"window\.__INITIAL_STATE__|window\.__DATA__|__INITIAL_DATA__", html):
        flags["likely_json_inline"] = True

    matches = API_CANDIDATE_RE.findall(html)
    if matches:
        flags["has_api_candidate"] = True

    # Try to extract obvious URLs from script tags
    found_urls = URL_RE.findall(html)
    # Filter and keep short unique candidates
    candidates = [u for u in found_urls if "/api/" in u or "/projects/" in u or "search" in u]
    flags["found_endpoints"] = sorted(set(candidates))[:10]
    return flags


def discover_list_page(url: str, use_dynamic_probe: bool = False) -> Dict[str, Any]:
    """Fetch a page and return discovery info (heuristics + optional XHR capture).

    This function purposely stays conservative: it will not execute full browser rendering
    unless explicitly asked via use_dynamic_probe.
    """
    f = Fetcher()
    result = {"url": url, "ok": False, "status": None, "analysis": {}, "xhr_calls": []}
    try:
        resp = f.fetch(url, use_dynamic=False)
        result["ok"] = True
        result["status"] = 200
        analysis = analyze_html_for_api(resp.text)
        result["analysis"] = analysis

        if use_dynamic_probe:
            # capture XHRs if requested and if supported by fetcher
            xhrs = f.capture_xhr(url)
            result["xhr_calls"] = xhrs
    except Exception as e:
        logger.exception("Discovery failed for %s: %s", url, e)
        result["ok"] = False
        result["status"] = getattr(e, "response", None)
    return result
