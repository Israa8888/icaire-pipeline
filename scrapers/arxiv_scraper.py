"""
Scraper 2 — arXiv (paper author discovery)
Uses expanded category list including cs.CY (ethical AI / society).
Saudi institution filter applied to abstract.
"""

import arxiv, logging, time
from config.settings import ARXIV_CATEGORIES, ORG_TO_CITY

logger = logging.getLogger(__name__)

SAUDI_SIGNALS = [
    "saudi","kaust","kacst","sdaia","king abdullah university",
    "king abdulaziz","king saud university","king fahd university",
    "kfupm","imam","alfaisal","princess nourah","aramco",
    "riyadh","jeddah","dhahran","thuwal","arabic nlp","arabert",
]

CAT_TO_SUBFIELD = {
    "cs.AI":"AI / General","cs.LG":"Machine Learning","cs.CL":"NLP",
    "cs.CV":"Computer Vision","cs.NE":"Neural Networks","cs.IR":"Information Retrieval",
    "cs.RO":"Robotics","cs.CY":"AI Ethics & Society","stat.ML":"Statistical ML",
    "eess.AS":"Speech & Audio","q-bio.QM":"Computational Biology",
}

# Queries per category — institution in abstract
QUERIES = [
    ('abs:"King Abdullah University" OR abs:"KAUST"',
     ["cs.AI","cs.LG","cs.CL","cs.CV","cs.CY","cs.NE"]),
    ('abs:"King Saud University" OR abs:"KSU"',
     ["cs.AI","cs.LG","cs.CL","cs.CV","cs.CY"]),
    ('abs:"King Abdulaziz University" OR abs:"KAU"',
     ["cs.AI","cs.LG","cs.CL","cs.CV"]),
    ('abs:"KFUPM" OR abs:"King Fahd University"',
     ["cs.AI","cs.LG","cs.CV","cs.CY"]),
    ('abs:"SDAIA" OR abs:"Saudi Data and AI"',
     ["cs.AI","cs.LG","cs.CY","cs.CL"]),
    ('abs:"KACST"',
     ["cs.AI","cs.LG","cs.CV"]),
    # Arabic NLP — high value for Culture domain
    ('abs:"Arabic NLP" OR abs:"Arabic language model" OR abs:"AraBERT" OR abs:"AraGPT"',
     ["cs.CL"]),
    # Ethical AI explicitly
    ('abs:"AI ethics" OR abs:"algorithmic fairness" OR abs:"responsible AI"',
     ["cs.CY","cs.AI","cs.LG"]),
    # Saudi Arabia broadly
    ('abs:"Saudi Arabia" AND (abs:"deep learning" OR abs:"machine learning")',
     ["cs.AI","cs.LG","cs.CV","stat.ML"]),
]


def fetch_arxiv_profiles(max_per_query: int = 75) -> list[dict]:
    all_records, seen = [], set()
    client = arxiv.Client(num_retries=2, delay_seconds=5)

    for i, (abstract_filter, cats) in enumerate(QUERIES):
        if i > 0: time.sleep(12)
        cat_filter = " OR ".join(f"cat:{c}" for c in cats)
        query      = f"({cat_filter}) AND ({abstract_filter})"
        logger.info(f"arXiv [{i+1}/{len(QUERIES)}]: {query[:80]}...")

        try:
            search = arxiv.Search(
                query=query,
                max_results=max_per_query,
                sort_by=arxiv.SortCriterion.SubmittedDate,
            )
            papers = list(client.results(search))
            logger.info(f"  {len(papers)} papers")

            for paper in papers:
                context  = f"{paper.summary} {paper.comment or ''}"
                if not _has_saudi_signal(context): continue
                subfield = CAT_TO_SUBFIELD.get(paper.primary_category, "AI")
                org      = _guess_org(context)

                for author in paper.authors:
                    name = author.name.strip()
                    if not name or len(name) < 4: continue
                    key  = f"{name.lower()}_{org.lower()}"
                    if key in seen: continue
                    seen.add(key)
                    all_records.append({
                        "name":              name,
                        "title":             "Researcher",
                        "organization":      org,
                        "city":              ORG_TO_CITY.get(org,"Saudi Arabia"),
                        "country":           "Saudi Arabia",
                        "ethical_ai_skills": subfield,
                        "sector":            "academia",
                        "source":            "arxiv",
                    })
        except Exception as e:
            logger.warning(f"arXiv query failed: {e}")
            time.sleep(15)

    logger.info(f"arXiv: {len(all_records)} author records.")
    return all_records


def _has_saudi_signal(text: str) -> bool:
    low = text.lower()
    return any(s in low for s in SAUDI_SIGNALS)


def _guess_org(text: str) -> str:
    low = text.lower()
    if "kaust" in low or "king abdullah university" in low: return "KAUST"
    if "kacst" in low or "king abdulaziz city" in low:     return "KACST"
    if "sdaia" in low:                                      return "SDAIA"
    if "king abdulaziz university" in low:                  return "KAU"
    if "king saud university" in low:                       return "KSU"
    if "kfupm" in low or "king fahd university" in low:     return "KFUPM"
    if "aramco" in low:                                     return "Saudi Aramco"
    if "imam" in low:                                       return "Imam University"
    if "alfaisal" in low:                                   return "Alfaisal University"
    if "princess nourah" in low:                            return "Princess Nourah University"
    return "Saudi Arabia"
