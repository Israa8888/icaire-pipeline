"""
test_scrapers.py — Run each scraper individually to verify it works
and see exactly what data it returns.

Usage:
  python test_scrapers.py --openalex     # test OpenAlex only
  python test_scrapers.py --orcid        # test ORCID only
  python test_scrapers.py --arxiv        # test arXiv only
  python test_scrapers.py --all          # test all three
"""

import sys
import os
import argparse
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def header(title):
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")

def success(msg): print(f"  {GREEN}✓{RESET} {msg}")
def error(msg):   print(f"  {RED}✗{RESET} {msg}")
def info(msg):    print(f"  {YELLOW}→{RESET} {msg}")

def print_records(records: list[dict], source: str, limit: int = 10):
    if not records:
        error(f"No records returned from {source}")
        return

    success(f"{len(records)} records collected from {source}")
    print(f"\n  {BOLD}Sample (first {min(limit, len(records))}):{RESET}")
    print(f"  {'─'*56}")

    for r in records[:limit]:
        name   = r.get('name', 'N/A')
        org    = r.get('organization', 'N/A')
        title  = r.get('title', 'N/A')
        city   = r.get('city', 'N/A')
        sub    = r.get('ai_subfield', 'N/A')
        papers = r.get('publications', 0)
        orcid  = r.get('orcid', '')
        email  = r.get('email', '')

        print(f"\n  {BOLD}{name}{RESET}")
        print(f"    Title:       {title}")
        print(f"    Org:         {org} ({city})")
        print(f"    AI subfield: {sub}")
        print(f"    Papers:      {papers}")
        if orcid:  print(f"    ORCID:       {orcid}")
        if email:  print(f"    Email:       {email}")

    if len(records) > limit:
        print(f"\n  ... and {len(records) - limit} more records")

    print(f"\n  {BOLD}Field coverage:{RESET}")
    fields = ['name','title','organization','city','ai_subfield',
              'publications','email','orcid','linkedin_url','openalex_id']
    for field in fields:
        filled = sum(1 for r in records if r.get(field))
        pct    = int(filled / len(records) * 100)
        bar    = '█' * (pct // 10) + '░' * (10 - pct // 10)
        print(f"    {field:<20} {bar} {pct}%")


def save_to_json(records: list[dict], source: str):
    os.makedirs("output", exist_ok=True)
    filename = f"output/test_{source}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    success(f"Full results saved to: {filename}")


# ── Individual scraper tests ──────────────────────────────────────────────────

def test_openalex():
    header("OpenAlex Scraper Test")
    info("Source: api.openalex.org — academic researchers at Saudi institutions")
    info("Free, no API key needed")
    info("Starting... (takes ~2-3 min)")
    print()

    try:
        from scrapers.openalex_scraper import fetch_openalex_profiles
        records = fetch_openalex_profiles()
        print_records(records, "OpenAlex")
        if records:
            save_to_json(records, "openalex")
        return len(records) > 0
    except Exception as e:
        error(f"OpenAlex scraper crashed: {e}")
        import traceback; traceback.print_exc()
        return False


def test_orcid():
    header("ORCID Scraper Test")
    info("Source: pub.orcid.org — verified researcher profiles")
    info("Free, no API key needed")
    info("Starting... (takes ~3-5 min)")
    print()

    try:
        from scrapers.orcid_scraper import fetch_orcid_profiles
        records = fetch_orcid_profiles()
        print_records(records, "ORCID")
        if records:
            save_to_json(records, "orcid")
        return len(records) > 0
    except Exception as e:
        error(f"ORCID scraper crashed: {e}")
        import traceback; traceback.print_exc()
        return False


def test_arxiv():
    header("arXiv Scraper Test")
    info("Source: export.arxiv.org — AI paper authors at Saudi institutions")
    info("Free, no API key needed")
    info("Starting... (takes ~5-8 min due to rate limit delays)")
    print()

    try:
        from scrapers.arxiv_scraper import fetch_arxiv_profiles
        records = fetch_arxiv_profiles(max_results_per_query=30)  # smaller for test
        print_records(records, "arXiv")
        if records:
            save_to_json(records, "arxiv")
        return len(records) > 0
    except Exception as e:
        error(f"arXiv scraper crashed: {e}")
        import traceback; traceback.print_exc()
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test individual scrapers")
    parser.add_argument("--openalex", action="store_true", help="Test OpenAlex scraper")
    parser.add_argument("--orcid",    action="store_true", help="Test ORCID scraper")
    parser.add_argument("--arxiv",    action="store_true", help="Test arXiv scraper")
    parser.add_argument("--all",      action="store_true", help="Test all scrapers")
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        print(f"\n{YELLOW}Examples:{RESET}")
        print("  python test_scrapers.py --openalex")
        print("  python test_scrapers.py --orcid")
        print("  python test_scrapers.py --arxiv")
        print("  python test_scrapers.py --all")
        sys.exit(0)

    results = {}

    if args.openalex or args.all:
        results["OpenAlex"] = test_openalex()

    if args.orcid or args.all:
        results["ORCID"] = test_orcid()

    if args.arxiv or args.all:
        results["arXiv"] = test_arxiv()

    if len(results) > 1:
        header("SUMMARY")
        for source, passed in results.items():
            status = f"{GREEN}WORKING{RESET}" if passed else f"{RED}FAILED{RESET}"
            print(f"  {source:<12} {status}")
        print()
