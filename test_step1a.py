"""
TEST — Step 1A: OpenAlex WORKS scraper
Run this first. Verify the people collected are actually AI-relevant
before moving to any other step.

Usage: python test_step1a.py
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GREEN  = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"
CYAN   = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"

def run():
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  STEP 1A — OpenAlex WORKS scraper test{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"\n  Searching AI/ethical AI papers with Saudi authors...")
    print(f"  This takes ~3-5 minutes.\n")

    from scrapers.openalex_scraper import fetch_openalex_profiles
    records = fetch_openalex_profiles()

    if not records:
        print(f"{RED}  ✗ No records collected. Check network.{RESET}")
        return

    print(f"\n{BOLD}  Total collected: {len(records)}{RESET}")
    print(f"\n{'─'*60}")
    print(f"{BOLD}  SAMPLE — first 15 people:{RESET}")
    print(f"  (Read these and verify they are AI-relevant people){RESET}")
    print(f"{'─'*60}\n")

    for i, r in enumerate(records[:15], 1):
        print(f"  {BOLD}{i}. {r.get('name')}{RESET}")
        print(f"     Org:          {r.get('organization')} ({r.get('city')})")
        print(f"     Sector:       {r.get('sector')}")
        print(f"     AI skill tag: {r.get('ethical_ai_skills')}")
        print(f"     Recent paper: {r.get('recent_paper_title', '')[:80]}")
        print(f"     Journals:     {r.get('top_journals', '')[:80]}")
        print(f"     Papers:       {r.get('publications')} | Citations: {r.get('citations')}")
        print(f"     ORCID:        {r.get('orcid') or '—'}")
        print()

    print(f"{'─'*60}")
    print(f"\n{BOLD}  Field coverage:{RESET}")
    fields = ["name","organization","city","ethical_ai_skills",
              "recent_paper_title","top_journals","publications",
              "citations","orcid","openalex_id"]
    for f in fields:
        filled = sum(1 for r in records if r.get(f))
        pct    = int(filled / len(records) * 100)
        bar    = "█" * (pct // 10) + "░" * (10 - pct // 10)
        print(f"    {f:<25} {bar} {pct}%")

    # Save to JSON for inspection
    os.makedirs("output", exist_ok=True)
    out = f"output/test_step1a_{len(records)}_records.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"\n  {GREEN}Full results saved to: {out}{RESET}")

    # Human verification gate
    print(f"\n{'─'*60}")
    print(f"{BOLD}  HUMAN VERIFICATION{RESET}")
    print(f"  Look at the 15 people above.")
    print(f"  Do they look like AI/ethical AI researchers?")
    ans = input(f"  Type YES to confirm or NO to abort: ").strip().upper()
    if ans == "YES":
        print(f"\n  {GREEN}✓ Step 1A verified. Proceed to next step.{RESET}\n")
    else:
        print(f"\n  {RED}✗ Aborted. Fix the scraper before continuing.{RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    run()
