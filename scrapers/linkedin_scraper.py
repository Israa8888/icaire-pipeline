"""
Scraper 1 — LinkedIn (linkedin-api, unofficial)
Searches for AI professionals in Saudi Arabia.
Rate-limited intentionally: 2–3 sec delay per call.
Use a secondary LinkedIn account, not your main one.
"""

import time
import random
import logging
from linkedin_api import Linkedin
from config.settings import LINKEDIN_EMAIL, LINKEDIN_PASSWORD, LINKEDIN_KEYWORDS

logger = logging.getLogger(__name__)


def fetch_linkedin_profiles(max_per_keyword: int = 50) -> list[dict]:
    """
    Search LinkedIn for AI professionals in Saudi Arabia.
    Returns a list of raw profile dicts.
    """
    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        logger.warning("LinkedIn credentials not set — skipping LinkedIn scrape.")
        return []

    try:
        api = Linkedin(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
        logger.info("LinkedIn login successful.")
    except Exception as e:
        logger.error(f"LinkedIn login failed: {e}")
        return []

    all_profiles = []
    seen_urns = set()

    for keyword in LINKEDIN_KEYWORDS:
        logger.info(f"Searching LinkedIn: '{keyword}' in Saudi Arabia...")
        try:
            results = api.search_people(
                keywords=keyword,
                regions=["sa:0"],          # Saudi Arabia region code
                limit=max_per_keyword,
            )
        except Exception as e:
            logger.error(f"Search failed for '{keyword}': {e}")
            time.sleep(5)
            continue

        for result in results:
            urn = result.get("urn_id") or result.get("public_id")
            if not urn or urn in seen_urns:
                continue
            seen_urns.add(urn)

            # Rate limit — be respectful, avoid account flag
            time.sleep(random.uniform(2.5, 4.0))

            try:
                profile = api.get_profile(urn)
                contact  = api.get_profile_contact_info(urn)
            except Exception as e:
                logger.warning(f"Could not fetch profile {urn}: {e}")
                continue

            record = _parse_profile(profile, contact)
            if record:
                all_profiles.append(record)
                logger.debug(f"  + {record['name']} @ {record['organization']}")

        # Pause between keyword searches
        time.sleep(random.uniform(8, 15))

    logger.info(f"LinkedIn: collected {len(all_profiles)} profiles.")
    return all_profiles


def _parse_profile(profile: dict, contact: dict) -> dict | None:
    first = profile.get("firstName", "")
    last  = profile.get("lastName", "")
    name  = f"{first} {last}".strip()
    if not name:
        return None

    # Get current position
    positions = profile.get("experience", [])
    title = org = ""
    if positions:
        current = positions[0]
        title = current.get("title", "")
        org   = current.get("companyName", "")

    # Location
    geo = profile.get("geoLocationName", "") or profile.get("locationName", "")
    city = _extract_city(geo)

    # LinkedIn public URL
    public_id = profile.get("public_id", "")
    linkedin_url = f"https://www.linkedin.com/in/{public_id}" if public_id else ""

    # Email from contact info
    emails = contact.get("email_address") or ""
    email  = emails if isinstance(emails, str) else ""

    return {
        "name":         name,
        "title":        title,
        "organization": org,
        "city":         city,
        "country":      "Saudi Arabia",
        "linkedin_url": linkedin_url,
        "email":        email,
        "source":       "linkedin",
    }


def _extract_city(geo_string: str) -> str:
    from config.settings import CITY_COORDINATES
    for city in CITY_COORDINATES:
        if city.lower() in geo_string.lower():
            return city
    if "Saudi Arabia" in geo_string or "KSA" in geo_string:
        return "Saudi Arabia"
    return geo_string.split(",")[0].strip() if geo_string else ""
