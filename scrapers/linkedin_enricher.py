"""
LinkedIn Enricher — uses Apify to enrich existing records with LinkedIn data.
Actor: harvestapi/linkedin-profile-search (regular profiles, not services)
Actor ID: M2FMdjRVeF1HPGFcc (from URL console.apify.com/actors/M2FMdjRVeF1HPGFcc)

For each person already in our list:
  Search LinkedIn by "Name Organization"
  Get back: real title, LinkedIn URL, current company, summary, experience
  Add to existing record without overwriting manual fields.

Cost: ~$0.004 per profile (Full mode) x 957 = ~$3.83 from $5 credit
"""

import requests, logging, time, os, json

logger       = logging.getLogger(__name__)
APIFY_KEY    = os.getenv("APIFY_API_KEY", "")
BASE_URL     = "https://api.apify.com/v2"
ACTOR_ID     = "M2FMdjRVeF1HPGFcc"  # harvestapi/linkedin-profile-search


def enrich_with_linkedin(records: list[dict], max_enriched: int = 500) -> list[dict]:
    """
    Enriches records with LinkedIn profile data.
    Only enriches records missing LinkedIn URL.
    Stops after max_enriched to control cost.
    """
    if not APIFY_KEY:
        logger.warning("APIFY_API_KEY not set — skipping LinkedIn enrichment.")
        return records

    enriched_count = 0
    result = []

    for record in records:
        # Skip if already has LinkedIn URL
        if record.get("linkedin_url"):
            result.append(record)
            continue

        # Skip if we've hit our limit
        if enriched_count >= max_enriched:
            result.append(record)
            continue

        name = record.get("name", "").strip()
        org  = record.get("organization", "").strip()
        if not name:
            result.append(record)
            continue

        # Search LinkedIn for this person
        search_query = f"{name} {org}".strip()
        logger.info(f"LinkedIn enrichment: {search_query}...")

        profile = _search_person(search_query)
        if profile:
            enriched = _merge_linkedin_data(record, profile)
            result.append(enriched)
            enriched_count += 1
            logger.debug(f"  ✓ Found: {profile.get('linkedin_url','')}")
        else:
            result.append(record)

        time.sleep(1)  # polite delay

    logger.info(f"LinkedIn enrichment: {enriched_count} records enriched.")
    return result


def _search_person(query: str) -> dict | None:
    """Search LinkedIn for a specific person and return their profile data."""
    try:
        # Start actor run
        run_resp = requests.post(
            f"{BASE_URL}/acts/{ACTOR_ID}/runs",
            headers={
                "Authorization": f"Bearer {APIFY_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "searchQuery":        query,
                "maxProfilesToScrape": 1,  # only need top result
                "profileScraperMode": "Full",
            },
            timeout=30,
        )
        run_resp.raise_for_status()
        run_id = run_resp.json().get("data", {}).get("id")
        if not run_id:
            return None

        # Wait for completion
        dataset_id = None
        for _ in range(24):  # wait up to 4 minutes
            time.sleep(10)
            status_resp = requests.get(
                f"{BASE_URL}/actor-runs/{run_id}",
                headers={"Authorization": f"Bearer {APIFY_KEY}"},
                timeout=15,
            )
            data   = status_resp.json().get("data", {})
            status = data.get("status")
            if status == "SUCCEEDED":
                dataset_id = data.get("defaultDatasetId")
                break
            elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                return None

        if not dataset_id:
            return None

        # Fetch result
        items_resp = requests.get(
            f"{BASE_URL}/datasets/{dataset_id}/items",
            headers={"Authorization": f"Bearer {APIFY_KEY}"},
            params={"format": "json"},
            timeout=20,
        )
        items_resp.raise_for_status()
        items = items_resp.json()

        if not items:
            return None

        return _parse_full_profile(items[0])

    except Exception as e:
        logger.warning(f"LinkedIn search failed for '{query}': {e}")
        return None


def _parse_full_profile(item: dict) -> dict | None:
    """Parse full LinkedIn profile — extract all useful fields."""
    if not isinstance(item, dict):
        return None

    name = (item.get("name") or item.get("fullName") or "").strip()
    if not name:
        return None

    # LinkedIn URL
    linkedin_url = (
        item.get("linkedinUrl") or
        item.get("linkedinProfileUrl") or
        item.get("profileUrl") or ""
    ).strip()

    # Title — current position
    title = (
        item.get("headline") or
        item.get("title") or
        item.get("position") or ""
    )
    if isinstance(title, dict):
        title = title.get("title", "")
    title = str(title).strip()[:150]

    # Location
    location = item.get("location") or {}
    if isinstance(location, dict):
        city = location.get("linkedinText") or location.get("city") or ""
    else:
        city = str(location)
    city = city.split(",")[0].strip()

    # Summary / about
    summary = (item.get("summary") or item.get("about") or "")[:500]

    # Current company from experience
    org = ""
    experience = item.get("experience") or item.get("positions") or []
    if isinstance(experience, list) and experience:
        current = experience[0]
        if isinstance(current, dict):
            org = (
                current.get("companyName") or
                current.get("company") or
                current.get("organisation") or ""
            )
            if isinstance(org, dict):
                org = org.get("name", "")
            # Get real title from experience if headline is generic
            if not title:
                title = current.get("title") or current.get("position") or ""

    # Degree from education
    degree = ""
    education = item.get("education") or []
    if isinstance(education, list) and education:
        for edu in education:
            if isinstance(edu, dict):
                field = (edu.get("degreeName") or edu.get("degree") or "").lower()
                if "phd" in field or "doctor" in field:
                    degree = "PhD"; break
                elif "master" in field or "msc" in field or "mba" in field:
                    degree = "MSc"
                elif "bachelor" in field or "bsc" in field or "beng" in field:
                    if not degree:
                        degree = "BSc"

    # Skills
    skills = item.get("skills") or []
    if isinstance(skills, list):
        skill_names = [
            s.get("name") if isinstance(s, dict) else str(s)
            for s in skills[:10]
        ]
        skills_str = ", ".join(s for s in skill_names if s)
    else:
        skills_str = ""

    # Connections count
    connections = item.get("connectionsCount") or item.get("connections") or ""

    return {
        "linkedin_url":   linkedin_url,
        "title":          title,
        "organization":   org,
        "city":           city,
        "summary":        summary,
        "degree":         degree,
        "linkedin_skills":skills_str,
        "connections":    str(connections),
    }


def _merge_linkedin_data(record: dict, linkedin: dict) -> dict:
    """
    Merge LinkedIn data into existing record.
    Rules:
    - LinkedIn URL: always add if found
    - Title: only fill if current is generic "Researcher"
    - Org: only fill if empty
    - City: only fill if currently "Saudi Arabia" (too generic)
    - Degree: only fill if empty
    - Never overwrite manual fields
    """
    merged = dict(record)
    MANUAL_FIELDS = {"connection_status","connection_type","outreach_notes","meeting_done"}

    # Always add LinkedIn URL
    if linkedin.get("linkedin_url") and not merged.get("linkedin_url"):
        merged["linkedin_url"] = linkedin["linkedin_url"]

    # Title — replace generic "Researcher" with real title
    if linkedin.get("title") and (not merged.get("title") or
                                   merged.get("title") == "Researcher"):
        merged["title"] = linkedin["title"]

    # Organization — fill if empty
    if linkedin.get("organization") and not merged.get("organization"):
        merged["organization"] = linkedin["organization"]

    # City — fill if too generic
    if linkedin.get("city") and merged.get("city") in ["Saudi Arabia", "", None]:
        merged["city"] = linkedin["city"]

    # Degree — fill if empty
    if linkedin.get("degree") and not merged.get("degree"):
        merged["degree"] = linkedin["degree"]

    # Add LinkedIn-specific fields
    if linkedin.get("summary"):
        merged["linkedin_summary"] = linkedin["summary"]
    if linkedin.get("linkedin_skills"):
        merged["linkedin_skills"] = linkedin["linkedin_skills"]
    if linkedin.get("connections"):
        merged["connections"] = linkedin["connections"]

    return merged
