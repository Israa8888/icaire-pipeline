"""
Scraper 1A — OpenAlex WORKS API (fast version)
Step 1: Collect all Saudi authors from AI papers (no extra API calls)
Step 2: Batch-enrich author profiles in one pass at the end
"""

import requests, logging, time
from config.settings import ORG_TO_CITY

logger  = logging.getLogger(__name__)
BASE    = "https://api.openalex.org"
HEADERS = {"User-Agent": "ICAIRE-Pipeline/1.0 (mailto:info@icaire.org)"}

AI_PAPER_SEARCHES = [
    {"topic": "AI ethics & governance",    "query": "artificial intelligence ethics governance"},
    {"topic": "Algorithmic fairness",      "query": "algorithmic fairness bias machine learning"},
    {"topic": "Responsible AI",            "query": "responsible AI trustworthy"},
    {"topic": "Explainable AI",            "query": "explainable artificial intelligence XAI"},
    {"topic": "Arabic NLP",                "query": "Arabic natural language processing NLP"},
    {"topic": "Machine Learning",          "query": "machine learning deep learning Saudi"},
    {"topic": "Computer Vision",           "query": "computer vision image recognition Saudi"},
    {"topic": "AI Safety",                 "query": "AI safety alignment"},
    {"topic": "Privacy preserving AI",     "query": "privacy preserving federated learning"},
    {"topic": "AI in healthcare",          "query": "artificial intelligence healthcare medical Saudi"},
    {"topic": "AI in education",           "query": "artificial intelligence education learning Saudi"},
    {"topic": "AI & misinformation",       "query": "AI disinformation fake news detection"},
]

SAUDI_SIGNALS = [
    "saudi","kaust","kacst","sdaia","king abdullah","king abdulaziz",
    "king saud","king fahd","kfupm","imam","alfaisal",
    "princess nourah","aramco","riyadh","jeddah","thuwal","dhahran",
]


def fetch_openalex_profiles() -> list[dict]:
    # Phase 1: collect author IDs and basic info from papers
    raw_authors = {}  # openalex_id → basic record

    for search in AI_PAPER_SEARCHES:
        topic = search["topic"]
        query = search["query"]
        logger.info(f"OpenAlex: '{topic}'...")
        _collect_from_papers(query, topic, raw_authors)
        time.sleep(0.5)

    logger.info(f"  Phase 1 done: {len(raw_authors)} unique Saudi AI authors found")

    # Phase 2: batch enrich
    enriched = _batch_enrich(list(raw_authors.values()))

    # Phase 3: filter — keep only people with 3+ papers OR explicit AI title
    before = len(enriched)
    enriched = [
        r for r in enriched
        if (int(r.get("publications") or 0) >= 3)
        or any(kw in (r.get("title") or "").lower()
               for kw in ["ai","machine learning","data scientist",
                           "professor","researcher","engineer"])
    ]
    logger.info(f"  Filter: {before} → {len(enriched)} (removed {before-len(enriched)} 1-paper co-authors)")

    logger.info(f"OpenAlex: {len(enriched)} profiles collected.")
    return enriched


def _collect_from_papers(query: str, topic: str, raw_authors: dict) -> None:
    try:
        resp = requests.get(
            f"{BASE}/works",
            headers=HEADERS,
            timeout=20,
            params={
                "search":   query,
                "filter":   "authorships.institutions.country_code:SA",
                "per-page": 50,
                "sort":     "cited_by_count:desc",
                "select":   "id,title,authorships,type,primary_location",
            }
        )
        resp.raise_for_status()
        works = resp.json().get("results", [])
        logger.info(f"  {len(works)} papers found")

        for work in works:
            pub_type = work.get("type", "")
            journal  = ((work.get("primary_location") or {})
                        .get("source") or {}).get("display_name", "")
            title    = work.get("title", "")

            for authorship in work.get("authorships", []):
                institutions = authorship.get("institutions", [])
                if not _is_saudi(institutions):
                    continue

                author    = authorship.get("author", {})
                author_id = (author.get("id") or "").replace("https://openalex.org/", "")
                name      = (author.get("display_name") or "").strip()
                if not name or not author_id:
                    continue

                if author_id in raw_authors:
                    # Already seen — just add more topic tags
                    existing = raw_authors[author_id]
                    existing_skills = existing.get("ethical_ai_skills", "")
                    if topic not in existing_skills:
                        existing["ethical_ai_skills"] = f"{existing_skills}, {topic}".strip(", ")
                    continue

                inst    = institutions[0] if institutions else {}
                raw_org = inst.get("display_name", "")
                org     = _norm_org(raw_org)
                city    = ORG_TO_CITY.get(org, _inst_city(inst))

                raw_authors[author_id] = {
                    "name":               name,
                    "title":              "Researcher",
                    "organization":       org,
                    "city":               city,
                    "country":            "Saudi Arabia",
                    "openalex_id":        author_id,
                    "orcid":              "",
                    "publications":       "",
                    "citations":          "",
                    "publication_types":  pub_type,
                    "top_journals":       journal,
                    "recent_paper_title": title,
                    "ethical_ai_skills":  topic,
                    "sector":             _guess_sector(org),
                    "source":             "openalex",
                }

    except Exception as e:
        logger.warning(f"OpenAlex paper search failed for '{query}': {e}")


def _batch_enrich(records: list[dict]) -> list[dict]:
    """
    Enrich author profiles in batches of 50 using OpenAlex filter API.
    One API call per 50 authors instead of one per author.
    """
    if not records:
        return records

    logger.info(f"  Phase 2: enriching {len(records)} authors in batches...")
    enriched_map = {}

    # Split into batches of 50
    ids = [r["openalex_id"] for r in records if r.get("openalex_id")]
    batches = [ids[i:i+50] for i in range(0, len(ids), 50)]

    for i, batch in enumerate(batches):
        logger.info(f"  Enrichment batch {i+1}/{len(batches)}...")
        try:
            filter_str = "|".join(batch)
            resp = requests.get(
                f"{BASE}/authors",
                headers=HEADERS,
                timeout=20,
                params={
                    "filter":   f"ids.openalex:{filter_str}",
                    "per-page": 50,
                    "select":   "id,works_count,cited_by_count,ids",
                }
            )
            resp.raise_for_status()
            authors = resp.json().get("results", [])

            for a in authors:
                aid   = (a.get("id") or "").replace("https://openalex.org/", "")
                orcid = (a.get("ids") or {}).get("orcid", "")
                if orcid:
                    orcid = orcid.replace("https://orcid.org/", "")
                enriched_map[aid] = {
                    "orcid":        orcid,
                    "publications": a.get("works_count", 0) or 0,
                    "citations":    a.get("cited_by_count", 0) or 0,
                }

        except Exception as e:
            logger.warning(f"  Batch enrichment failed: {e}")

        time.sleep(0.5)

    # Merge enrichment back into records
    for r in records:
        aid = r.get("openalex_id", "")
        if aid in enriched_map:
            r.update(enriched_map[aid])

    return records


def _is_saudi(institutions: list) -> bool:
    for inst in institutions:
        if inst.get("country_code") == "SA":
            return True
        name = (inst.get("display_name") or "").lower()
        if any(s in name for s in SAUDI_SIGNALS):
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
    geo = inst.get("geo") or {}
    return geo.get("city", "Saudi Arabia")


def _guess_sector(org: str) -> str:
    academia   = ["KAUST","KAU","KSU","KFUPM","KACST",
                  "Imam University","Princess Nourah University","Alfaisal University"]
    government = ["SDAIA"]
    if org in academia:    return "academia"
    if org in government:  return "government"
    return "industry"
