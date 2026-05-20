# ICAIRE AI Connection Pipeline

Automated pipeline that collects, deduplicates, classifies, and maintains
a live connection list of AI professionals in Saudi Arabia.

---

## What this does

- Scrapes 4 sources: LinkedIn (unofficial API), Semantic Scholar, arXiv, university websites
- Deduplicates across sources using fuzzy matching
- Enriches with email (Hunter.io) and coordinates (for the Looker Studio map)
- Classifies each person into Tier 1/2/3 with a priority score using Claude API
- Pushes everything into a Google Sheet (3 tabs: Connections, Scoring Guide, Run Log)
- Runs automatically every Monday via GitHub Actions

**Total ongoing cost: ~$0/month** (Claude API calls ~$0.01/week for the classification step)

---

## Project structure

```
icaire_pipeline/
├── main.py                          ← Run this to execute the pipeline
├── requirements.txt
├── .env.example                     ← Copy to .env and fill in
├── .gitignore
├── config/
│   ├── settings.py                  ← All constants, target institutions, keywords
│   └── google_credentials.json      ← You create this (see Step 3)
├── scrapers/
│   ├── linkedin_scraper.py
│   ├── semantic_scholar_scraper.py
│   ├── arxiv_scraper.py
│   └── web_scraper.py
├── pipeline/
│   ├── deduplicator.py
│   ├── enricher.py
│   ├── classifier.py
│   └── push_to_sheets.py
├── tests/
│   └── test_pipeline.py             ← Run after each step
└── .github/workflows/
    └── weekly_refresh.yml           ← GitHub Actions auto-run
```

---

## STEP-BY-STEP SETUP

---

### STEP 0 — Prerequisites (do this first, takes ~10 min)

Make sure you have:
- Python 3.10 or 3.11 installed (`python --version`)
- A GitHub account (free)
- A Google account (free)
- Your Anthropic API key (you already have this)

---

### STEP 1 — Clone and install

```bash
# 1. Clone or download this project folder
cd icaire_pipeline

# 2. Create a virtual environment (keeps dependencies clean)
python -m venv venv
source venv/bin/activate          # Mac/Linux
# OR:
venv\Scripts\activate             # Windows

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Copy the env template
cp .env.example .env
```

✅ TEST STEP 1:
```bash
python -c "import anthropic, gspread, linkedin_api, semanticscholar, rapidfuzz; print('All packages installed OK')"
```
Expected output: `All packages installed OK`

---

### STEP 2 — Fill in your .env file

Open `.env` in any text editor and fill in:

```
LINKEDIN_EMAIL=your_secondary_account@gmail.com   # Use a secondary LinkedIn account
LINKEDIN_PASSWORD=your_linkedin_password
ANTHROPIC_API_KEY=sk-ant-...                      # From console.anthropic.com
HUNTER_API_KEY=...                                # From hunter.io (free signup)
GOOGLE_SHEET_ID=...                               # You fill this in after Step 3
```

**Important — LinkedIn:**
- Do NOT use your main LinkedIn account. Create a free secondary account.
- The script adds 2–4 second delays between calls to avoid getting flagged.

**Important — Hunter.io:**
- Go to hunter.io → sign up free → go to Dashboard → copy your API key.
- Free tier gives 25 email lookups/month — enough to start.

✅ TEST STEP 2 (scrapers only, no real LinkedIn call):
```bash
python tests/test_pipeline.py --step 1
```
Expected: all green checkmarks. Semantic Scholar and arXiv will make real API calls.

---

### STEP 3 — Set up Google Sheets (takes ~15 min, do it once)

#### 3a. Create your Google Sheet
1. Go to sheets.google.com → create a new blank spreadsheet
2. Name it: `ICAIRE AI Connections`
3. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/THIS_IS_YOUR_SHEET_ID/edit`
4. Paste it into `.env` as `GOOGLE_SHEET_ID=...`

#### 3b. Create a Service Account (this is how Python talks to Sheets)
1. Go to console.cloud.google.com
2. Create a new project (name it `icaire-pipeline`)
3. Go to: APIs & Services → Enable APIs → search "Google Sheets API" → Enable
4. Also enable: "Google Drive API"
5. Go to: APIs & Services → Credentials → Create Credentials → Service Account
6. Name it `icaire-sheets-bot` → click Create
7. On the service account page → Keys tab → Add Key → JSON
8. Download the JSON file → rename it `google_credentials.json`
9. Move it into: `icaire_pipeline/config/google_credentials.json`

#### 3c. Share your Sheet with the service account
1. Open the downloaded JSON file — find the `client_email` field
   (looks like: `icaire-sheets-bot@icaire-pipeline.iam.gserviceaccount.com`)
2. Open your Google Sheet → Share → paste that email → give Editor access

✅ TEST STEP 3:
```bash
python tests/test_pipeline.py --step 5
```
Expected: `Connected to Google Sheet: 'ICAIRE AI Connections'` + dry run summary.

---

### STEP 4 — Run the dedup and enrichment tests

These use no external APIs — just validates the logic:

```bash
python tests/test_pipeline.py --step 2
python tests/test_pipeline.py --step 3
```

Expected: all green checkmarks for both.

---

### STEP 5 — Test the Claude classifier (uses real API, minimal cost)

```bash
python tests/test_pipeline.py --step 4
```

This sends 2 profiles to Claude to verify the API key works and classification returns
valid tiers and scores. Cost: ~$0.001.

---

### STEP 6 — Run the full pipeline (first real run)

```bash
# Dry run first — shows what WOULD be pushed, no writes
DRY_RUN=true python main.py

# If that looks correct, run for real:
python main.py
```

First run takes ~5–15 minutes depending on how many pages get scraped.
Open your Google Sheet — you should see:
- Tab 1: Connections (populated with rows)
- Tab 2: Scoring Guide (formula explanation)
- Tab 3: Run Log (timestamp + counts)

---

### STEP 7 — Run the full test suite

```bash
python tests/test_pipeline.py --all
```

Expected: all 5 steps pass.

---

### STEP 8 — Set up GitHub Actions (auto-run every Monday)

This is what makes it fully automatic — you never touch it again.

#### 8a. Push your project to GitHub
```bash
git init
git add .
git commit -m "ICAIRE pipeline initial setup"
# Create a new PRIVATE repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/icaire-pipeline.git
git push -u origin main
```

#### 8b. Add your secrets to GitHub
Go to your GitHub repo → Settings → Secrets and variables → Actions → New repository secret

Add these secrets one by one:

| Secret name              | Value                                      |
|--------------------------|-------------------------------------------|
| `LINKEDIN_EMAIL`         | Your secondary LinkedIn email             |
| `LINKEDIN_PASSWORD`      | Your LinkedIn password                    |
| `ANTHROPIC_API_KEY`      | Your Anthropic API key                    |
| `HUNTER_API_KEY`         | Your Hunter.io API key                    |
| `GOOGLE_SHEET_ID`        | Your Google Sheet ID                      |
| `GOOGLE_CREDENTIALS_JSON`| Paste the ENTIRE contents of google_credentials.json |

#### 8c. Verify the workflow runs
Go to your repo → Actions tab → you should see `ICAIRE Pipeline — Weekly Refresh`
Click → Run workflow → Run workflow (manual trigger to test it)

Watch it run in real time. When it finishes green, automation is live.
Every Monday at 08:00 UTC it will run automatically.

---

### STEP 9 — Connect Looker Studio (the visual dashboard)

1. Go to lookerstudio.google.com → Create → Report
2. Add data source → Google Sheets → select `ICAIRE AI Connections` → Connections tab
3. Build your pages:
   - **Page 1 — Dashboard:** Add scorecard widgets for totals, bar chart (org), pie chart (sector)
   - **Page 2 — Table:** Add a table widget, select all fields, enable filters
   - **Page 3 — Map:** Add Google Maps widget → set Location field to `city` or use lat/long columns
4. Add filter controls at the top: Tier, City, AI Subfield, Status
5. Share the Looker Studio report link with the ICAIRE team

Looker Studio auto-refreshes from Sheets — no action needed after setup.

---

## Customising the pipeline

**Add a new institution:**
Open `config/settings.py` → add to `TARGET_INSTITUTIONS` and `FACULTY_PAGES`

**Change scoring weights:**
Open `pipeline/classifier.py` → edit the `SYSTEM_PROMPT` scoring section

**Change how often it runs:**
Open `.github/workflows/weekly_refresh.yml` → edit the `cron` line
(use crontab.guru to build cron expressions)

**Add more LinkedIn keywords:**
Open `config/settings.py` → add to `LINKEDIN_KEYWORDS`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| LinkedIn login fails | Check credentials in .env. Try logging in manually first. Use secondary account. |
| Sheets connection fails | Make sure you shared the sheet with the service account email |
| Claude returns invalid JSON | Rare — re-run. The classifier has retry logic built in |
| GitHub Actions fails | Check the Actions log. Usually a missing secret |
| Hunter.io returns nothing | Free tier may be exhausted for the month (25 limit) |
| arXiv returns no results | Try running again — arXiv API occasionally times out |
