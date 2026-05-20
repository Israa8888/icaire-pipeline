"""
ORCID Enricher — enriches existing records using ORCID IDs
found by OpenAlex. Also enriches LinkedIn/Google records
if ORCID can be found by name + org search.

Gets: email, email_source, degree, experience_years,
      employment history, education.
"""

import requests, logging, time
from config.settings import ORG_TO_CITY

logger   = logging.getenv = logging.getLogger(__name__)
BASE     = "https://pub.orcid.org/v3.0"
HEADERS  = {"Accept":"application/json","User-Agent":"ICAIRE-Pipeline/1.0"}

DEGREE_KEYWORDS = {
    "phd":"PhD","ph.d":"PhD","doctor":"PhD","prof":"PhD","professor":"PhD",
    "postdoc":"PhD","associate prof":"PhD",
    "msc":"MSc","m.sc":"MSc","master":"MSc","ms ":"MSc",
    "bsc":"BSc","b.sc":"BSc","bachelor":"BSc",
}


def enrich_with_orcid(records: list[dict]) -> list[dict]:
    enriched = []
    calls    = 0

    for record in records:
        r = dict(record)
        orcid_id = r.get("orcid","").strip()

        # Try to find ORCID if we don't have it
        if not orcid_id and calls < 200:
            orcid_id = _search_orcid(r)
            if orcid_id:
                r["orcid"] = orcid_id
                calls += 1
                time.sleep(0.5)

        # Fetch profile if we have ORCID
        if orcid_id:
            profile = _fetch_profile(orcid_id)
            if profile:
                # Only fill fields that are empty
                for field in ["email","email_source","degree",
                              "experience_years","title"]:
                    if not r.get(field) and profile.get(field):
                        r[field] = profile[field]
                # LinkedIn URL enrichment
                if not r.get("linkedin_url") and profile.get("linkedin_url"):
                    r["linkedin_url"] = profile["linkedin_url"]

        enriched.append(r)

    logger.info(f"ORCID enricher: processed {len(enriched)} records.")
    return enriched


def _search_orcid(record: dict) -> str:
    """Try to find ORCID ID by name + org for records without one."""
    name = record.get("name","").strip()
    org  = record.get("organization","").strip()
    if not name or not org: return ""

    # Only search for known Saudi orgs — avoids false positives
    known_orgs = ["KAUST","KAU","KSU","KFUPM","KACST","SDAIA",
                  "Imam University","Alfaisal University",
                  "Princess Nourah University","Saudi Aramco"]
    if org not in known_orgs: return ""

    query = f'family-name:"{name.split()[-1]}" AND given-names:"{name.split()[0]}"'
    try:
        r = requests.get(f"{BASE}/search/",
            params={"q":query,"rows":3},
            headers=HEADERS, timeout=10)
        r.raise_for_status()
        results = r.json().get("result",[]) or []
        if len(results) == 1:   # only use if unambiguous single match
            return results[0].get("orcid-identifier",{}).get("path","")
    except Exception:
        pass
    return ""


def _fetch_profile(orcid_id: str) -> dict:
    try:
        r = requests.get(f"{BASE}/{orcid_id}/record",
            headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning(f"ORCID fetch failed {orcid_id}: {e}")
        return {}

    result = {}

    # Email (public only)
    emails = (data.get("person",{}).get("emails",{}).get("email",[]))
    if emails:
        result["email"]        = emails[0].get("email","")
        result["email_source"] = "orcid_profile"

    # LinkedIn URL from external identifiers
    ext_ids = (data.get("person",{})
                   .get("external-identifiers",{})
                   .get("external-identifier",[]))
    for ext in ext_ids:
        if "linkedin" in str(ext.get("external-id-type","")).lower():
            url = ext.get("external-id-url",{}).get("value","")
            if url:
                result["linkedin_url"] = url
                break

    # Current employment → title
    employments = (data.get("activities-summary",{})
                       .get("employments",{})
                       .get("affiliation-group",[]))
    for grp in employments:
        for s in grp.get("summaries",[]):
            emp = s.get("employment-summary",{})
            if emp.get("end-date"): continue
            title = (emp.get("role-title") or "").strip()
            if title:
                result["title"] = title
                break
        if result.get("title"): break

    # Education → degree + experience years
    educations = (data.get("activities-summary",{})
                      .get("educations",{})
                      .get("affiliation-group",[]))
    highest_degree = ""
    earliest_year  = 9999

    for grp in educations:
        for s in grp.get("summaries",[]):
            edu   = s.get("education-summary",{})
            role  = (edu.get("role-title") or "").lower()
            degree= _infer_degree(role)
            if degree and _degree_rank(degree) > _degree_rank(highest_degree):
                highest_degree = degree
            # Start year for experience calculation
            start = edu.get("start-date",{})
            year  = start.get("year",{}).get("value")
            if year:
                try:
                    yr = int(year)
                    if yr < earliest_year: earliest_year = yr
                except ValueError: pass

    if highest_degree:
        result["degree"] = highest_degree
    if earliest_year < 9999:
        result["experience_years"] = 2026 - earliest_year

    return result


def _infer_degree(role_text: str) -> str:
    for kw, degree in DEGREE_KEYWORDS.items():
        if kw in role_text:
            return degree
    return ""


def _degree_rank(degree: str) -> int:
    return {"BSc":1,"MSc":2,"PhD":3}.get(degree, 0)
