"""
Scraper 1A — OpenAlex WORKS API
Searches AI/ethical AI papers where at least one author is Saudi-affiliated.
Guarantees every person collected has published AI-related work.
"""

import requests, logging, time
from config.settings import ORG_TO_CITY

logger  = logging.getLogger(__name__)
BASE    = "https://api.openalex.org"
HEADERS = {"User-Agent": "ICAIRE-Pipeline/1.0 (mailto:info@icaire.org)"}

# Search papers by topic — these are OpenAlex topic IDs confirmed for AI/ethics
AI_PAPER_SEARCHES = [
    # Ethical AI explicitly
    {"topic": "AI ethics",                "query": "artificial intelligence ethics"},
    {"topic": "Algorithmic fairness",     "query": "algorithmic fairness bias"},
    {"topic": "Responsible AI",           "query": "responsible AI governance"},
    {"topic": "Explainable AI",           "query": "explainable artificial intelligence XAI"},
    {"topic": "AI policy",                "query": "AI policy regulation"},
    # Core AI subfields relevant to ethical AI
    {"topic": "NLP / Arabic NLP",         "query": "natural language processing Arabic"},
    {"topic": "Machine Learning",         "query": "machine learning deep learning"},
    {"topic": "Computer Vision",          "query": "computer vision image recognition"},
    {"topic": "AI Safety",               "query": "AI safety alignment"},
    {"topic": "Privacy / Data protection","query": "privacy preserving machine learning"},
    # Applied ethical AI
    {"topic": "AI in healthcare",         "query": "artificial intelligence healthcare medical"},
    {"topic": "AI in education",          "query": "artificial intelligence education learning"},
    {"topic": "AI & misinformation",      "query": "AI disinformation detection fake news"},
    {"topic": "Arabic language AI",       "query": "Arabic language model NLP AraBERT"},
]

SAUDI_ORG_SIGNALS = [
    "saudi", "kaust", "kacst", "sdaia",
    "king abdullah", "king abdulaziz", "king saud",
    "king fahd", "kfupm", "imam", "alfaisal",
    "princess nourah", "aramco", "riyadh", "jeddah",
    "thuwal", "dhahran", "elm company", "mozn",
]


def fetch_openalex_profiles() -> list[dict]:
    all_records = []
    seen_ids    = set()

    for search in AI_PAPER_SEARCHES:
        topic   = search["topic"]
        query   = search["query"]
        logger.info(f"OpenAlex WORKS: '{topic}'...")

        authors = _fetch_authors_from_papers(query, topic)
        for r in authors:
            uid = r.get("openalex_id", "")
            if uid and uid not in seen_ids:
                seen_ids.add(uid)
                all_records.append(r)
            elif not uid:
                # No OpenAlex ID — use name+org as key
                key = f"{r.get('name','').lower()}_{r.get('organization','').lower()}"
                if key not in seen_ids:
                    seen_ids.add(key)
                    all_records.append(r)

        time.sleep(1)

    logger.info(f"OpenAlex: {len(all_records)} AI-relevant profiles collected.")
    return all_records


def _fetch_authors_from_papers(query: str, topic: str) -> list[dict]:
    """
    Search papers by query, filter for Saudi-authored ones,
    extract and enrich each author.
    """
    authors_found = []
    seen_author_ids = set()

    try:
        # Search works (papers) matching the query
        resp = requests.get(
            f"{BASE}/works",
            headers=HEADERS,
            timeout=20,
            params={
                "search":   query,
                "filter":   "authorships.institutions.country_code:SA",
                "per-page": 50,
                "sort":     "cited_by_count:desc",
                "select":   "id,title,authorships,publication_year,type,primary_location,cited_by_count",
            }
        )
        resp.raise_for_status()
        works = resp.json().get("results", [])
        logger.info(f"  Found {len(works)} papers")

        for work in works:
            pub_type  = work.get("type", "")
            journal   = ((work.get("primary_location") or {})
                         .get("source") or {}).get("display_name", "")
            pub_year  = work.get("publication_year", "")
            title     = work.get("title", "")

            for authorship in work.get("authorships", []):
                author = authorship.get("author", {})
                author_id = (author.get("id") or "").replace("https://openalex.org/", "")

                # Only include Saudi-affiliated authors
                institutions = authorship.get("institutions", [])
                if not _is_saudi_affiliated(institutions):
                    continue

                if author_id and author_id in seen_author_ids:
                    continue
                if author_id:
                    seen_author_ids.add(author_id)

                name = author.get("display_name", "").strip()
                if not name:
                    continue

                # Get institution details
                inst     = institutions[0] if institutions else {}
                raw_org  = inst.get("display_name", "")
                org      = _norm_org(raw_org)
                city     = ORG_TO_CITY.get(org, _inst_city(inst))

                # Fetch full author profile for publications/citations
                full_profile = _fetch_author_profile(author_id) if author_id else {}

                record = {
                    "name":               name,
                    "title":              "Researcher",
                    "organization":       org,
                    "city":               city,
                    "country":            "Saudi Arabia",
                    "openalex_id":        author_id,
                    "orcid":              full_profile.get("orcid", ""),
                    "publications":       full_profile.get("publications", ""),
                    "citations":          full_profile.get("citations", ""),
                    "publication_types":  pub_type,
                    "top_journals":       journal,
                    "recent_paper_title": title,
                    "ethical_ai_skills":  topic,
                    "sector":             _guess_sector(org),
                    "source":             "openalex",
                }
                authors_found.append(record)

    except Exception as e:
        logger.warning(f"OpenAlex works search failed for '{query}': {e}")

    return authors_found


def _fetch_author_profile(author_id: str) -> dict:
    """Fetch full author profile for publications and citations count."""
    if not author_id:
        return {}
    try:
        resp = requests.get(
            f"{BASE}/authors/{author_id}",
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        # Get top journals from recent works
        works_resp = requests.get(
            f"{BASE}/works",
            headers=HEADERS,
            timeout=15,
            params={
                "filter":   f"author.id:{author_id}",
                "per-page": 5,
                "sort":     "publication_date:desc",
                "select":   "title,primary_location,type",
            }
        )
        journals = []
        recent_title = ""
        if works_resp.ok:
            works = works_resp.json().get("results", [])
            if works:
                recent_title = works[0].get("title", "")
            journals = list({
                ((w.get("primary_location") or {}).get("source") or {}).get("display_name", "")
                for w in works
                if ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
            })

        orcid = (data.get("ids") or {}).get("orcid", "")
        if orcid:
            orcid = orcid.replace("https://orcid.org/", "")

        return {
            "orcid":              orcid,
            "publications":       data.get("works_count", 0) or 0,
            "citations":          data.get("cited_by_count", 0) or 0,
            "top_journals":       ", ".join(j for j in journals[:3] if j),
            "recent_paper_title": recent_title,
        }
    except Exception:
        return {}


def _is_saudi_affiliated(institutions: list) -> bool:
    for inst in institutions:
        country = inst.get("country_code", "")
        if country == "SA":
            return True
        name = inst.get("display_name", "").lower()
        if any(sig in name for sig in SAUDI_ORG_SIGNALS):
            return True
    return False


def _norm_org(raw: str) -> str:
    m = {
        "king abdullah university": "KAUST",
        "kaust":                    "KAUST",
        "king abdulaziz city":      "KACST",
        "king abdulaziz university":"KAU",
        "king saud university":     "KSU",
        "king fahd university":     "KFUPM",
        "kfupm":                    "KFUPM",
        "imam":                     "Imam University",
        "princess nourah":          "Princess Nourah University",
        "alfaisal":                 "Alfaisal University",
        "aramco":                   "Saudi Aramco",
        "sdaia":                    "SDAIA",
        "elm":                      "Elm",
        "mozn":                     "Mozn",
    }
    low = raw.lower()
    for k, v in m.items():
        if k in low:
            return v
    return raw


def _inst_city(inst: dict) -> str:
    """Extract city from OpenAlex institution data."""
    geo = inst.get("geo") or {}
    city = geo.get("city", "")
    if city:
        return city
    return ORG_TO_CITY.get(_norm_org(inst.get("display_name", "")), "Saudi Arabia")


def _guess_sector(org: str) -> str:
    academic = ["KAUST", "KAU", "KSU", "KFUPM", "KACST",
                "Imam University", "Princess Nourah University", "Alfaisal University"]
    government = ["SDAIA"]
    if org in academic:    return "academia"
    if org in government:  return "government"
    return "industry"
