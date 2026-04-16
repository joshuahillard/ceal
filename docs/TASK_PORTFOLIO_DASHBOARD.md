# Task Card: Portfolio Dashboard Generator
**Paste after CEAL CORE v1.1 contract. Modes: db, web, product.**
*Created: April 3, 2026*

---

## How to Use

Copy the block below into Claude Code after your Core Contract. It will:
1. Query the Ceal SQLite DB for live job pipeline data
2. Mine git history for commit/sprint/release metrics
3. Read Moss Lane file tree for project metrics
4. Generate or update a single-file HTML portfolio dashboard
5. Output to `career/Josh_Hillard_Portfolio_Dashboard.html`

Rerun after any sprint to get updated numbers.

---

## Prompt Block — Copy Everything Below

```
TASK: Generate or update portfolio dashboard

Goal: Build a single-file interactive HTML dashboard that showcases all engineering work across Ceal and Moss Lane projects, job search pipeline data, skills inventory, and career narrative — sourced from live repo/DB data. This is a portfolio artifact for interviews.

Scope:
- Ceal repo: git log, file tree, line counts, test counts, schema, DB contents
- Ceal SQLite DB (data/ceal.db): job_listings (37 rows), skills (38 rows), company_tiers (11 rows), resume_profiles (1 row), all other tables
- Moss Lane directory (sibling to Ceal): github-repo/, deliverables/, ops/, deploy/, brand/, career/
- Career materials: career/ dirs in both Ceal and Moss Lane
- Output: career/Josh_Hillard_Portfolio_Dashboard.html (single file, Chart.js via CDN)

Out of scope: Do not modify any source code, tests, or schema. Read-only data gathering. Do not run the scraper or ranker.

MODE: db
MODE: web
MODE: product

---

DATA COLLECTION STEPS (run these first, collect all numbers):

1. GIT METRICS (run from ceal/ root):
   git log --oneline | wc -l                              # total commits
   git log --format="%ad" --date=short | sort | uniq -c   # commits by day
   git tag -l                                              # release tags
   git log --oneline --format="%H|%ad|%s" --date=short    # full commit history

2. CEAL CODEBASE METRICS:
   find src -name "*.py" | wc -l                           # source file count
   find tests -name "*.py" | wc -l                         # test file count
   find src -name "*.py" -exec wc -l {} + | sort -rn       # lines by file
   find tests -name "*.py" -exec wc -l {} + | sort -rn     # test lines by file
   find src -name "*.py" -exec cat {} + | wc -l            # total src lines
   find tests -name "*.py" -exec cat {} + | wc -l          # total test lines
   wc -l src/web/templates/*.html                          # template sizes
   wc -l src/web/routes/*.py                               # route sizes
   find docs -type f | wc -l                               # doc count
   # Lines by module directory:
   for d in src/*/; do echo -n "$d: "; find "$d" -name "*.py" -exec cat {} + | wc -l; done

3. CEAL DATABASE (data/ceal.db via python3 + sqlite3):
   - Table names + row counts (all 13 tables + sqlite_sequence)
   - job_listings: SELECT title, company_name, status, match_score, location, remote_type, salary_min, salary_max, scraped_at, ranked_at, source FROM job_listings ORDER BY company_name
   - Status distribution: SELECT status, COUNT(*) FROM job_listings GROUP BY status
   - Location distribution: SELECT location, COUNT(*) FROM job_listings GROUP BY location ORDER BY COUNT(*) DESC
   - Remote type distribution: SELECT remote_type, COUNT(*) FROM job_listings GROUP BY remote_type
   - Company frequency: SELECT company_name, COUNT(*) FROM job_listings GROUP BY company_name ORDER BY COUNT(*) DESC
   - Skills by category: SELECT category, COUNT(*) FROM skills GROUP BY category
   - All skills: SELECT name, category FROM skills ORDER BY category, name
   - Company tiers: SELECT company_pattern, tier, notes FROM company_tiers ORDER BY tier
   - Match score stats: SELECT MIN(match_score), ROUND(AVG(match_score),2), MAX(match_score) FROM job_listings WHERE match_score IS NOT NULL

4. MOSS LANE METRICS (from sibling Moss-Lane/ directory):
   find github-repo -name "*.py" | wc -l                   # python files
   find github-repo -name "*.py" -exec cat {} + | wc -l    # total python lines
   wc -l github-repo/lazarus.py github-repo/fort_v2_clean.py github-repo/learning_engine.py github-repo/data_integrity.py github-repo/db_adapter.py github-repo/fund_splitter.py github-repo/load_test.py
   wc -l github-repo/engine/*.py                           # engine subdir
   find . -name "*.md" | wc -l                             # markdown docs
   find . -name "*.pdf" | wc -l                            # PDFs
   find . -name "*.pptx" | wc -l                           # presentations
   ls deploy/*.sh | wc -l                                  # deploy scripts
   ls ops/briefings/                                       # ops briefings
   ls ops/handoffs/                                        # session handoffs
   ls deliverables/                                        # deliverable artifacts

---

DASHBOARD STRUCTURE (6 tabs, 10-15 sections each):

TAB 1: OVERVIEW
- KPI grid: commits, tests, total LOC (combined both projects), sprints, days, python files, DB tables, jobs tracked, docs written, web routes
- Commits by day (bar chart)
- Test growth over time (line chart, by date: Mar 28 → Apr 3)
- Sprint velocity (bar chart, features per sprint)
- Code growth cumulative (dual-line: Ceal vs Moss Lane)
- Project comparison (grouped bar: src LOC, test LOC, templates, docs, deploy scripts)
- Output by artifact type (donut: python, test, markdown, HTML, PDF, PPTX, shell)
- Full build timeline (7-day detailed with milestones)
- Release history table (4 tags with dates and highlights)
- Documentation output (3-column: Ceal docs, Moss Lane docs, Career materials)
- Infrastructure comparison (2-column: Ceal infra vs Moss Lane infra)

TAB 2: CEAL ENGINE
- KPI grid: src files, src lines, test files, test lines, tests passing (317 local SQLite), DB tables, web routes, release tags, ADRs, doc files
- Architecture flow diagram (core pipeline + extended modules — use CSS flexbox boxes with arrows)
- Source lines by module (horizontal bar: models, tailoring, document, web, scrapers, ranker, normalizer, apply)
- Largest source files (horizontal bar: database.py, main.py, etc.)
- Unit vs integration test split (horizontal bar)
- Test file inventory (2-column mini-stat list)
- Database schema (donut by phase + table with row counts)
- Web routes (horizontal bar by LOC)
- Templates (horizontal bar by LOC)
- 8 ADRs as styled cards (2-column layout)
- Technical debt register (table: 5 items with severity badges)
- Tech stack (tag cloud with colored badges)
- Commit timeline (timeline component by date with commit details)

TAB 3: MOSS LANE
- KPI grid: python files, python lines, engine core LOC, deploy scripts, API integrations, MD docs, PDFs, PPTX, deliverables, handoffs
- Architecture flow diagram (trading pipeline + support systems)
- Module LOC (horizontal bar chart)
- System maturity radar (radar chart: engine, risk, data integrity, API, DB, devops, learning, docs, brand, ops)
- Engine internals (donut: root modules vs engine subdir vs other)
- Module detail table (10 modules with lines and purpose)
- Operations (3-column: deploy scripts, ops briefings, session handoffs)
- Deliverables portfolio (table: 12 artifacts with type and interview value)
- Build timeline (7-day, Moss Lane specific milestones)
- Tech stack tags

TAB 4: JOB PIPELINE
- KPI grid: jobs tracked, unique companies, target tiers, skills indexed, avg match score, metro areas, ranked count, awaiting rank
- Status funnel (bar chart: scraped → ranked → applied → interviewing → offer)
- Match score distribution (bar chart for ranked listings)
- Geography (horizontal bar: locations by frequency)
- Work model distribution (donut: unknown, hybrid, remote, onsite)
- Company frequency (horizontal bar: top 15 companies)
- Target companies by tier (donut: tier 1/2/3 counts)
- Tiered role strategy (3-column detail: tier 1/2/3 with roles, companies, salary, fit/gap)
- Full 37-listing scrollable table (title, company, location, remote, status, score)
- Scrape timeline (timeline: batch timestamps with details)
- Skills demand (bar chart: categories from DB + full inventory list)

TAB 5: SKILLS & STACK
- Engineering proficiency bars (8 skills: Python, SQL, APIs, LLM, Docker, CI/CD, Linux, GCP)
- Leadership proficiency bars (8 skills: Escalation, Leadership, Process, FinTech, Customer, Training, PM, AI/ML)
- Skill radar (radar: current level vs Tier 1 requirements — dual dataset)
- Skills by category (polar area chart from DB)
- Skill gap analysis (3-column: Tier 1 ready / Tier 2 gaps / Tier 3 campaign)
- Certification timeline (timeline: completed, in progress, planned)
- Tool/framework matrix (table: demonstrated, claimed, target)

TAB 6: CAREER NARRATIVE
- The story (prose: Toast background → transition → sprint week → active search)
- Career timeline (timeline: Apr 2019 → Jun 2022 → Oct 2023 → Oct 2025 → Mar 2026 → Apr 2026)
- X-Y-Z resume bullets (4 styled cards: Ceal, Moss Lane, $12M save, 37% reduction)
- Interview talking points (2-column, 5 per column: technical depth + leadership impact)
- Transition narrative (2-column, 3 per column: Q&A format)
- Toast impact KPIs (kpi grid: $12M, 37%, 63%, 6+ years, CEO)
- STAR story bank (table: 6 stories with situation, result, best-for)
- Portfolio artifacts index (3-column: Code, Documents, Presentations)

---

TECH REQUIREMENTS:
- Single HTML file. All CSS inline in <style>. All JS inline in <script>.
- Chart.js 4.x via CDN: https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js
- Dark theme (bg: #0f1117, surface: #1a1d27, accent: #6366f1, green: #22c55e, amber: #f59e0b, pink: #ec4899, cyan: #06b6d4)
- Responsive grid (auto-fit minmax). Mobile breakpoints at 700px and 1000px.
- Sticky navigation bar. Smooth scroll to top on tab switch.
- Tab-based navigation (6 tabs, JS show/hide). Active tab highlighted.
- All job listing data embedded as JS array in <script> tag (from DB query).
- Print-friendly: all sections visible, white background.

STYLING COMPONENTS:
- .kpi — stat card with gradient text (use CSS background-clip: text)
- .pnl — panel card with border, border-radius 10px
- .tl / .tl-i — vertical timeline with colored dots
- .tag — inline badge with category-specific background colors
- .tbl — data table with hover rows
- .tp — talking point card with left border accent
- .af / .ab — architecture flow diagram with CSS flex boxes + arrow dividers
- .sk — skill bar with gradient fill
- .ms — mini stat row (label + value, flex space-between)
- .sh — section header (uppercase, letter-spacing, accent color)

---

Acceptance:
- Dashboard loads in browser with all 6 tabs functional
- All numbers match live repo/DB data (cross-check totals)
- Combined LOC = Ceal src + Ceal tests + Moss Lane python (verify with wc -l)
- All 37 job listings appear in pipeline table
- All 38 skills appear in skills inventory
- All 11 company tiers appear in tier analysis
- Charts render correctly (no console errors)
- Timeline components appear on Overview, Ceal, Moss Lane, Pipeline, Skills, and Narrative tabs

Verify:
- Open career/Josh_Hillard_Portfolio_Dashboard.html in browser
- Click all 6 tabs — each should display content
- Compare KPI numbers against: git log --oneline | wc -l, DB row counts, file system counts
- Check browser console for JS errors

Deliver:
- career/Josh_Hillard_Portfolio_Dashboard.html (single file)
- Report: actual numbers collected vs numbers in dashboard
- Flag any data that couldn't be collected or seems stale
```

---

## Snapshot (update before each run)

```
SNAPSHOT:
- Branch: main | Latest release tag: v2.10.0-sprint10-pdf-generation
- Tests: 317 passing locally under SQLite, 0 warnings, ruff clean
- Known issues: TD-001 through TD-006 (see ledger)
- DB state: 37 job_listings, 38 skills, 11 company_tiers, 1 resume_profile
- Recent context: Sprint 10 shipped April 3 2026. PDF gen + CRM + Vertex AI live.
```

---

## Notes

**When to rerun:** After any sprint that adds tests, features, or job listings. The dashboard should always reflect current repo state.

**Data freshness:** Git metrics and file counts are always live. DB data depends on running the scraper/ranker. If new listings are scraped or ranked, rerun to update the pipeline tab.

**Moss Lane path:** The prompt assumes Moss-Lane/ is a sibling directory to Ceal/. If the structure changes, update the path references in step 4.

**Career narrative:** The Toast numbers ($12M, 37%, 63%) are from Josh's resume and are stable. Update only if the resume changes.
