"""
Scraper 2 — ORCID Public API (free, no key needed)
Fixed: simpler query syntax, no nested OR inside AND
ORCID search uses Lucene but has limits on query complexity.
"""

import requests
import logging
import time

logger  = logging.getLogger(__name__)
BASE_URL = "https://pub.orcid.org/v3.0"
HEADERS  = {
    "Accept":     "application/json",
    "User-Agent": "ICAIRE-Pipeline/1.0 (mailto:info@icaire.org)",
}

# Simple queries — one institution per query, no nested OR
# ORCID handles simple affiliation searches reliably
ORCID_QUERIES = [
    'affiliation-org-name:KAUST',
    'affiliation-org-name:"King Abdullah University"',
    'affiliation-org-name:"King Abdulaziz University"',
    'affiliation-org-name:"King Saud University"',
    'affiliation-org-name:KFUPM',
    'affiliation-org-name:"King Fahd University of Petroleum"',
    'affiliation-org-name:KACST',
    'affiliation-org-name:"King Abdulaziz City for Science"',
    'affiliation-org-name:SDAIA',
    'affiliation-org-name:"Imam Muhammad ibn Saud"',
    'affiliation-org-name:"Alfaisal University"',
    'affiliation-org-name:"Princess Nourah"',
    'affiliation-org-name:"Saudi Aramco"',
]

ORG_MAP = {
    "king abdullah university": "KAUST",
    "kaust":                    "KAUST",
    "king abdulaziz university":"KAU",
    "king saud university":     "KSU",
    "king fahd university":     "KFUPM",
    "kfupm":                    "KFUPM",
    "king abdulaziz city":      "KACST",
    "kacst":                    "KACST",
    "saudi data":               "SDAIA",
    "sdaia":                    "SDAIA",
    "imam muhammad":            "Imam University",
    "imam mohammed":            "Imam University",
    "alfaisal":                 "Alfaisal University",
    "princess nourah":          "Princess Nourah University",
    "aramco":                   "Saudi Aramco",
}


def fetch_orcid_profiles() -> list[dict]:
    all_records = []
    seen_orcids = set()

    for query in ORCID_QUERIES:
        logger.info(f"ORCID: {query}")
        try:
            resp = requests.get(
                f"{BASE_URL}/search/",
                params={"q": query, "rows": 50, "start": 0},
                headers=HEADERS,
                timeout=20,
            )
            if resp.status_code == 500:
                # Try even simpler version
                simple = query.split(":")[1].replace('"', '').split()[0]
                resp = requests.get(
                    f"{BASE_URL}/search/",
                    params={"q": simple, "rows": 20, "start": 0},
                    headers=HEADERS,
                    timeout=20,
                )

            resp.raise_for_status()
            results = resp.json().get("result", []) or []
            logger.info(f"  Found {len(results)} ORCID profiles")

            for item in results:
                orcid_id = item.get("orcid-identifier", {}).get("path", "")
                if not orcid_id or orcid_id in seen_orcids:
                    continue
                seen_orcids.add(orcid_id)

                time.sleep(0.5)
                record = _fetch_profile(orcid_id)
                if record and is_ai_relevant(record):
                    all_records.append(record)
                    logger.debug(f"  + {record['name']} @ {record['organization']}")

        except Exception as e:
            logger.warning(f"ORCID search failed for '{query}': {e}")

        time.sleep(2)

    logger.info(f"ORCID: collected {len(all_records)} profiles.")
    return all_records


def _fetch_profile(orcid_id: str) -> dict | None:
    try:
        resp = requests.get(
            f"{BASE_URL}/{orcid_id}/record",
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"ORCID profile fetch failed for {orcid_id}: {e}")
        return None

    # Name
    name_data = data.get("person", {}).get("name") or {}
    given     = (name_data.get("given-names") or {}).get("value", "")
    family    = (name_data.get("family-name") or {}).get("value", "")
    name      = f"{given} {family}".strip()
    if not name:
        return None

    # Email
    emails = data.get("person", {}).get("emails", {}).get("email", [])
    email  = emails[0].get("email", "") if emails else ""

    # Current employment
    org = title = city = ""
    employments = (
        data.get("activities-summary", {})
            .get("employments", {})
            .get("affiliation-group", [])
    )
    for emp_group in employments:
        for s in emp_group.get("summaries", []):
            emp      = s.get("employment-summary", {})
            end_date = emp.get("end-date")
            if end_date:
                continue
            org_data = emp.get("organization", {})
            org      = org_data.get("name", "")
            title    = (emp.get("role-title") or "").strip()
            address  = org_data.get("address", {})
            city     = address.get("city", "")
            if org:
                break
        if org:
            break

    # Works count
    works       = data.get("activities-summary", {}).get("works", {})
    works_count = len(works.get("group", [])) if works else 0

    normalised_org = _normalise_org(org)

    # Only keep if Saudi-affiliated
    if org and not _is_saudi_org(org):
        return None

    return {
        "name":         name,
        "title":        title or "Researcher",
        "organization": normalised_org or "Saudi Arabia",
        "city":         _org_to_city(normalised_org) or city,
        "country":      "Saudi Arabia",
        "email":        email,
        "orcid":        orcid_id,
        "publications": works_count,
        "sector":       "academia",
        "source":       "orcid",
    }


def _is_saudi_org(org: str) -> bool:
    signals = ["saudi", "kaust", "kacst", "kau", "ksu", "kfupm",
               "sdaia", "aramco", "imam", "alfaisal", "nourah",
               "riyadh", "jeddah", "dhahran", "thuwal"]
    lower = org.lower()
    return any(s in lower for s in signals)


def _normalise_org(raw: str) -> str:
    lower = raw.lower()
    for key, val in ORG_MAP.items():
        if key in lower:
            return val
    return raw


def _org_to_city(org: str) -> str:
    return {
        "KAUST":                     "Thuwal",
        "KAU":                       "Jeddah",
        "KSU":                       "Riyadh",
        "KFUPM":                     "Dhahran",
        "KACST":                     "Riyadh",
        "SDAIA":                     "Riyadh",
        "Saudi Aramco":              "Dhahran",
        "Imam University":           "Riyadh",
        "Princess Nourah University":"Riyadh",
        "Alfaisal University":       "Riyadh",
    }.get(org, "Saudi Arabia")


# ── Post-filter: keep only AI-relevant profiles ───────────────────────────────
AI_TITLE_KEYWORDS = [
    "machine learning", "deep learning", "artificial intelligence",
    "data science", "data scientist", "nlp", "natural language",
    "computer vision", "neural", "ai researcher", "ai engineer",
    "research scientist", "professor", "lecturer", "phd",
    "postdoc", "research fellow", "algorithm", "robotics",
    "computational", "knowledge graph", "information retrieval",
]

def is_ai_relevant(record: dict) -> bool:
    """Keep record only if title or org suggests AI relevance."""
    title = record.get("title", "").lower()
    org   = record.get("organization", "").lower()
    papers = record.get("publications", 0) or 0

    # Keep if title contains AI keywords
    if any(kw in title for kw in AI_TITLE_KEYWORDS):
        return True
    # Keep if they have publications (researchers)
    if papers >= 3:
        return True
    # Keep if at a known AI org (SDAIA, KACST etc — smaller orgs = more targeted)
    if any(o in org for o in ["sdaia", "kacst", "mozn", "elm"]):
        return True
    return False
