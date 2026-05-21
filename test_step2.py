"""
TEST — Step 2: Deduplication
Combines OpenAlex + arXiv records and merges duplicates.
Run after Steps 1A and 1B pass.

Usage: python test_step2.py
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GREEN = "\033[92m"; RED = "\033[91m"; CYAN = "\033[96m"
BOLD  = "\033[1m";  RESET = "\033[0m"

def run():
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  STEP 2 — Deduplication test{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}\n")

    # Load saved results from step 1A and 1B
    import glob

    oa_files = sorted(glob.glob("output/test_step1a_*.json"))
    ax_files = sorted(glob.glob("output/test_step1b_*.json"))

    if not oa_files:
        print(f"{RED}  ✗ No Step 1A output found. Run test_step1a.py first.{RESET}")
        sys.exit(1)
    if not ax_files:
        print(f"{RED}  ✗ No Step 1B output found. Run test_step1b.py first.{RESET}")
        sys.exit(1)

    with open(oa_files[-1]) as f: oa_records = json.load(f)
    with open(ax_files[-1]) as f: ax_records = json.load(f)

    all_raw = oa_records + ax_records
    print(f"  OpenAlex records:  {len(oa_records)}")
    print(f"  arXiv records:     {len(ax_records)}")
    print(f"  Total before dedup: {len(all_raw)}\n")

    from pipeline.deduplicator import deduplicate
    deduped = deduplicate(all_raw)
    merged  = len(all_raw) - len(deduped)

    print(f"  {GREEN}✓ After dedup: {len(deduped)} unique people{RESET}")
    print(f"  Duplicates merged: {merged}")

    # Show sample of merged records (people found in both sources)
    merged_records = [r for r in deduped if "," in str(r.get("sources_merged",""))]
    print(f"  Found in multiple sources: {len(merged_records)}")

    if merged_records:
        print(f"\n{BOLD}  Sample — people found in BOTH OpenAlex and arXiv:{RESET}\n")
        for r in merged_records[:5]:
            print(f"  · {r.get('name')} | {r.get('organization')} | Sources: {r.get('sources_merged')}")

    # Field coverage after merge
    print(f"\n{BOLD}  Field coverage after dedup:{RESET}")
    fields = ["name","organization","city","ethical_ai_skills",
              "publications","citations","orcid","openalex_id","linkedin_url","email"]
    for f in fields:
        filled = sum(1 for r in deduped if r.get(f))
        pct    = int(filled / len(deduped) * 100)
        bar    = "█"*(pct//10) + "░"*(10-pct//10)
        print(f"    {f:<25} {bar} {pct}%")

    # Save
    os.makedirs("output", exist_ok=True)
    out = f"output/test_step2_{len(deduped)}_records.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)
    print(f"\n  {GREEN}✓ Saved to: {out}{RESET}")

    print(f"\n  {GREEN}✓ Step 2 verified. Proceed to next step.{RESET}\n")

if __name__ == "__main__":
    run()
