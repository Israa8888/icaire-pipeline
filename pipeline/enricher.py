"""
Pipeline Step — Basic Enricher
Adds: lat/long for map, default manual fields, timestamp.
ORCID enrichment is handled separately by orcid_enricher.py
"""

import logging
from datetime import datetime, timezone
from config.settings import CITY_COORDINATES, ORG_TO_CITY

logger = logging.getLogger(__name__)


def enrich(records: list[dict]) -> list[dict]:
    enriched = []
    for record in records:
        r = dict(record)

        # Lat/long from city
        city = r.get("city","")
        if city in CITY_COORDINATES and not r.get("latitude"):
            lat, lon = CITY_COORDINATES[city]
            r["latitude"]  = lat
            r["longitude"] = lon

        # If city is missing, infer from org
        if not r.get("city") or r.get("city") == "Saudi Arabia":
            org = r.get("organization","")
            if org in ORG_TO_CITY:
                r["city"] = ORG_TO_CITY[org]
                if r["city"] in CITY_COORDINATES:
                    lat, lon = CITY_COORDINATES[r["city"]]
                    r["latitude"]  = lat
                    r["longitude"] = lon

        # Sources merged
        if not r.get("sources_merged"):
            r["sources_merged"] = r.get("source","unknown")

        # Default manual fields — never overwrite
        r.setdefault("connection_status", "Not contacted")
        r.setdefault("connection_type",   "")
        r.setdefault("outreach_notes",    "")
        r.setdefault("meeting_done",      "No")
        r.setdefault("added_by",          "pipeline")

        # Default empty fields for completeness
        r.setdefault("degree",            "")
        r.setdefault("experience_years",  "")
        r.setdefault("email",             "")
        r.setdefault("email_source",      "")
        r.setdefault("linkedin_url",      "")
        r.setdefault("orcid",             "")
        r.setdefault("openalex_id",       "")
        r.setdefault("citations",         0)
        r.setdefault("publication_types", "")
        r.setdefault("top_journals",      "")
        r.setdefault("recent_paper_title","")
        r.setdefault("unesco_domains",    "")
        r.setdefault("unesco_sub_areas",  "")
        r.setdefault("ethical_ai_skills", "")
        r.setdefault("ai_relationship",   "")
        r.setdefault("org_type",          "")
        r.setdefault("industry_area",     "")
        r.setdefault("tier",              "")
        r.setdefault("priority_score",    "")

        r["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        enriched.append(r)

    logger.info(f"Enricher: {len(enriched)} records processed.")
    return enriched
