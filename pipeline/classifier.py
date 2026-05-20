"""
Pipeline Step — Claude API Classifier
Assigns to each person:
  - unesco_domains (list — can be multiple)
  - unesco_sub_areas (list — can be multiple)
  - ethical_ai_skills (list — examples not exhaustive)
  - ai_relationship (Primary AI / Adjacent AI)
  - org_type
  - sector
  - industry_area
  - tier (1/2/3)
  - priority_score (0-100)
  - degree (if not already set)
  - experience_years (if not already set)

UNESCO domains based on actual paper topics + arXiv categories.
Claude can assign MULTIPLE domains if the person fits more than one.
"""

import json, logging, time
from anthropic import Anthropic
from config.settings import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)
client = Anthropic(api_key=ANTHROPIC_API_KEY)
BATCH_SIZE = 8

SYSTEM_PROMPT = """You are a research analyst for ICAIRE, an ethical AI research institute in Riyadh.
Your job is to classify AI professionals in Saudi Arabia for a connection list focused on ETHICAL AI.

The overarching theme is UNESCO's Recommendation on the Ethics of AI (2021).

UNESCO DOMAINS (a person can fit MULTIPLE — assign all that apply):
1. Education — AI in learning, teaching, EdTech, AI literacy, digital skills, higher education policy
2. Natural Sciences — AI in climate, water, ocean, ecology, bioinformatics, health, energy, disaster risk
3. Social & Human Sciences — AI ethics, AI governance, algorithmic fairness, bioethics, human rights, gender equality, social transformations
4. Culture — AI in cultural heritage, Arabic language/NLP, generative AI and creativity, intangible heritage, intercultural dialogue
5. Communication & Information — AI in media, misinformation/deepfakes, internet governance, freedom of expression, media literacy, hate speech detection

UNESCO SUB-AREAS (assign the most specific one(s) — examples, not exhaustive):
Education: AI literacy, adaptive learning, higher education policy, teacher training, inclusive education
Natural Sciences: water sciences, ocean sciences, ecological sciences, climate change, bioinformatics, disaster risk, energy
Social & Human Sciences: ethics of AI, ethics of neurotechnology, bioethics, social transformations, fight against racism, human rights, gender equality, futures literacy
Culture: world heritage preservation, intangible cultural heritage, Arabic language & linguistics, creative industries, intercultural dialogue, museum & archives
Communication & Information: freedom of expression, media literacy, countering hate speech, internet governance, digital policy & inclusion, AI & rule of law, multilingualism

ETHICAL AI SKILLS (assign all that apply — these are examples, not an exhaustive list — infer from their work):
Core: AI ethics & governance, responsible AI design, explainable AI, AI safety & alignment, algorithmic fairness, AI policy & regulation, privacy & data protection, AI & human rights
Applied: NLP / Arabic NLP, computer vision, generative AI, agentic AI, classification & prediction, reinforcement learning, knowledge graphs, MLOps, bioinformatics AI, speech recognition, recommendation systems

AI RELATIONSHIP:
- Primary AI: AI is their main technical field (ML engineer, AI researcher, data scientist, NLP scientist)
- Adjacent AI: Main field is something else but they publish or work with ethical AI (lawyer, doctor, educator, social scientist, journalist, policy maker who uses or studies AI)

ORG TYPE: university / research_lab / startup / corporation / government / ngo / think_tank / international_org

SECTOR: academia / industry / government / civil_society

INDUSTRY AREA (if industry/government): health / finance / energy / education / legal / government / culture / media / transportation / environment / agriculture / defence / smart_cities / general_tech

TIER:
- Tier 1 (Speaker): Strong public voice, gives talks, known in Saudi/GCC AI ecosystem, senior title
- Tier 2 (Partner): Decision maker (CEO, CTO, VP, Director, Head of) at AI-relevant org
- Tier 3 (Research): Publishes AI research, affiliated with university or research lab

SCORING (0-100):
- Title seniority: 15pts (CEO/Prof/Director=15, Manager/Lead=10, Engineer/Researcher=5)
- Org recognition: 15pts (SDAIA/KAUST/Aramco=15, known startup=10, unknown=3)
- Ethical AI relevance: 15pts (explicit ethics focus=15, applied AI with ethics angle=8, general AI=3)
- Publication count: 15pts (10+ papers=15, 3-9=10, 1-2=5, none=0)
- Public presence: 10pts (conference talks/posts=10, some=5, none=0)
- Location: 10pts (Riyadh=10, KSA other=7, GCC=4)
- Contact availability: 10pts (email found=10, LinkedIn only=6, neither=0)
- Profile completeness: 10pts (3+ sources=10, 2=7, 1=3)

IMPORTANT:
- unesco_domains, unesco_sub_areas, ethical_ai_skills are LISTS — assign ALL that apply, not just one
- ethical_ai_skills is not exhaustive — infer skills from their papers and title even if not in the list above
- If a person has NO connection to ethical AI, set all unesco_domains to ["Not relevant"] and score=0

Return ONLY a valid JSON array. No explanation, no markdown. Each element:
{
  "name": "exact name from input",
  "unesco_domains": ["Domain1", "Domain2"],
  "unesco_sub_areas": ["Sub-area1", "Sub-area2"],
  "ethical_ai_skills": ["Skill1", "Skill2"],
  "ai_relationship": "Primary AI" or "Adjacent AI",
  "org_type": "...",
  "sector": "...",
  "industry_area": "...",
  "tier": 1 or 2 or 3,
  "priority_score": 0-100,
  "degree": "PhD" or "MSc" or "BSc" or "",
  "experience_years": number or 0
}"""


def classify(records: list[dict]) -> list[dict]:
    classified = []
    batches = [records[i:i+BATCH_SIZE] for i in range(0, len(records), BATCH_SIZE)]
    logger.info(f"Classifier: {len(records)} records in {len(batches)} batches...")

    for i, batch in enumerate(batches):
        logger.info(f"  Batch {i+1}/{len(batches)}...")
        results = _classify_batch(batch)
        result_map = {r["name"].lower(): r for r in results}

        for record in batch:
            c = result_map.get(record.get("name","").lower(), {})
            # Apply classification — lists join as comma-separated strings
            record["unesco_domains"]    = _join(c.get("unesco_domains", []))
            record["unesco_sub_areas"]  = _join(c.get("unesco_sub_areas", []))
            record["ethical_ai_skills"] = _join(c.get("ethical_ai_skills", []))
            record["ai_relationship"]   = c.get("ai_relationship", "")
            record["org_type"]          = c.get("org_type", "")
            record["sector"]            = c.get("sector", record.get("sector",""))
            record["industry_area"]     = c.get("industry_area", "")
            record["tier"]              = c.get("tier", 3)
            record["priority_score"]    = c.get("priority_score", 30)
            # Only fill degree/experience if not already set by ORCID
            if not record.get("degree"):
                record["degree"]           = c.get("degree","")
            if not record.get("experience_years"):
                record["experience_years"] = c.get("experience_years", 0)
            classified.append(record)

        if i < len(batches) - 1:
            time.sleep(1)

    logger.info(f"Classifier: {len(classified)} records classified.")
    return classified


def _classify_batch(batch: list[dict]) -> list[dict]:
    profiles = json.dumps([{
        "name":             r.get("name",""),
        "title":            r.get("title",""),
        "organization":     r.get("organization",""),
        "city":             r.get("city",""),
        "publications":     r.get("publications",0),
        "citations":        r.get("citations",0),
        "recent_paper":     r.get("recent_paper_title",""),
        "top_journals":     r.get("top_journals",""),
        "ethical_ai_skills":r.get("ethical_ai_skills",""),
        "email_found":      bool(r.get("email")),
        "linkedin_found":   bool(r.get("linkedin_url")),
        "sources":          r.get("sources_merged", r.get("source","")),
        "degree":           r.get("degree",""),
        "experience_years": r.get("experience_years",0),
    } for r in batch], ensure_ascii=False, indent=2)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role":"user","content":
                f"Classify these {len(batch)} professionals:\n\n{profiles}"}],
        )
        raw = response.content[0].text.strip()
        raw = raw.replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Claude returned invalid JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Claude API failed: {e}")
        return []


def _join(val) -> str:
    if isinstance(val, list): return ", ".join(str(v) for v in val if v)
    return str(val) if val else ""
