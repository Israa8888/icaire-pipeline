"""
TEST — Step 1C: Google Custom Search (LinkedIn profiles)
Run after Step 1B passes.
Covers industry + government people not in academic databases.

Usage: python test_step1c.py
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"
CYAN  = "\033[96m"; BOLD = "\033[1m";  RESET = "\033[0m"

def run():
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  STEP 1C — Google CSE / LinkedIn scraper test{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}\n")

    APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")
    if not APIFY_API_KEY:
        print(f"{RED}  ✗ Google CSE credentials not set in .env{RESET}")
        print(f"  Add GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX to your .env file")
        sys.exit(1)

    print(f"  {GREEN}✓ Google CSE credentials found{RESET}")
    print(f"  Searching LinkedIn for Saudi AI professionals...")
    print(f"  This takes ~3-5 minutes.\n")

    from scrapers.google_search_scraper import fetch_google_profiles
    records = fetch_google_profiles()

    if not records:
        print(f"{RED}  ✗ No records. Check credentials and CSE setup.{RESET}")
        return

    print(f"\n{BOLD}  Total collected: {len(records)}{RESET}")
    print(f"\n{'─'*60}")
    print(f"{BOLD}  SAMPLE — first 15 people:{RESET}\n")

    for i, r in enumerate(records[:15], 1):
        print(f"  {BOLD}{i}. {r.get('name')}{RESET}")
        print(f"     Title:    {r.get('title','—')[:60]}")
        print(f"     Org:      {r.get('organization','—')}")
        print(f"     LinkedIn: {r.get('linkedin_url','—')}\n")

    print(f"{'─'*60}")
    print(f"\n{BOLD}  Field coverage:{RESET}")
    for f in ["name","title","organization","linkedin_url","city"]:
        filled = sum(1 for r in records if r.get(f))
        pct    = int(filled / len(records) * 100)
        bar    = "█"*(pct//10) + "░"*(10-pct//10)
        print(f"    {f:<25} {bar} {pct}%")

    os.makedirs("output", exist_ok=True)
    out = f"output/test_step1c_{len(records)}_records.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"\n  {GREEN}✓ Saved to: {out}{RESET}")

    print(f"\n{'─'*60}")
    print(f"{BOLD}  HUMAN VERIFICATION{RESET}")
    print(f"  Do these look like real Saudi AI professionals from LinkedIn?")
    print(f"  Check: are titles and orgs making sense?")
    ans = input(f"  Type YES to confirm or NO to abort: ").strip().upper()
    if ans == "YES":
        print(f"\n  {GREEN}✓ Step 1C verified. Proceed to next step.{RESET}\n")
    else:
        print(f"\n  {RED}✗ Aborted.{RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    run()
