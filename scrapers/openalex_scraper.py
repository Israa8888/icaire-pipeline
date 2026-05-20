"""
Scraper 1 — OpenAlex (primary discovery source)
Finds AI researchers at Saudi institutions.
Also fetches publication details: type, journal, recent paper title.
"""

import requests, logging, time
from config.settings import OPENALEX_INSTITUTION_IDS, OPENALEX_AI_TOPICS, ORG_TO_CITY

logger  = logging.getLogger(__name__)
BASE    = "https://api.openalex.org"
HEADERS = {"User-Agent": "ICAIRE-Pipeline/1.0 (mailto:info@icaire.org)"}


def fetch_openalex_profiles() -> list[dict]:
    all_records, seen = [], set()

    # Strategy 1: by institution + AI topic filter
    for inst_name, inst_id in OPENALEX_INSTITUTION_IDS.items():
        logger.info(f"OpenAlex: {inst_name}...")
        for record in _fetch_institution(inst_id, inst_name):
            uid = record.get("openalex_id","")
            if uid and uid not in seen:
                seen.add(uid); all_records.append(record)
        time.sleep(1)

    # Strategy 2: Saudi country + AI topics
    logger.info("OpenAlex: Saudi Arabia country-level AI search...")
    for topic_id in OPENALEX_AI_TOPICS[:6]:
        for record in _fetch_country_topic(topic_id):
            uid = record.get("openalex_id","")
            if uid and uid not in seen:
                seen.add(uid); all_records.append(record)
        time.sleep(1)

    logger.info(f"OpenAlex: {len(all_records)} profiles collected.")
    return all_records


def _fetch_institution(inst_id: str, inst_name: str) -> list[dict]:
    records, cursor = [], "*"
    while True:
        try:
            r = requests.get(f"{BASE}/authors", headers=HEADERS, timeout=20, params={
                "filter":   f"last_known_institutions.id:{inst_id}",
                "per-page": 50, "cursor": cursor,
                "sort":     "cited_by_count:desc",
            })
            r.raise_for_status()
            data    = r.json()
            results = data.get("results", [])
            if not results: break
            for a in results:
                if _is_ai_related(a):
                    rec = _parse_author(a, inst_name)
                    if rec: records.append(rec)
            cursor = data.get("meta", {}).get("next_cursor")
            if not cursor or len(records) >= 300: break
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"OpenAlex {inst_name}: {e}"); break
    return records


def _fetch_country_topic(topic_id: str) -> list[dict]:
    records = []
    try:
        r = requests.get(f"{BASE}/authors", headers=HEADERS, timeout=20, params={
            "filter":   f"last_known_institutions.country_code:SA,topics.id:{topic_id}",
            "per-page": 50, "sort": "cited_by_count:desc",
        })
        r.raise_for_status()
        for a in r.json().get("results", []):
            rec = _parse_author(a, None)
            if rec: records.append(rec)
    except Exception as e:
        logger.warning(f"OpenAlex country+topic {topic_id}: {e}")
    return records


def _is_ai_related(author: dict) -> bool:
    topics = author.get("topics", []) or []
    ai_kw  = ["machine learning","deep learning","artificial intelligence",
               "neural network","natural language","computer vision",
               "reinforcement learning","data science","AI ethics",
               "algorithmic fairness","explainable","generative"]
    for t in topics:
        if any(kw in t.get("display_name","").lower() for kw in ai_kw):
            return True
    return (author.get("works_count",0) or 0) >= 3


def _parse_author(author: dict, inst_override: str | None) -> dict | None:
    name = author.get("display_name","").strip()
    if not name: return None

    insts   = author.get("last_known_institutions") or []
    inst    = insts[0] if insts else {}
    country = inst.get("country_code","")
    if country and country != "SA": return None

    raw_org = inst_override or inst.get("display_name","Saudi Arabia")
    org     = _norm_org(raw_org)
    oa_id   = (author.get("id") or "").replace("https://openalex.org/","")
    orcid   = (author.get("ids") or {}).get("orcid","")
    if orcid: orcid = orcid.replace("https://orcid.org/","")

    papers  = author.get("works_count",0) or 0
    cited   = author.get("cited_by_count",0) or 0
    topics  = author.get("topics",[]) or []
    subfield= topics[0].get("display_name","AI") if topics else "AI"

    # Fetch top works for journal/type/recent paper
    pub_types, journals, recent_title = _fetch_works(oa_id)

    return {
        "name":              name,
        "title":             "Researcher",
        "organization":      org,
        "city":              ORG_TO_CITY.get(org, "Saudi Arabia"),
        "country":           "Saudi Arabia",
        "openalex_id":       oa_id,
        "orcid":             orcid,
        "publications":      papers,
        "citations":         cited,
        "publication_types": pub_types,
        "top_journals":      journals,
        "recent_paper_title":recent_title,
        "ethical_ai_skills": subfield,
        "sector":            "academia",
        "source":            "openalex",
    }


def _fetch_works(oa_id: str) -> tuple[str, str, str]:
    if not oa_id: return "", "", ""
    try:
        r = requests.get(f"{BASE}/works", headers=HEADERS, timeout=15, params={
            "filter":   f"author.id:{oa_id}",
            "per-page": 10, "sort": "publication_date:desc",
            "select":   "title,type,primary_location",
        })
        r.raise_for_status()
        works = r.json().get("results", [])
        types   = list({w.get("type","") for w in works if w.get("type")})
        journals= list({
            (w.get("primary_location") or {}).get("source",{}).get("display_name","")
            for w in works
            if (w.get("primary_location") or {}).get("source")
        })
        recent  = works[0].get("title","") if works else ""
        return (", ".join(types[:3]),
                ", ".join(j for j in journals[:3] if j),
                recent)
    except Exception:
        return "", "", ""


def _norm_org(raw: str) -> str:
    m = {
        "king abdullah university":"KAUST","kaust":"KAUST",
        "king abdulaziz city":"KACST","kacst":"KACST",
        "king abdulaziz university":"KAU","king saud university":"KSU",
        "king fahd university":"KFUPM","kfupm":"KFUPM",
        "imam":"Imam University","princess nourah":"Princess Nourah University",
        "alfaisal":"Alfaisal University","aramco":"Saudi Aramco",
        "sdaia":"SDAIA","elm":"Elm","mozn":"Mozn",
    }
    low = raw.lower()
    for k,v in m.items():
        if k in low: return v
    return raw
