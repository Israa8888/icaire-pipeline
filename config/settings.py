import os
from dotenv import load_dotenv
load_dotenv()

# ── API credentials ───────────────────────────────────────────────────────────
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_CSE_API_KEY  = os.getenv("GOOGLE_CSE_API_KEY")   # Google Custom Search
GOOGLE_CSE_CX       = os.getenv("GOOGLE_CSE_CX")        # Custom Search Engine ID
SCRAPIN_API_KEY     = os.getenv("SCRAPIN_API_KEY", "")
GOOGLE_CREDS_PATH   = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "config/google_credentials.json")
GOOGLE_SHEET_ID     = os.getenv("GOOGLE_SHEET_ID")
DRY_RUN             = os.getenv("DRY_RUN", "false").lower() == "true"

# ── Target institutions (KSA) ─────────────────────────────────────────────────
TARGET_INSTITUTIONS = [
    "KAUST", "King Abdullah University of Science and Technology",
    "KACST", "King Abdulaziz City for Science and Technology",
    "SDAIA", "Saudi Data and AI Authority",
    "KAU",   "King Abdulaziz University",
    "KSU",   "King Saud University",
    "KFUPM", "King Fahd University of Petroleum and Minerals",
    "Imam Muhammad ibn Saud Islamic University",
    "Princess Nourah bint Abdulrahman University",
    "Alfaisal University",
    "Saudi Aramco", "Aramco",
    "Elm", "Mozn", "STC", "NEOM",
]

# ── OpenAlex institution IDs (verified) ───────────────────────────────────────
OPENALEX_INSTITUTION_IDS = {
    "KAUST":                     "I124991207",
    "KAU":                       "I126076563",
    "KSU":                       "I167823236",
    "KFUPM":                     "I116951627",
    "KACST":                     "I4210163614",
    "Imam University":           "I2800280975",
    "Princess Nourah University":"I2802148613",
    "Alfaisal University":       "I4210095253",
}

# ── OpenAlex AI topic IDs ─────────────────────────────────────────────────────
OPENALEX_AI_TOPICS = [
    "T10007",   # Machine Learning
    "T11413",   # Deep Learning
    "T12444",   # Natural Language Processing
    "T10516",   # Computer Vision
    "T10161",   # Artificial Intelligence
    "T10575",   # Reinforcement Learning
    "T11278",   # Neural Networks
    "T10285",   # AI Ethics
    "T10399",   # Algorithmic Fairness
    "T11050",   # Explainable AI
    "T10823",   # Data Science
    "T12100",   # Knowledge Graphs
    "T10934",   # Generative AI
    "T11601",   # AI Safety
]

# ── arXiv categories (AI + ethical AI) ───────────────────────────────────────
ARXIV_CATEGORIES = [
    "cs.AI",    # Artificial Intelligence
    "cs.LG",    # Machine Learning
    "cs.CL",    # Computation and Language (NLP)
    "cs.CV",    # Computer Vision
    "cs.NE",    # Neural and Evolutionary Computing
    "cs.IR",    # Information Retrieval
    "cs.RO",    # Robotics
    "cs.CY",    # Computers and Society (AI ethics, fairness, policy)
    "stat.ML",  # Statistical Machine Learning
    "eess.AS",  # Audio and Speech Processing (Arabic NLP)
    "q-bio.QM", # Quantitative Methods (AI in health)
]

# ── Google Custom Search queries (broad → Claude filters) ─────────────────────
GOOGLE_SEARCH_QUERIES = [
    '"artificial intelligence" "Saudi Arabia" site:linkedin.com/in',
    '"machine learning" "Riyadh" site:linkedin.com/in',
    '"deep learning" "Saudi Arabia" site:linkedin.com/in',
    '"AI researcher" "Saudi Arabia" site:linkedin.com/in',
    '"data scientist" "KAUST" OR "SDAIA" OR "KSU" site:linkedin.com/in',
    '"AI ethics" "Saudi Arabia" site:linkedin.com/in',
    '"NLP" "Arabic" "Saudi Arabia" site:linkedin.com/in',
    '"computer vision" "Riyadh" site:linkedin.com/in',
    '"AI engineer" "Saudi Arabia" site:linkedin.com/in',
    '"responsible AI" "Saudi Arabia" site:linkedin.com/in',
    '"SDAIA" "artificial intelligence" site:linkedin.com/in',
    '"KACST" "machine learning" site:linkedin.com/in',
]

# ── Geography ─────────────────────────────────────────────────────────────────
CITY_COORDINATES = {
    "Riyadh":  (24.6877, 46.7219),
    "Jeddah":  (21.3891, 39.8579),
    "Thuwal":  (22.3025, 39.1036),
    "Dammam":  (26.4207, 50.0888),
    "Dhahran": (26.2172, 50.1971),
    "Abha":    (18.2164, 42.5053),
    "Medina":  (24.5247, 39.5692),
}

ORG_TO_CITY = {
    "KAUST":                     "Thuwal",
    "KAU":                       "Jeddah",
    "KSU":                       "Riyadh",
    "KFUPM":                     "Dhahran",
    "KACST":                     "Riyadh",
    "SDAIA":                     "Riyadh",
    "Saudi Aramco":              "Dhahran",
    "Imam University":           "Riyadh",
    "Princess Nourah University":"Riyadh",
    "Alfaisal University":       "Riyadh",
    "Elm":                       "Riyadh",
    "Mozn":                      "Riyadh",
    "STC":                       "Riyadh",
}

# ── Google Sheets ─────────────────────────────────────────────────────────────
SHEET_TAB_CONNECTIONS = "Connections"
SHEET_TAB_SCORING     = "Scoring Guide"
SHEET_TAB_LOG         = "Run Log"

# Column order — each row = one person, each column = one field
SHEET_COLUMNS = [
    # Identity
    "name",
    "title",
    "degree",
    "experience_years",
    # Organisation
    "organization",
    "org_type",
    "sector",
    "industry_area",
    # Location
    "city",
    "country",
    "latitude",
    "longitude",
    # Contact
    "email",
    "email_source",
    "linkedin_url",
    "orcid",
    "openalex_id",
    # Research
    "publications",
    "citations",
    "publication_types",
    "top_journals",
    "recent_paper_title",
    # Ethical AI classification
    "unesco_domains",
    "unesco_sub_areas",
    "ethical_ai_skills",
    "ai_relationship",
    # Scoring
    "tier",
    "priority_score",
    # Connection management (never overwritten by pipeline)
    "connection_status",
    "connection_type",
    "outreach_notes",
    "meeting_done",
    # Meta
    "sources_merged",
    "added_by",
    "last_updated",
]
