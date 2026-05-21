"""
TEST — Step 1B: arXiv scraper
Run after Step 1A passes.

Usage: python test_step1b.py
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GREEN = "\033[92m"; RED = "\033[91m"; CYAN = "\033[96m"
BOLD  = "\033[1m";  RESET = "\033[0m"

def run():
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  STEP 1B — arXiv scraper test{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"\n  Searching AI papers with Saudi institution in abstract...")
    print(f"  This takes ~5-8 minutes (rate limit delays between queries).\n")

    from scrapers.arxiv_scraper import fetch_arxiv_profiles
    records = fetch_arxiv_profiles(max_per_query=50)

    if not records:
        print(f"{RED}  ✗ No records. Check network.{RESET}")
        return

    print(f"\n{BOLD}  Total collected: {len(records)}{RESET}")
    print(f"\n{'─'*60}")
    print(f"{BOLD}  SAMPLE — first 15 people:{RESET}\n")

    for i, r in enumerate(records[:15], 1):
        print(f"  {BOLD}{i}. {r.get('name')}{RESET}")
        print(f"     Org:      {r.get('organization')} ({r.get('city')})")
        print(f"     Subfield: {r.get('ethical_ai_skills')}")
        print(f"     Source:   arXiv\n")

    print(f"{'─'*60}")
    print(f"\n{BOLD}  Field coverage:{RESET}")
    for f in ["name","organization","city","ethical_ai_skills"]:
        filled = sum(1 for r in records if r.get(f))
        pct    = int(filled / len(records) * 100)
        bar    = "█"*(pct//10) + "░"*(10-pct//10)
        print(f"    {f:<25} {bar} {pct}%")

    os.makedirs("output", exist_ok=True)
    out = f"output/test_step1b_{len(records)}_records.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"\n  {GREEN}✓ Saved to: {out}{RESET}")

    print(f"\n{'─'*60}")
    print(f"{BOLD}  HUMAN VERIFICATION{RESET}")
    print(f"  Do the names and paper subfields look like real AI researchers?")
    ans = input(f"  Type YES to confirm or NO to abort: ").strip().upper()
    if ans == "YES":
        print(f"\n  {GREEN}✓ Step 1B verified. Proceed to next step.{RESET}\n")
    else:
        print(f"\n  {RED}✗ Aborted.{RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    run()
