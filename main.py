"""
main.py — ICAIRE Ethical AI Connection Pipeline
Sources: OpenAlex (primary) + arXiv + Google Custom Search
Enrichment: ORCID (adds email, degree, experience)
Classification: Claude API (UNESCO domains, ethical AI skills, tier, score)

Run: python main.py
     DRY_RUN=true python main.py
"""

import logging, sys, os
from datetime import datetime, timezone

os.makedirs("output", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f"output/run_{datetime.now().strftime('%Y%m%d_%H%M')}.log"),
    ]
)
logger = logging.getLogger(__name__)


def run():
    logger.info("="*60)
    logger.info("ICAIRE Ethical AI Pipeline — starting")
    logger.info("="*60)

    stats   = {"total_raw":0,"duplicates_merged":0,"errors":0,"sources":""}
    all_raw = []
    sources = []

    # ── STEP 1: Collect ──────────────────────────────────────────
    logger.info("STEP 1 — Collecting from all sources...")

    try:
        from scrapers.openalex_scraper import fetch_openalex_profiles
        oa = fetch_openalex_profiles()
        all_raw.extend(oa); sources.append("openalex")
        logger.info(f"  OpenAlex: {len(oa)} records")
    except Exception as e:
        logger.error(f"  OpenAlex failed: {e}"); stats["errors"] += 1

    try:
        from scrapers.arxiv_scraper import fetch_arxiv_profiles
        ax = fetch_arxiv_profiles()
        all_raw.extend(ax); sources.append("arxiv")
        logger.info(f"  arXiv: {len(ax)} records")
    except Exception as e:
        logger.error(f"  arXiv failed: {e}"); stats["errors"] += 1

    try:
        from scrapers.google_search_scraper import fetch_google_profiles
        gs = fetch_google_profiles()
        all_raw.extend(gs); sources.append("google_linkedin")
        logger.info(f"  Google/LinkedIn: {len(gs)} records")
    except Exception as e:
        logger.warning(f"  Google search skipped: {e}")

    stats["total_raw"] = len(all_raw)
    stats["sources"]   = ",".join(sources)
    logger.info(f"  Total raw: {len(all_raw)} from {len(sources)} sources")

    if not all_raw:
        logger.error("No records collected. Check network and try again.")
        return

    # ── STEP 2: Deduplicate ──────────────────────────────────────
    logger.info("STEP 2 — Deduplicating...")
    from pipeline.deduplicator import deduplicate
    deduped = deduplicate(all_raw)
    stats["duplicates_merged"] = stats["total_raw"] - len(deduped)
    logger.info(f"  {len(deduped)} unique people ({stats['duplicates_merged']} merged)")

    # ── STEP 3: Basic enrichment (lat/long, defaults) ────────────
    logger.info("STEP 3 — Basic enrichment...")
    from pipeline.enricher import enrich
    enriched = enrich(deduped)
    logger.info(f"  {len(enriched)} records enriched")

    # ── STEP 4: ORCID enrichment (email, degree, experience) ─────
    logger.info("STEP 4 — ORCID enrichment (email, degree, LinkedIn)...")
    from pipeline.orcid_enricher import enrich_with_orcid
    enriched = enrich_with_orcid(enriched)
    email_count = sum(1 for r in enriched if r.get("email"))
    logger.info(f"  {email_count} records now have email")

    # ── STEP 5: Claude API classification ────────────────────────
    logger.info("STEP 5 — Classifying with Claude API (UNESCO + ethical AI)...")
    from pipeline.classifier import classify
    classified = classify(enriched)
    logger.info(f"  {len(classified)} records classified")

    # Print breakdown
    for tier, label in [(1,"Speaker"),(2,"Partner"),(3,"Research")]:
        n = sum(1 for r in classified if r.get("tier") == tier)
        logger.info(f"    Tier {tier} ({label}): {n}")

    for domain in ["Education","Natural Sciences","Social & Human Sciences",
                   "Culture","Communication & Information"]:
        n = sum(1 for r in classified
                if domain in str(r.get("unesco_domains","")))
        logger.info(f"    {domain}: {n}")

    # ── STEP 6: Push to Google Sheets ────────────────────────────
    logger.info("STEP 6 — Pushing to Google Sheets...")
    from pipeline.push_to_sheets import push_to_sheets
    push_to_sheets(classified, stats)

    logger.info("="*60)
    logger.info("Pipeline complete.")
    logger.info("="*60)


if __name__ == "__main__":
    run()
