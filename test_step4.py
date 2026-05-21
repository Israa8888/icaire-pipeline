"""
TEST — Step 4: Claude API classification
Tests on 10 people only to verify quality before full run.
Run after Step 3 passes.

Usage: python test_step4.py
"""

import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GREEN = "\033[92m"; RED = "\033[91m"; CYAN = "\033[96m"
BOLD  = "\033[1m";  RESET = "\033[0m"

def run():
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  STEP 4 — Claude classification test (10 people){RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}\n")

    from config.settings import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        print(f"{RED}  ✗ ANTHROPIC_API_KEY not set in .env{RESET}")
        sys.exit(1)
    print(f"  {GREEN}✓ Anthropic API key found{RESET}")

    files = sorted(glob.glob("output/test_step3_*.json"))
    if not files:
        print(f"{RED}  ✗ No Step 3 output. Run test_step3.py first.{RESET}")
        sys.exit(1)

    with open(files[-1]) as f:
        records = json.load(f)

    # Pick 10 diverse people for testing
    # Mix of orgs, sectors, skill tags
    test_records = records[:10]

    print(f"  Classifying 10 people with Claude API...")
    print(f"  Cost: ~$0.01\n")

    from pipeline.classifier import classify
    classified = classify(test_records)

    print(f"\n{'─'*60}")
    print(f"{BOLD}  Classification results:{RESET}\n")

    all_good = True
    for r in classified:
        name    = r.get("name","")
        org     = r.get("organization","")
        domains = r.get("unesco_domains","")
        subs    = r.get("unesco_sub_areas","")
        skills  = r.get("ethical_ai_skills","")
        tier    = r.get("tier","")
        score   = r.get("priority_score","")
        rel     = r.get("ai_relationship","")
        degree  = r.get("degree","")

        print(f"  {BOLD}{name}{RESET} | {org}")
        print(f"    UNESCO domain(s):   {domains or RED+'MISSING'+RESET}")
        print(f"    UNESCO sub-area(s): {subs or RED+'MISSING'+RESET}")
        print(f"    Ethical AI skills:  {skills or RED+'MISSING'+RESET}")
        print(f"    AI relationship:    {rel or RED+'MISSING'+RESET}")
        print(f"    Tier: {tier} | Score: {score} | Degree: {degree or '—'}")
        print()

        if not domains or domains == "Not relevant":
            all_good = False

    print(f"{'─'*60}")

    if all_good:
        print(f"\n  {GREEN}✓ Classification looks good — UNESCO domains assigned{RESET}")
    else:
        print(f"\n  {RED}✗ Some records missing UNESCO domains — check classifier{RESET}")

    # Save
    out = f"output/test_step4_classified.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(classified, f, ensure_ascii=False, indent=2)
    print(f"  {GREEN}✓ Saved to: {out}{RESET}")

    print(f"\n{'─'*60}")
    print(f"{BOLD}  HUMAN VERIFICATION{RESET}")
    print(f"  Do the UNESCO domains and ethical AI skills look accurate?")
    ans = input(f"  Type YES to confirm or NO to abort: ").strip().upper()
    if ans == "YES":
        print(f"\n  {GREEN}✓ Step 4 verified. Ready for full pipeline run.{RESET}\n")
    else:
        print(f"\n  {RED}✗ Aborted. Review classifier prompt.{RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    run()
