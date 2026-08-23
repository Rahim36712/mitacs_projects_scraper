"""
Parser utilities to extract canonical project fields from HTML or JSON payloads.
Keep parsing resilient: return a dict with known keys, using None for missing values.
"""
from typing import Dict, Optional
from bs4 import BeautifulSoup
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def clean_text(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return " ".join(s.split()).strip()


def parse_project_from_html(html: str, url: str) -> Dict[str, Optional[str]]:
    """Attempt to extract common fields from a project page HTML.
    This is intentionally conservative and will be adjusted after a real discovery step.
    """
    soup = BeautifulSoup(html or "", "lxml")

    # Heuristics — common patterns
    title = None
    h1 = soup.find("h1")
    if h1:
        title = clean_text(h1.get_text())
    if not title:
        # fallback to title tag
        if soup.title:
            title = clean_text(soup.title.get_text())

    # description: try meta description then a main article element
    description = None
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = clean_text(meta_desc.get("content"))
    else:
        # look for common container
        article = soup.find("article") or soup.find(role="main") or soup.find("div", class_=lambda x: x and "description" in x.lower())
        if article:
            description = clean_text(article.get_text())

    # Try to locate university / host
    uni = None
    prov = None
    # Generic keyword searches
    text = soup.get_text(separator=" \n ")
    # Very naive — refine after discovery
    if "University" in text:
        uni = "(contains 'University' in text)"

    record = {
        "project_id": None,
        "title": title,
        "description": description,
        "university": uni,
        "province": prov,
        "supervisor": None,
        "discipline": None,
        "preferred_background": None,
        "skills": None,
        "language": None,
        "url": url,
        "metadata": None,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
    }
    return record


def parse_project_from_json(payload: dict, url: str) -> Dict[str, Optional[str]]:
    """Convert an API JSON payload into the canonical record shape.
    This function should be adapted when the real API schema is known.
    """
    record = {
        "project_id": payload.get("id") or payload.get("project_id"),
        "title": payload.get("title") or payload.get("name"),
        "description": payload.get("description"),
        "university": payload.get("institution") or payload.get("university"),
        "province": payload.get("province"),
        "supervisor": payload.get("supervisor") or payload.get("contact"),
        "discipline": payload.get("discipline"),
        "preferred_background": payload.get("preferred_background"),
        "skills": payload.get("skills"),
        "language": payload.get("language"),
        "url": url,
        "metadata": None,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
    }
    return record
