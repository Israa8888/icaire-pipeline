"""
Scraper 4 — University / org faculty page scraper (BeautifulSoup)
Targets: KAUST, KAU, KSU, KFUPM, KACST, SDAIA faculty pages.
"""

import requests
import logging
import time
from bs4 import BeautifulSoup
from config.settings import FACULTY_PAGES

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

AI_KEYWORDS = [
    "artificial intelligence", "machine learning", "deep learning",
    "natural language", "computer vision", "neural network",
    "data science", "nlp", "reinforcement learning", "ai",
    "robotics", "cognitive", "intelligent systems",
]


def fetch_faculty_profiles() -> list[dict]:
    all_records = []

    for institution, urls in FACULTY_PAGES.items():
        for url in urls:
            logger.info(f"Scraping {institution}: {url}")
            records = _scrape_page(url, institution)
            all_records.extend(records)
            time.sleep(3)   # polite delay between pages

    logger.info(f"Web scraper: collected {len(all_records)} profiles.")
    return all_records


def _scrape_page(url: str, institution: str) -> list[dict]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    records = []

    # Strategy: find elements that look like person cards
    # Common patterns across university sites
    candidates = (
        soup.select(".faculty-member, .person-card, .staff-card, "
                    ".team-member, .profile-card, .faculty-item") or
        soup.select("[class*='faculty'], [class*='person'], [class*='staff']") or
        soup.select("article, .card")
    )

    if not candidates:
        # Fallback: parse any <h2>/<h3> that look like names
        candidates = soup.find_all(["h2", "h3", "h4"])

    for el in candidates:
        text = el.get_text(" ", strip=True)
        if not _is_ai_related(text):
            continue

        name  = _extract_name(el, text)
        title = _extract_title(el, text)

        if not name or len(name) < 4:
            continue

        records.append({
            "name":         name,
            "title":        title,
            "organization": institution,
            "city":         _inst_to_city(institution),
            "country":      "Saudi Arabia",
            "source":       "web_scrape",
            "sector":       "academia",
        })

    return records


def _is_ai_related(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in AI_KEYWORDS)


def _extract_name(el, text: str) -> str:
    # Try heading tags first
    for tag in ["h2", "h3", "h4", "h5"]:
        heading = el.find(tag)
        if heading:
            return heading.get_text(strip=True)
    # Try common name class patterns
    for cls in ["name", "title", "person-name", "faculty-name"]:
        node = el.find(class_=lambda c: c and cls in c.lower())
        if node:
            return node.get_text(strip=True)
    # Return first 40 chars of text as last resort
    return text[:40].split("\n")[0].strip()


def _extract_title(el, text: str) -> str:
    for cls in ["role", "position", "designation", "job-title", "title"]:
        node = el.find(class_=lambda c: c and cls in c.lower())
        if node:
            return node.get_text(strip=True)
    # Look for common academic titles in text
    for keyword in ["Professor", "Associate Prof", "Assistant Prof",
                    "Researcher", "Lecturer", "Director", "Head"]:
        if keyword.lower() in text.lower():
            return keyword
    return ""


def _inst_to_city(institution: str) -> str:
    return {
        "KAUST":  "Thuwal",
        "KAU":    "Jeddah",
        "KSU":    "Riyadh",
        "KFUPM":  "Dhahran",
        "KACST":  "Riyadh",
        "SDAIA":  "Riyadh",
    }.get(institution, "Saudi Arabia")
