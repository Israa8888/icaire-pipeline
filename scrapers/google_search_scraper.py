"""
Scraper 3 — Apify LinkedIn Profile Search (discovery)
Finds industry + government Saudi AI professionals not in academic databases.
Actor: harvestapi/linkedin-profile-search
Actor ID: M2FMdjRVeF1HPGFcc

Cost: ~$0.004 per profile (Full mode)
Free credits: $5 on signup
"""

import requests, logging, time, os

logger    = logging.getLogger(__name__)
APIFY_KEY = os.getenv("APIFY_API_KEY", "")
BASE_URL  = "https://api.apify.com/v2"
ACTOR_ID  = "M2FMdjRVeF1HPGFcc"

# Targeted queries for Saudi AI professionals in industry/government
SEARCH_QUERIES = [
    "AI ethics Saudi Arabia",
    "responsible AI Riyadh",
    "machine learning engineer Saudi Arabia",
    "artificial intelligence SDAIA",
    "data scientist Saudi Arabia",
    "NLP Arabic Saudi Arabia",
    "computer vision Saudi Arabia",
    "AI engineer Riyadh",
    "deep learning Saudi Arabia",
    "AI governance Saudi Arabia",
]

MAX_PER_QUERY = 10  # keeps cost ~$0.40 per query


def fetch_google_profiles() -> list[dict]:
    if not APIFY_KEY:
        logger.warning("APIFY_API_KEY not set — skipping LinkedIn discovery.")
        return []

    all_records, seen_urls = [], set()

    for query in SEARCH_QUERIES:
        logger.info(f"Apify LinkedIn discovery: '{query}'...")
        records = _run_actor(query)
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


def _run_actor(query: str) -> list[dict]:
    try:
        run_resp = requests.post(
            f"{BASE_URL}/acts/{ACTOR_ID}/runs",
            headers={
                "Authorization": f"Bearer {APIFY_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "searchQuery":         query,
                "maxProfilesToScrape": MAX_PER_QUERY,
                "profileScraperMode":  "Short",
            },
            timeout=30,
        )
        run_resp.raise_for_status()
        data   = run_resp.json().get("data", {})
        run_id = data.get("id")
        if not run_id:
            return []

        # Wait for completion
        dataset_id = None
        for _ in range(30):
            time.sleep(10)
            status_resp = requests.get(
                f"{BASE_URL}/actor-runs/{run_id}",
                headers={"Authorization": f"Bearer {APIFY_KEY}"},
                timeout=15,
            )
            run_data   = status_resp.json().get("data", {})
            status     = run_data.get("status")
            if status == "SUCCEEDED":
                dataset_id = run_data.get("defaultDatasetId")
                break
            elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                logger.warning(f"  Actor run {status}")
                return []

        if not dataset_id:
            return []

        items_resp = requests.get(
            f"{BASE_URL}/datasets/{dataset_id}/items",
            headers={"Authorization": f"Bearer {APIFY_KEY}"},
            params={"format": "json"},
            timeout=20,
        )
        items_resp.raise_for_status()
        items = items_resp.json()
        logger.info(f"  Got {len(items)} profiles")

        records = []
        for item in items:
            record = _parse_profile(item)
            if record:
                records.append(record)
        return records

    except Exception as e:
        logger.warning(f"Apify actor failed for '{query}': {e}")
        return []


def _parse_profile(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None

    name = (item.get("name") or item.get("fullName") or "").strip()
    if not name or len(name) < 4:
        return None

    linkedin_url = (
        item.get("linkedinUrl") or
        item.get("linkedinProfileUrl") or
        item.get("profileUrl") or ""
    ).strip()

    title = (
        item.get("headline") or
        item.get("position") or
        item.get("title") or ""
    )
    if isinstance(title, dict):
        title = title.get("title", "")
    title = str(title).strip()[:150]

    location = item.get("location") or {}
    if isinstance(location, dict):
        city_text = location.get("linkedinText") or location.get("city") or ""
    else:
        city_text = str(location)

    # Filter — only Saudi-based people
    saudi_signals = [
        "saudi", "ksa", "riyadh", "jeddah", "mecca", "medina",
        "dammam", "dhahran", "thuwal", "abha", "tabuk", "hail",
        "jubail", "yanbu", "khobar", "hofuf", "taif", "buraidah",
        "kingdom of saudi", "المملكة", "الرياض", "جدة", "مكة",
    ]
    if not any(s in city_text.lower() for s in saudi_signals):
        return None

    # Extract org from experience
    org = ""
    experience = item.get("experience") or item.get("positions") or []
    if isinstance(experience, list) and experience:
        current = experience[0]
        if isinstance(current, dict):
            org = (current.get("companyName") or
                   current.get("company") or "")
            if isinstance(org, dict):
                org = org.get("name", "")

    # Fallback: extract from title
    if not org:
        if " at " in title:
            org = title.split(" at ")[-1].strip()[:80]
        elif " @ " in title:
            org = title.split(" @ ")[-1].strip()[:80]

    city = city_text.split(",")[0].strip() or "Saudi Arabia"

    return {
        "name":         name,
        "title":        title,
        "organization": org,
        "city":         city,
        "country":      "Saudi Arabia",
        "linkedin_url": linkedin_url,
        "source":       "apify_linkedin",
    }
