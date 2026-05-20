"""
Pipeline Step — Push to Google Sheets
Rows = people (one person per row)
Columns = fields (name, title, degree, ...)
Never overwrites manual fields.
"""

import logging
from datetime import datetime, timezone
import gspread
from google.oauth2.service_account import Credentials
from config.settings import (
    GOOGLE_CREDS_PATH, GOOGLE_SHEET_ID, DRY_RUN,
    SHEET_TAB_CONNECTIONS, SHEET_TAB_SCORING, SHEET_TAB_LOG,
    SHEET_COLUMNS,
)

logger = logging.getLogger(__name__)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
MANUAL_FIELDS = {
    "connection_status","connection_type",
    "outreach_notes","meeting_done","added_by"
}


def push_to_sheets(records: list[dict], run_stats: dict) -> None:
    if DRY_RUN:
        _dry_run_summary(records); return

    gc    = _get_client()
    sheet = gc.open_by_key(GOOGLE_SHEET_ID)
    _ensure_tabs(sheet)
    added, updated = _upsert(sheet, records)
    _write_log(sheet, run_stats, added, updated)
    _write_scoring_guide(sheet)
    logger.info(f"Sheets: {added} added, {updated} updated.")


def _get_client():
    creds = Credentials.from_service_account_file(GOOGLE_CREDS_PATH, scopes=SCOPES)
    return gspread.authorize(creds)


def _ensure_tabs(sheet) -> None:
    existing = [ws.title for ws in sheet.worksheets()]
    for tab in [SHEET_TAB_CONNECTIONS, SHEET_TAB_SCORING, SHEET_TAB_LOG]:
        if tab not in existing:
            sheet.add_worksheet(title=tab, rows=3000, cols=40)
            logger.info(f"Created tab: {tab}")
    ws = sheet.worksheet(SHEET_TAB_CONNECTIONS)
    if not ws.row_values(1):
        # Header row — human-readable labels
        headers = [_col_label(c) for c in SHEET_COLUMNS]
        ws.append_row(headers, value_input_option="RAW")
        # Freeze header row
        ws.freeze(rows=1)
        logger.info("Header row written and frozen.")


def _col_label(col: str) -> str:
    labels = {
        "name":"Name","title":"Title / Role","degree":"Degree",
        "experience_years":"Experience (years)","organization":"Organization",
        "org_type":"Org type","sector":"Sector","industry_area":"Industry area",
        "city":"City","country":"Country","latitude":"Latitude","longitude":"Longitude",
        "email":"Email","email_source":"Email source","linkedin_url":"LinkedIn URL",
        "orcid":"ORCID","openalex_id":"OpenAlex ID",
        "publications":"Publications","citations":"Citations",
        "publication_types":"Publication types","top_journals":"Top journals",
        "recent_paper_title":"Most recent paper",
        "unesco_domains":"UNESCO domain(s)","unesco_sub_areas":"UNESCO sub-area(s)",
        "ethical_ai_skills":"Ethical AI skill(s)","ai_relationship":"AI relationship",
        "tier":"Tier","priority_score":"Priority score",
        "connection_status":"Connection status","connection_type":"Connection type",
        "outreach_notes":"Outreach notes","meeting_done":"Meeting done",
        "sources_merged":"Sources","added_by":"Added by","last_updated":"Last updated",
    }
    return labels.get(col, col.replace("_"," ").title())


def _upsert(sheet, records: list[dict]) -> tuple[int,int]:
    ws       = sheet.worksheet(SHEET_TAB_CONNECTIONS)
    all_rows = ws.get_all_records()
    added = updated = 0

    # Build lookup indexes
    li_idx     = {r.get("LinkedIn URL","").strip(): i
                  for i,r in enumerate(all_rows) if r.get("LinkedIn URL")}
    orcid_idx  = {r.get("ORCID","").strip(): i
                  for i,r in enumerate(all_rows) if r.get("ORCID")}
    oa_idx     = {r.get("OpenAlex ID","").strip(): i
                  for i,r in enumerate(all_rows) if r.get("OpenAlex ID")}
    email_idx  = {r.get("Email","").strip(): i
                  for i,r in enumerate(all_rows) if r.get("Email")}
    nameorg_idx= {f"{r.get('Name','').lower()}_{r.get('Organization','').lower()}": i
                  for i,r in enumerate(all_rows)}

    rows_to_add = []
    updates     = []

    for record in records:
        existing_idx = _find_row(record, li_idx, orcid_idx, oa_idx,
                                 email_idx, nameorg_idx)
        if existing_idx is not None:
            existing = all_rows[existing_idx]
            merged   = _merge_for_update(existing, record)
            updates.append((existing_idx + 2, merged))
            updated += 1
        else:
            rows_to_add.append([_safe(record.get(col)) for col in SHEET_COLUMNS])
            added += 1

    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option="USER_ENTERED")
    for row_num, merged in updates:
        ws.update(f"A{row_num}", [[_safe(merged.get(_col_label(col),
                                          merged.get(col,"")))
                                   for col in SHEET_COLUMNS]])

    return added, updated


def _find_row(record, li_idx, orcid_idx, oa_idx, email_idx, nameorg_idx):
    checks = [
        (record.get("linkedin_url","").strip(), li_idx),
        (record.get("orcid","").strip(),        orcid_idx),
        (record.get("openalex_id","").strip(),  oa_idx),
        (record.get("email","").strip(),        email_idx),
    ]
    for val, idx in checks:
        if val and val in idx: return idx[val]
    key = f"{record.get('name','').lower()}_{record.get('organization','').lower()}"
    return nameorg_idx.get(key)


def _merge_for_update(existing: dict, new: dict) -> dict:
    merged = dict(existing)
    for field, val in new.items():
        label = _col_label(field)
        if field in MANUAL_FIELDS or label in MANUAL_FIELDS:
            continue
        if field in {"publications","citations","priority_score"}:
            try:
                merged[label] = max(int(merged.get(label,0) or 0),
                                    int(val or 0))
            except (ValueError, TypeError): pass
            continue
        # Multi-value fields — merge sets
        if field in {"unesco_domains","unesco_sub_areas","ethical_ai_skills"}:
            existing_set = set(str(merged.get(label,"")).split(", "))
            new_set      = set(str(val or "").split(", "))
            existing_set.discard(""); new_set.discard("")
            merged[label] = ", ".join(sorted(existing_set | new_set))
            continue
        if val and not merged.get(label):
            merged[label] = val
    merged[_col_label("last_updated")] = \
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return merged


def _write_log(sheet, run_stats, added, updated):
    ws = sheet.worksheet(SHEET_TAB_LOG)
    if not ws.row_values(1):
        ws.append_row(["Timestamp","Records raw","Duplicates merged",
                       "Added","Updated","Errors","Sources"])
    ws.append_row([
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        run_stats.get("total_raw",0),
        run_stats.get("duplicates_merged",0),
        added, updated,
        run_stats.get("errors",0),
        run_stats.get("sources",""),
    ])


def _write_scoring_guide(sheet):
    ws = sheet.worksheet(SHEET_TAB_SCORING)
    if ws.row_values(1): return
    rows = [
        ["Score band","Label","What it means","Recommended action"],
        ["90–100","Priority","Senior + strong research + ethical AI focus + Riyadh","Contact this week"],
        ["70–89","Strong pipeline","Good signals in 2 of 3 goal areas","Contact this month"],
        ["50–69","Warm","Relevant but missing a key signal","Follow up next quarter"],
        ["30–49","Monitor","In the ecosystem, not yet a clear fit","Keep, revisit later"],
        ["0–29","Low signal","Incomplete profile or weak ethical AI connection","Review next cycle"],
        [],
        ["Signal","Max points","How measured"],
        ["Title seniority","15","CEO/Prof/Director=15, Manager/Lead=10, Engineer/Researcher=5"],
        ["Org recognition","15","SDAIA/KAUST/Aramco=15, known startup=10, unknown=3"],
        ["Ethical AI relevance","15","Explicit ethics focus=15, applied AI=8, general AI=3"],
        ["Publication count","15","10+ papers=15, 3-9=10, 1-2=5, none=0"],
        ["Public presence","10","Conference talks or posts=10, some=5, none=0"],
        ["Location","10","Riyadh=10, KSA other=7, GCC=4"],
        ["Contact availability","10","Email found=10, LinkedIn only=6, neither=0"],
        ["Profile completeness","10","3+ sources merged=10, 2=7, 1=3"],
        [],
        ["UNESCO domains","","Education / Natural Sciences / Social & Human Sciences / Culture / Communication & Information"],
        ["Ethical AI skills","","Examples: AI ethics, NLP, algorithmic fairness, XAI, AI policy, generative AI, etc. Not exhaustive."],
        ["AI relationship","","Primary AI = AI is main field | Adjacent AI = uses AI in another field"],
        ["Tier 1","Speaker","Strong public voice, gives talks, senior title"],
        ["Tier 2","Partner","Decision maker at AI-relevant org"],
        ["Tier 3","Research","Publishes AI research, university or research lab"],
    ]
    ws.update("A1", rows)


def _safe(val) -> str:
    if val is None: return ""
    return str(val)


def _dry_run_summary(records):
    print("\n── DRY RUN SUMMARY ─────────────────────────────────────────")
    print(f"  Total records to push: {len(records)}")
    for r in records[:8]:
        print(f"  · {r.get('name')} | {r.get('organization')} | "
              f"Tier {r.get('tier')} | Score {r.get('priority_score')} | "
              f"{r.get('unesco_domains','')}")
    if len(records) > 8:
        print(f"  ... and {len(records)-8} more")
    print("────────────────────────────────────────────────────────────\n")
