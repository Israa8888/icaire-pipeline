"""
Scraper 3 — Apify LinkedIn Profile Search
Actor: harvestapi/linkedin-profile-search
Searches LinkedIn for Saudi AI professionals.
Free credits: $5 on signup (~500 profiles).
"""

import requests, logging, time, os

logger = logging.getLogger(__name__)

APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")
ACTOR_ID      = "harvestapi~linkedin-profile-search"
BASE_URL      = "https://api.apify.com/v2"

# Search queries targeting Saudi AI/ethical AI professionals
SEARCH_QUERIES = [
    {"query": "AI ethics Saudi Arabia",          "location": "Saudi Arabia"},
    {"query": "responsible AI Riyadh",           "location": "Saudi Arabia"},
    {"query": "machine learning KAUST",          "location": "Saudi Arabia"},
    {"query": "artificial intelligence SDAIA",   "location": "Saudi Arabia"},
    {"query": "data scientist Riyadh",           "location": "Saudi Arabia"},
    {"query": "NLP Arabic language model",       "location": "Saudi Arabia"},
    {"query": "computer vision Saudi Arabia",    "location": "Saudi Arabia"},
    {"query": "AI engineer Riyadh",              "location": "Saudi Arabia"},
    {"query": "algorithmic fairness Saudi",      "location": "Saudi Arabia"},
    {"query": "AI governance Saudi Arabia",      "location": "Saudi Arabia"},
]

MAX_PROFILES_PER_QUERY = 20  # keeps cost low during testing


def fetch_google_profiles() -> list[dict]:
    if not APIFY_API_KEY:
        logger.warning("APIFY_API_KEY not set — skipping LinkedIn search.")
        return []

    all_records = []
    seen_urls   = set()

    for search in SEARCH_QUERIES:
        query    = search["query"]
        location = search["location"]
        logger.info(f"Apify LinkedIn: '{query}'...")

        records = _run_actor(query, location)
        for r in records:
            url = r.get("linkedin_url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            all_records.append(r)

        time.sleep(2)

    logger.info(f"Apify LinkedIn: {len(all_records)} profiles collected.")
    return all_records


def _run_actor(query: str, location: str) -> list[dict]:
    """Run the Apify actor and wait for results."""
    try:
        # Start the actor run
        run_resp = requests.post(
            f"{BASE_URL}/acts/{ACTOR_ID}/runs",
            headers={"Authorization": f"Bearer {APIFY_API_KEY}"},
            json={
                "searchQuery":   query,
                "location":      location,
                "maxProfiles":   MAX_PROFILES_PER_QUERY,
                "scrapeMode":    "fast",  # cheaper — gets name, title, URL, location
            },
            timeout=30,
        )
        run_resp.raise_for_status()
        run_id = run_resp.json().get("data", {}).get("id")
        if not run_id:
            logger.warning(f"No run ID returned for '{query}'")
            return []

        # Wait for run to complete
        logger.info(f"  Run started: {run_id} — waiting...")
        for _ in range(30):  # wait up to 5 minutes
            time.sleep(10)
            status_resp = requests.get(
                f"{BASE_URL}/actor-runs/{run_id}",
                headers={"Authorization": f"Bearer {APIFY_API_KEY}"},
                timeout=15,
            )
            status = status_resp.json().get("data", {}).get("status")
            if status == "SUCCEEDED":
                break
            elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                logger.warning(f"  Run failed with status: {status}")
                return []

        # Fetch results from dataset
        dataset_id = status_resp.json().get("data", {}).get("defaultDatasetId")
        if not dataset_id:
            return []

        results_resp = requests.get(
            f"{BASE_URL}/datasets/{dataset_id}/items",
            headers={"Authorization": f"Bearer {APIFY_API_KEY}"},
            params={"clean": True, "format": "json"},
            timeout=30,
        )
        results_resp.raise_for_status()
        items = results_resp.json()

        records = []
        for item in items:
            record = _parse_item(item)
            if record:
                records.append(record)

        logger.info(f"  Got {len(records)} profiles")
        return records

    except Exception as e:
        logger.warning(f"Apify actor failed for '{query}': {e}")
        return []


def _parse_item(item: dict) -> dict | None:
    name = (item.get("name") or item.get("fullName") or "").strip()
    if not name or len(name) < 4:
        return None

    linkedin_url = (item.get("linkedinUrl") or item.get("url") or "").strip()
    title        = (item.get("headline") or item.get("title") or "").strip()
    location     = (item.get("location") or "").strip()
    org          = (item.get("currentCompany") or
                    item.get("company") or "").strip()

    return {
        "name":         name,
        "title":        title[:100] if title else "",
        "organization": _norm_org(org),
        "city":         _extract_city(location),
        "country":      "Saudi Arabia",
        "linkedin_url": linkedin_url,
        "source":       "apify_linkedin",
    }


def _norm_org(raw: str) -> str:
    if not raw:
        return ""
    m = {
        "king abdullah university": "KAUST", "kaust": "KAUST",
        "sdaia": "SDAIA", "kacst": "KACST",
        "king abdulaziz university": "KAU",
        "king saud university": "KSU",
        "kfupm": "KFUPM", "king fahd": "KFUPM",
        "aramco": "Saudi Aramco", "elm": "Elm", "mozn": "Mozn",
        "alfaisal": "Alfaisal University",
        "imam": "Imam University",
    }
    low = raw.lower()
    for k, v in m.items():
        if k in low:
            return v
    return raw


def _extract_city(location: str) -> str:
    cities = ["Riyadh", "Jeddah", "Thuwal", "Dhahran", "Dammam", "Abha", "Medina"]
    low = location.lower()
    for city in cities:
        if city.lower() in low:
            return city
    return "Saudi Arabia"
