"""
tests/test_pipeline.py
──────────────────────────────────────────────────────────────────────────────
Run after EACH step to confirm it works before moving to the next.

Usage:
  python tests/test_pipeline.py --step 1    # test scrapers only
  python tests/test_pipeline.py --step 2    # test deduplication
  python tests/test_pipeline.py --step 3    # test enrichment
  python tests/test_pipeline.py --step 4    # test Claude classifier
  python tests/test_pipeline.py --step 5    # test Sheets push (dry run)
  python tests/test_pipeline.py --all       # run everything
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
import json
import argparse
import logging
from datetime import datetime

logging.basicConfig(level=logging.WARNING)  # suppress info noise during tests

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}"); return False
def warn(msg): print(f"  {YELLOW}⚠{RESET} {msg}")
def section(title): print(f"\n{BOLD}{CYAN}── {title} {'─'*(52-len(title))}{RESET}")
def result(passed): 
    if passed: print(f"  {GREEN}{BOLD}PASSED{RESET}")
    else:       print(f"  {RED}{BOLD}FAILED — fix this before moving on{RESET}")
    return passed


# ── STEP 1: Scraper tests (uses mock data, no real API calls) ─────────────────
def test_step1_scrapers():
    section("STEP 1 — Scrapers (mock / connectivity check)")
    passed = True

    # Test 1a: Semantic Scholar (real call — free, no key)
    print("  Testing Semantic Scholar API connectivity...")
    try:
        from semanticscholar import SemanticScholar
        sch = SemanticScholar()
        results = sch.search_author("machine learning KAUST", limit=2)
        results_list = list(results)
        if len(results_list) >= 0:
            ok(f"Semantic Scholar API reachable — got {len(results_list)} results")
        else:
            warn("Semantic Scholar returned 0 results (may be a query issue)")
    except Exception as e:
        fail(f"Semantic Scholar failed: {e}")
        passed = False

    # Test 1b: arXiv API (real call — free, no key)
    print("  Testing arXiv API connectivity...")
    try:
        import arxiv
        client = arxiv.Client()
        search = arxiv.Search(query="cat:cs.AI AND Saudi", max_results=2)
        papers = list(client.results(search))
        ok(f"arXiv API reachable — got {len(papers)} papers")
    except Exception as e:
        fail(f"arXiv API failed: {e}")
        passed = False

    # Test 1c: Web scraper (mock — just checks BS4 parses HTML)
    print("  Testing BeautifulSoup HTML parsing...")
    try:
        from bs4 import BeautifulSoup
        sample_html = """
        <div class="faculty-member">
          <h3>Dr. Sara Al-Amri</h3>
          <p class="role">Assistant Professor — Machine Learning</p>
        </div>"""
        soup = BeautifulSoup(sample_html, "lxml")
        name = soup.find("h3").get_text(strip=True)
        assert "Sara" in name
        ok(f"BeautifulSoup parsing works — extracted: '{name}'")
    except Exception as e:
        fail(f"BeautifulSoup test failed: {e}")
        passed = False

    # Test 1d: LinkedIn credentials present (does NOT log in)
    print("  Checking LinkedIn credentials in .env...")
    from config.settings import LINKEDIN_EMAIL, LINKEDIN_PASSWORD
    if LINKEDIN_EMAIL and LINKEDIN_PASSWORD:
        ok(f"LinkedIn credentials found ({LINKEDIN_EMAIL})")
    else:
        warn("LinkedIn credentials missing — LinkedIn scraper will be skipped.")
        warn("Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in your .env file.")

    result(passed)
    return passed


# ── STEP 2: Deduplication tests ───────────────────────────────────────────────
def test_step2_dedup():
    section("STEP 2 — Deduplication")
    from pipeline.deduplicator import deduplicate, _normalise_name, _normalise_org
    passed = True

    # Test 2a: Exact LinkedIn URL match
    records = [
        {"name": "Sara Al-Amri",  "organization": "KAUST", "linkedin_url": "linkedin.com/in/sara", "source": "linkedin"},
        {"name": "Sarah Al Amri", "organization": "KAUST", "linkedin_url": "linkedin.com/in/sara", "publications": 5, "source": "semantic_scholar"},
    ]
    result_list = deduplicate(records)
    if len(result_list) == 1:
        ok("Exact LinkedIn URL dedup works — 2 records merged into 1")
        if result_list[0].get("publications") == 5:
            ok("Merge fills empty fields from second source")
        else:
            fail("Merge did not fill publications field"); passed = False
    else:
        fail(f"Expected 1 record, got {len(result_list)}"); passed = False

    # Test 2b: Fuzzy name + org match
    records2 = [
        {"name": "Dr. Ahmed Al-Ghamdi",   "organization": "SDAIA",  "source": "linkedin"},
        {"name": "Ahmed Alghamdi",         "organization": "SDAIA",  "source": "arxiv"},
    ]
    result2 = deduplicate(records2)
    if len(result2) == 1:
        ok("Fuzzy name match works — 'Dr. Ahmed Al-Ghamdi' = 'Ahmed Alghamdi' @ SDAIA")
    else:
        fail(f"Fuzzy dedup failed — got {len(result2)} records, expected 1"); passed = False

    # Test 2c: Different people, same name different org — must NOT merge
    records3 = [
        {"name": "Mohammed Al-Rashid", "organization": "KAUST",  "source": "linkedin"},
        {"name": "Mohammed Al-Rashid", "organization": "Aramco", "source": "semantic_scholar"},
    ]
    result3 = deduplicate(records3)
    if len(result3) == 2:
        ok("Correctly kept 2 people with same name but different orgs")
    else:
        fail(f"False merge: same name different org should stay separate"); passed = False

    # Test 2d: Manual fields are preserved
    records4 = [
        {"name": "Fatima", "organization": "KSU", "source": "linkedin",
         "status": "Connected", "outreach_notes": "Met at LEAP 2025",
         "linkedin_url": "linkedin.com/in/fatima"},
        {"name": "Fatima", "organization": "KSU", "source": "arxiv",
         "status": "Not contacted", "outreach_notes": "",
         "linkedin_url": "linkedin.com/in/fatima", "publications": 8},
    ]
    result4 = deduplicate(records4)
    if result4[0].get("status") == "Connected":
        ok("Manual field 'status' preserved after merge (not overwritten)")
    else:
        fail("Manual field 'status' was overwritten — BUG!"); passed = False
    if result4[0].get("outreach_notes") == "Met at LEAP 2025":
        ok("Manual field 'outreach_notes' preserved")
    else:
        fail("outreach_notes was overwritten"); passed = False

    # Test 2e: Name normalisation
    assert _normalise_name("Dr. Sara Al-Amri") == _normalise_name("sara alamri"), \
        "Name normalisation failed"
    ok("Name normalisation strips titles and particles correctly")

    result(passed)
    return passed


# ── STEP 3: Enrichment tests ──────────────────────────────────────────────────
def test_step3_enrichment():
    section("STEP 3 — Enrichment")
    from pipeline.enricher import enrich
    passed = True

    sample = [
        {"name": "Sara Al-Amri",    "organization": "KAUST", "city": "Thuwal",  "source": "linkedin"},
        {"name": "Ahmed Al-Ghamdi", "organization": "SDAIA", "city": "Riyadh",  "source": "arxiv"},
        {"name": "Maha Khalid",     "organization": "Mozn",  "city": "Riyadh",  "source": "linkedin",
         "email": "maha@mozn.ai"},
    ]

    enriched = enrich(sample)

    # Check lat/long added
    thuwal = next(r for r in enriched if r["city"] == "Thuwal")
    if thuwal.get("latitude") and thuwal.get("longitude"):
        ok(f"Lat/long added for Thuwal: {thuwal['latitude']}, {thuwal['longitude']}")
    else:
        fail("Lat/long not added for Thuwal"); passed = False

    # Check default status set
    for r in enriched:
        if r.get("status") != "Not contacted":
            fail(f"Default status not set for {r['name']}"); passed = False; break
    else:
        ok("Default status 'Not contacted' set on all records")

    # Check existing email preserved
    maha = next(r for r in enriched if r["name"] == "Maha Khalid")
    if maha.get("email") == "maha@mozn.ai":
        ok("Existing email preserved (not overwritten by Hunter.io)")
    else:
        fail("Email was overwritten!"); passed = False

    # Check timestamp added
    if all(r.get("last_updated") for r in enriched):
        ok("last_updated timestamp added to all records")
    else:
        fail("last_updated missing on some records"); passed = False

    result(passed)
    return passed


# ── STEP 4: Claude classifier test ───────────────────────────────────────────
def test_step4_classifier():
    section("STEP 4 — Claude API Classifier")
    from config.settings import ANTHROPIC_API_KEY
    passed = True

    if not ANTHROPIC_API_KEY:
        warn("ANTHROPIC_API_KEY not set — skipping classifier test.")
        warn("Set it in .env and re-run.")
        return True   # don't fail the whole suite

    # Test with 2 records only to keep cost minimal
    sample = [
        {
            "name": "Dr. Sara Al-Amri",
            "title": "Assistant Professor",
            "organization": "KAUST",
            "city": "Thuwal",
            "publications": 14,
            "h_index": 8,
            "email": "s.alamri@kaust.edu.sa",
            "linkedin_url": "linkedin.com/in/sara-alamri",
            "sources_merged": "linkedin,semantic_scholar,arxiv",
        },
        {
            "name": "Ahmed Al-Ghamdi",
            "title": "Head of AI",
            "organization": "SDAIA",
            "city": "Riyadh",
            "publications": 0,
            "h_index": 0,
            "email": "",
            "linkedin_url": "linkedin.com/in/ahmed-alghamdi",
            "sources_merged": "linkedin",
        },
    ]

    print("  Calling Claude API with 2 test profiles (minimal cost)...")
    try:
        from pipeline.classifier import classify
        classified = classify(sample)
    except Exception as e:
        fail(f"Classifier threw exception: {e}"); return False

    if len(classified) != 2:
        fail(f"Expected 2 classified records, got {len(classified)}"); passed = False
    else:
        ok(f"Classifier returned {len(classified)} records")

    for r in classified:
        tier  = r.get("tier")
        score = r.get("priority_score")
        subf  = r.get("ai_subfield")

        if tier in [1, 2, 3]:
            ok(f"  {r['name']}: Tier {tier} | Score {score} | Subfield: {subf}")
        else:
            fail(f"  {r['name']}: invalid tier '{tier}'"); passed = False

        if isinstance(score, (int, float)) and 0 <= score <= 100:
            ok(f"  Score {score} is in valid range 0–100")
        else:
            fail(f"  Score '{score}' is out of range or wrong type"); passed = False

    result(passed)
    return passed


# ── STEP 5: Google Sheets dry-run test ───────────────────────────────────────
def test_step5_sheets():
    section("STEP 5 — Google Sheets (dry run)")
    from config.settings import GOOGLE_SHEET_ID, GOOGLE_CREDS_PATH
    import os
    passed = True

    if not GOOGLE_SHEET_ID:
        warn("GOOGLE_SHEET_ID not set — skipping Sheets test.")
        warn("Follow README Step 3 to set this up.")
        return True

    if not os.path.exists(GOOGLE_CREDS_PATH):
        warn(f"Google credentials file not found at {GOOGLE_CREDS_PATH}")
        warn("Follow README Step 3 to download your service account JSON.")
        return True

    # Test connectivity
    print("  Testing Google Sheets API connection...")
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_file(
            GOOGLE_CREDS_PATH,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        gc    = gspread.authorize(creds)
        sheet = gc.open_by_key(GOOGLE_SHEET_ID)
        ok(f"Connected to Google Sheet: '{sheet.title}'")
    except Exception as e:
        fail(f"Sheets connection failed: {e}")
        warn("Make sure you shared the sheet with your service account email.")
        return False

    # Dry run push
    print("  Running dry-run push (no writes)...")
    import os
    os.environ["DRY_RUN"] = "true"
    sample = [
        {
            "name": "Test Person", "title": "Professor", "organization": "KAUST",
            "org_type": "university", "ai_subfield": "NLP", "sector": "academia",
            "tier": 3, "priority_score": 85,
            "city": "Thuwal", "country": "Saudi Arabia",
            "latitude": 22.3025, "longitude": 39.1036,
            "linkedin_url": "linkedin.com/in/test", "email": "test@kaust.edu.sa",
            "orcid": "", "semantic_scholar_id": "12345",
            "publications": 10, "h_index": 5,
            "sources_merged": "linkedin,semantic_scholar",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "status": "Not contacted", "outreach_notes": "",
            "meeting_done": "No", "added_by": "pipeline",
        }
    ]
    try:
        from pipeline.push_to_sheets import push_to_sheets
        push_to_sheets(sample, {"total_raw": 1, "duplicates_merged": 0, "errors": 0})
        ok("Dry run push completed without errors")
    except Exception as e:
        fail(f"Dry run push failed: {e}"); passed = False

    result(passed)
    return passed


# ── Main runner ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ICAIRE Pipeline Test Suite")
    parser.add_argument("--step", type=int, choices=[1, 2, 3, 4, 5],
                        help="Run a specific step test")
    parser.add_argument("--all", action="store_true", help="Run all step tests")
    args = parser.parse_args()

    print(f"\n{BOLD}ICAIRE Pipeline — Test Suite{RESET}")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    steps = {
        1: test_step1_scrapers,
        2: test_step2_dedup,
        3: test_step3_enrichment,
        4: test_step4_classifier,
        5: test_step5_sheets,
    }

    if args.all:
        results = {s: fn() for s, fn in steps.items()}
        section("FULL SUITE SUMMARY")
        all_passed = True
        for step_num, passed in results.items():
            status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
            print(f"  Step {step_num}: {status}")
            if not passed:
                all_passed = False
        print()
        if all_passed:
            print(f"{GREEN}{BOLD}All tests passed. Pipeline is ready.{RESET}\n")
        else:
            print(f"{RED}{BOLD}Some tests failed. Fix them before running the full pipeline.{RESET}\n")
        sys.exit(0 if all_passed else 1)

    elif args.step:
        passed = steps[args.step]()
        sys.exit(0 if passed else 1)

    else:
        parser.print_help()
        print("\nTip: run --step 1 first, then --step 2, and so on.\n")
