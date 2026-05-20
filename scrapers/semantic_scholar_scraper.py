"""
Scraper 2 — Semantic Scholar (free API, no key needed)
Pulls AI researchers affiliated with Saudi institutions.
"""

import logging
from semanticscholar import SemanticScholar
from config.settings import TARGET_INSTITUTIONS

logger = logging.getLogger(__name__)

sch = SemanticScholar()

SEARCH_QUERIES = [
    "artificial intelligence Saudi Arabia",
    "machine learning KAUST",
    "deep learning Saudi",
    "NLP Arabic language model",
    "computer vision KACST",
    "reinforcement learning KFUPM",
    "AI SDAIA Saudi",
]


def fetch_semantic_scholar_profiles() -> list[dict]:
    all_records = []
    seen_ids = set()

    for query in SEARCH_QUERIES:
        logger.info(f"Semantic Scholar: searching '{query}'...")
        try:
            results = sch.search_author(query, limit=20)
        except Exception as e:
            logger.warning(f"Semantic Scholar query failed '{query}': {e}")
            continue

        for author in results:
            aid = str(author.authorId)
            if aid in seen_ids:
                continue

            affiliations = _get_affiliations(author)
            if not _is_saudi_affiliated(affiliations):
                continue

            seen_ids.add(aid)
            record = _parse_author(author, affiliations)
            if record:
                all_records.append(record)
                logger.debug(f"  + {record['name']} — {record['organization']}")

    logger.info(f"Semantic Scholar: collected {len(all_records)} profiles.")
    return all_records


def _get_affiliations(author) -> list[str]:
    try:
        affiliations = author.affiliations or []
        return [a.get("name", "") if isinstance(a, dict) else str(a)
                for a in affiliations]
    except Exception:
        return []


def _is_saudi_affiliated(affiliations: list[str]) -> bool:
    combined = " ".join(affiliations).lower()
    saudi_signals = [i.lower() for i in TARGET_INSTITUTIONS] + \
                    ["saudi", "ksa", "riyadh", "jeddah", "dammam"]
    return any(sig in combined for sig in saudi_signals)


def _parse_author(author, affiliations: list[str]) -> dict | None:
    name = author.name
    if not name:
        return None

    org = affiliations[0] if affiliations else ""
    # Normalise to short institution name
    org = _normalise_org(org)

    papers = author.paperCount or 0
    h_idx  = author.hIndex or 0

    return {
        "name":               name,
        "title":              "Researcher",   # enriched later by Claude
        "organization":       org,
        "city":               _guess_city(org),
        "country":            "Saudi Arabia",
        "semantic_scholar_id": str(author.authorId),
        "publications":       papers,
        "h_index":            h_idx,
        "source":             "semantic_scholar",
        "sector":             "academia",
    }


def _normalise_org(raw: str) -> str:
    mapping = {
        "king abdullah university": "KAUST",
        "kaust":                    "KAUST",
        "king abdulaziz city":      "KACST",
        "kacst":                    "KACST",
        "saudi data":               "SDAIA",
        "sdaia":                    "SDAIA",
        "king abdulaziz university":"KAU",
        "king saud university":     "KSU",
        "king fahd university":     "KFUPM",
        "kfupm":                    "KFUPM",
        "imam":                     "Imam University",
        "aramco":                   "Saudi Aramco",
        "elm":                      "Elm",
        "mozn":                     "Mozn",
    }
    lower = raw.lower()
    for key, val in mapping.items():
        if key in lower:
            return val
    return raw


def _guess_city(org: str) -> str:
    city_map = {
        "KAUST":        "Thuwal",
        "KAU":          "Jeddah",
        "KSU":          "Riyadh",
        "KFUPM":        "Dhahran",
        "KACST":        "Riyadh",
        "SDAIA":        "Riyadh",
        "Saudi Aramco": "Dhahran",
        "Elm":          "Riyadh",
        "Mozn":         "Riyadh",
        "Imam University": "Riyadh",
    }
    return city_map.get(org, "Saudi Arabia")
