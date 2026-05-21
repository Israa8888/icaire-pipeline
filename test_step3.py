"""
TEST — Step 3: ORCID enrichment
Adds email, degree, experience years for people with ORCID IDs.
Run after Step 2 passes.

Usage: python test_step3.py
"""

import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GREEN = "\033[92m"; RED = "\033[91m"; CYAN = "\033[96m"
BOLD  = "\033[1m";  RESET = "\033[0m"

def run():
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  STEP 3 — ORCID enrichment test{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}\n")

    files = sorted(glob.glob("output/test_step2_*.json"))
    if not files:
        print(f"{RED}  ✗ No Step 2 output found. Run test_step2.py first.{RESET}")
        sys.exit(1)

    with open(files[-1]) as f:
        records = json.load(f)

    print(f"  Input: {len(records)} records")
    has_orcid = sum(1 for r in records if r.get("orcid"))
    print(f"  Records with ORCID: {has_orcid} ({int(has_orcid/len(records)*100)}%)")
    print(f"\n  Fetching ORCID profiles... (takes 5-10 min)")
    print(f"  Only fetching first 50 for test — full run does all.\n")

    # Test on first 50 only to keep it fast
    test_records = records[:50]
    rest_records = records[50:]

    from pipeline.orcid_enricher import enrich_with_orcid
    enriched_sample = enrich_with_orcid(test_records)
    enriched = enriched_sample + rest_records

    # Stats
    emails  = sum(1 for r in enriched_sample if r.get("email"))
    degrees = sum(1 for r in enriched_sample if r.get("degree"))
    exp     = sum(1 for r in enriched_sample if r.get("experience_years"))

    print(f"\n{BOLD}  Results from first 50 records:{RESET}")
    print(f"  Emails found:      {emails}")
    print(f"  Degrees found:     {degrees}")
    print(f"  Experience years:  {exp}")

    # Show sample with email
    print(f"\n{BOLD}  People with email found:{RESET}\n")
    email_records = [r for r in enriched_sample if r.get("email")]
    for r in email_records[:8]:
        print(f"  · {r.get('name')}")
        print(f"    Email:  {r.get('email')} (source: {r.get('email_source')})")
        print(f"    Degree: {r.get('degree') or '—'}")
        print(f"    Exp:    {r.get('experience_years') or '—'} years\n")

    if not email_records:
        print(f"  {RED}No emails found in first 50 records.{RESET}")
        print(f"  This may be normal — ORCID emails are only shown when public.")

    # Save full enriched
    out = f"output/test_step3_{len(enriched)}_records.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
    print(f"  {GREEN}✓ Saved to: {out}{RESET}")
    print(f"\n  {GREEN}✓ Step 3 done. Proceed to Step 4 (Claude classification).{RESET}\n")

if __name__ == "__main__":
    run()
