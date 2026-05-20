"""
Pipeline Step — Deduplication
Merges records of the same person from multiple sources.
Priority: LinkedIn URL > ORCID > OpenAlex ID > email > fuzzy name+org
Manual fields (connection_status, outreach_notes etc) are NEVER overwritten.
"""

import re, logging
from rapidfuzz import fuzz
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MANUAL_FIELDS = {
    "connection_status","connection_type",
    "outreach_notes","meeting_done","added_by"
}
KEEP_MAX = {"publications","citations","priority_score","experience_years"}


def deduplicate(records: list[dict]) -> list[dict]:
    index     = {}   # canonical_key → merged record
    alias_map = {}   # unique_id → canonical_key

    total_in = len(records)
    merged_ct = 0

    for record in records:
        canonical = _find_existing(record, index, alias_map)
        if canonical:
            index[canonical] = _merge(index[canonical], record)
            merged_ct += 1
        else:
            key = _make_key(record)
            index[key] = record
            _register_aliases(record, key, alias_map)

    result = list(index.values())
    logger.info(f"Dedup: {total_in} in → {len(result)} unique "
                f"({merged_ct} duplicates merged)")
    return result


def _find_existing(record, index, alias_map) -> str | None:
    # Step 1: exact unique ID match
    for uid_field in ["linkedin_url","orcid","openalex_id","email"]:
        uid = (record.get(uid_field) or "").strip()
        if uid and uid in alias_map:
            return alias_map[uid]

    # Step 2: fuzzy name + org (threshold: 88% name, 72% org)
    name_norm = _norm_name(record.get("name",""))
    org_norm  = _norm_org(record.get("organization",""))
    if not name_norm: return None

    for key, existing in index.items():
        en = _norm_name(existing.get("name",""))
        eo = _norm_org(existing.get("organization",""))
        ns = fuzz.token_sort_ratio(name_norm, en)
        os = fuzz.token_sort_ratio(org_norm, eo) if org_norm and eo else 0
        if ns >= 88 and os >= 72:
            return key

    return None


def _merge(existing: dict, new: dict) -> dict:
    merged = dict(existing)
    for field, val in new.items():
        if field in MANUAL_FIELDS:
            continue
        if field in KEEP_MAX:
            try:
                merged[field] = max(int(merged.get(field) or 0), int(val or 0))
            except (ValueError, TypeError):
                pass
            continue
        if field == "source":
            existing_sources = set(merged.get("sources_merged","").split(","))
            existing_sources.discard("")
            existing_sources.add(val)
            existing_sources.add(merged.get("source",""))
            existing_sources.discard("")
            merged["sources_merged"] = ",".join(sorted(existing_sources))
            continue
        # List fields — merge, not overwrite
        if field in ["unesco_domains","unesco_sub_areas","ethical_ai_skills"]:
            existing_vals = set(str(merged.get(field,"")).split(","))
            existing_vals.discard("")
            new_vals = set(str(val or "").split(","))
            new_vals.discard("")
            merged[field] = ",".join(sorted(existing_vals | new_vals))
            continue
        # Default: fill empty with new value
        if not merged.get(field) and val:
            merged[field] = val

    merged["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return merged


def _make_key(record: dict) -> str:
    for uid in ["linkedin_url","openalex_id","orcid","email"]:
        v = (record.get(uid) or "").strip()
        if v: return v
    return f"{_norm_name(record.get('name','unknown'))}__{_norm_org(record.get('organization',''))}"


def _register_aliases(record: dict, key: str, alias_map: dict) -> None:
    for uid in ["linkedin_url","orcid","openalex_id","email"]:
        v = (record.get(uid) or "").strip()
        if v: alias_map[v] = key


def _norm_name(name: str) -> str:
    low = name.lower()
    low = re.sub(r'\b(dr|prof|professor|mr|mrs|ms|phd|eng)\b\.?','',low)
    low = re.sub(r'\b(al|el|bin|bint|abu|ibn)\b','',low)
    low = re.sub(r'[^a-z\s]','',low)
    return " ".join(low.split())


def _norm_org(org: str) -> str:
    replacements = {
        "king abdullah university of science and technology":"kaust",
        "king abdulaziz city for science and technology":    "kacst",
        "saudi data and ai authority":                       "sdaia",
        "king abdulaziz university":                         "kau",
        "king saud university":                              "ksu",
        "king fahd university of petroleum and minerals":    "kfupm",
        "saudi aramco":                                      "aramco",
    }
    low = org.lower()
    for long, short in replacements.items():
        if long in low: return short
    return low.strip()