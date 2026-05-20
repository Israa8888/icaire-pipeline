"""
Scraper 3 — Google Custom Search API
Finds LinkedIn profiles of AI professionals in Saudi Arabia.
Legal: searches Google's public index, not LinkedIn directly.
Free tier: 100 queries/day = ~1,000 profiles.
Claude filters who is ethical AI relevant.
"""

import requests, logging, time, re
from config.settings import GOOGLE_CSE_API_KEY, GOOGLE_CSE_CX, GOOGLE_SEARCH_QUERIES

logger = logging.getLogger(__name__)
BASE   = "https://www.googleapis.com/customsearch/v1"


def fetch_google_profiles() -> list[dict]:
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_CX:
        logger.warning("Google CSE credentials not set — skipping Google search.")
        return []

    all_records, seen_urls = [], set()
    queries_used = 0

    for query in GOOGLE_SEARCH_QUERIES:
        if queries_used >= 90:   # stay under free tier limit
            logger.info("Google CSE: approaching daily limit, stopping.")
            break

        logger.info(f"Google CSE: {query[:70]}...")

        # Paginate — each page = 10 results, max 10 pages per query
        for start in range(1, 51, 10):
            if queries_used >= 90: break
            try:
                r = requests.get(BASE, timeout=15, params={
                    "key":   GOOGLE_CSE_API_KEY,
                    "cx":    GOOGLE_CSE_CX,
                    "q":     query,
                    "start": start,
                    "num":   10,
                })
                queries_used += 1

                if r.status_code == 429:
                    logger.warning("Google CSE rate limited — waiting 60s")
                    time.sleep(60); continue

                r.raise_for_status()
                items = r.json().get("items", [])
                if not items: break

                for item in items:
                    record = _parse_result(item)
                    if not record: continue
                    url = record.get("linkedin_url","")
                    if url and url in seen_urls: continue
                    if url: seen_urls.add(url)
                    all_records.append(record)

                time.sleep(1)   # polite delay between pages

            except Exception as e:
                logger.warning(f"Google CSE error: {e}"); break

        time.sleep(2)   # between queries

    logger.info(f"Google CSE: {len(all_records)} profiles collected "
                f"({queries_used} queries used).")
    return all_records


def _parse_result(item: dict) -> dict | None:
    link    = item.get("link","")
    title   = item.get("title","")
    snippet = item.get("snippet","")

    # Must be a LinkedIn profile URL
    if "linkedin.com/in/" not in link: return None

    # Clean LinkedIn URL — remove query params
    linkedin_url = re.sub(r'\?.*$','', link).rstrip('/')

    # Extract name from title (format: "Name - Title | LinkedIn" or "Name | LinkedIn")
    name = _extract_name(title)
    if not name: return None

    # Extract title/role from snippet or page title
    role = _extract_role(title, snippet)

    # Extract location signals
    city = _extract_city(snippet)

    # Extract org signals
    org  = _extract_org(snippet + " " + title)

    return {
        "name":         name,
        "title":        role,
        "organization": org,
        "city":         city,
        "country":      "Saudi Arabia",
        "linkedin_url": linkedin_url,
        "source":       "google_linkedin",
        # Claude will classify UNESCO domain / ethical AI relevance
    }


def _extract_name(title: str) -> str:
    # "First Last - Title at Company | LinkedIn"
    # "First Last | LinkedIn"
    parts = title.split(" - ")
    if parts:
        name = parts[0].replace("| LinkedIn","").strip()
        # Basic sanity: name should have at least 2 words, no special chars
        words = name.split()
        if 2 <= len(words) <= 5 and all(w[0].isalpha() for w in words if w):
            return name
    return ""


def _extract_role(title: str, snippet: str) -> str:
    # Title format: "Name - ROLE at Company | LinkedIn"
    if " - " in title and " at " in title:
        role_part = title.split(" - ")[1].split(" at ")[0].strip()
        if len(role_part) < 80:
            return role_part
    # Fall back to first sentence of snippet
    first_sentence = snippet.split(".")[0].strip()
    return first_sentence[:100] if first_sentence else ""


def _extract_city(text: str) -> str:
    from config.settings import CITY_COORDINATES
    low = text.lower()
    for city in CITY_COORDINATES:
        if city.lower() in low:
            return city
    if "saudi" in low or "ksa" in low:
        return "Saudi Arabia"
    return ""


def _extract_org(text: str) -> str:
    from config.settings import TARGET_INSTITUTIONS
    low = text.lower()
    org_map = {
        "kaust":"KAUST","king abdullah university":"KAUST",
        "sdaia":"SDAIA","kacst":"KACST",
        "king abdulaziz university":"KAU","king saud university":"KSU",
        "kfupm":"KFUPM","king fahd university":"KFUPM",
        "aramco":"Saudi Aramco","elm company":"Elm","mozn":"Mozn",
        "imam university":"Imam University","alfaisal":"Alfaisal University",
    }
    for key, val in org_map.items():
        if key in low: return val
    return ""
