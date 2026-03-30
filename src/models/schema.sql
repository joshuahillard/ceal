-- Céal Phase 1 Schema
-- Event-driven job matching pipeline with ATS-proof data model

-- Core job listings table
CREATE TABLE IF NOT EXISTS job_listings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id     TEXT    NOT NULL,
    source          TEXT    NOT NULL CHECK(source IN ('linkedin', 'indeed', 'google_jobs', 'manual')),
    title           TEXT    NOT NULL,
    company_name    TEXT    NOT NULL,
    company_tier    INTEGER CHECK(company_tier BETWEEN 1 AND 3),
    location        TEXT,
    remote_type     TEXT    CHECK(remote_type IN ('remote', 'hybrid', 'onsite', 'unknown')),
    salary_min      REAL,
    salary_max      REAL,
    salary_currency TEXT    DEFAULT 'USD',
    url             TEXT    NOT NULL,
    description_raw TEXT,
    description_clean TEXT,
    posting_date    TEXT,
    expiry_date     TEXT,
    match_score     REAL    CHECK(match_score BETWEEN 0.0 AND 1.0),
    match_reasoning TEXT,
    rank_model_version TEXT,
    status          TEXT    NOT NULL DEFAULT 'scraped'
                           CHECK(status IN ('scraped','ranked','applied','responded','interviewing','offer','rejected','archived')),
    scraped_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ranked_at       TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(external_id, source)
);

-- Skills vocabulary table
CREATE TABLE IF NOT EXISTS skills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    canonical_name  TEXT,
    category        TEXT    NOT NULL CHECK(category IN (
                        'language', 'framework', 'infrastructure', 'database',
                        'cloud', 'methodology', 'soft_skill', 'domain', 'tool'
                    )),
    weight          REAL    NOT NULL DEFAULT 0.5 CHECK(weight BETWEEN 0.0 AND 1.0)
);

-- Many-to-many: which skills each job requires
CREATE TABLE IF NOT EXISTS job_skills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES job_listings(id) ON DELETE CASCADE,
    skill_id        INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    is_required     BOOLEAN NOT NULL DEFAULT 1,
    source_context  TEXT,
    UNIQUE(job_id, skill_id)
);

-- Resume profiles for matching
CREATE TABLE IF NOT EXISTS resume_profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    version         TEXT    NOT NULL DEFAULT '1.0',
    raw_text        TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Resume skills with proficiency
CREATE TABLE IF NOT EXISTS resume_skills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id      INTEGER NOT NULL REFERENCES resume_profiles(id) ON DELETE CASCADE,
    skill_id        INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    proficiency     TEXT    NOT NULL CHECK(proficiency IN ('expert', 'proficient', 'familiar', 'learning')),
    years_experience REAL,
    evidence        TEXT,
    UNIQUE(profile_id, skill_id)
);

-- Operational metrics per scrape run
CREATE TABLE IF NOT EXISTS scrape_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL,
    query_term      TEXT    NOT NULL,
    jobs_found      INTEGER NOT NULL DEFAULT 0,
    jobs_new        INTEGER NOT NULL DEFAULT 0,
    jobs_duplicate  INTEGER NOT NULL DEFAULT 0,
    errors          INTEGER NOT NULL DEFAULT 0,
    error_details   TEXT,
    duration_seconds REAL,
    completed_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Company tier lookup
CREATE TABLE IF NOT EXISTS company_tiers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_pattern TEXT    NOT NULL UNIQUE,
    tier            INTEGER NOT NULL CHECK(tier BETWEEN 1 AND 3),
    notes           TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_jobs_status ON job_listings(status);
CREATE INDEX IF NOT EXISTS idx_jobs_match_score ON job_listings(match_score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_company_tier ON job_listings(company_tier);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at ON job_listings(scraped_at);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON job_listings(source);
CREATE INDEX IF NOT EXISTS idx_job_skills_job ON job_skills(job_id);
CREATE INDEX IF NOT EXISTS idx_job_skills_skill ON job_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_resume_skills_profile ON resume_skills(profile_id);
CREATE INDEX IF NOT EXISTS idx_scrape_log_source ON scrape_log(source);

-- Trigger: auto-update updated_at timestamp
CREATE TRIGGER IF NOT EXISTS trg_jobs_updated_at
    AFTER UPDATE ON job_listings
    FOR EACH ROW
BEGIN
    UPDATE job_listings SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;

-- Seed Tier 1-3 companies
INSERT OR IGNORE INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Stripe', 1, 'Tier 1 - TSE/Solutions roles');
INSERT OR IGNORE INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Square', 1, 'Tier 1 - FinTech');
INSERT OR IGNORE INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Plaid', 1, 'Tier 1 - FinTech APIs');
INSERT OR IGNORE INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Coinbase', 1, 'Tier 1 - Crypto/FinTech');
INSERT OR IGNORE INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Datadog', 1, 'Tier 1 - Observability');
INSERT OR IGNORE INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Toast', 1, 'Tier 1 - Former employer, strong network');
INSERT OR IGNORE INTO company_tiers (company_pattern, tier, notes) VALUES
    ('MongoDB', 2, 'Tier 2 - Needs cloud credential');
INSERT OR IGNORE INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Cloudflare', 2, 'Tier 2 - Infrastructure');
INSERT OR IGNORE INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Google', 3, 'Tier 3 - L5 TPM campaign');
INSERT OR IGNORE INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Amazon', 3, 'Tier 3 - Long campaign');
INSERT OR IGNORE INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Microsoft', 3, 'Tier 3 - Long campaign');

-- Seed skills vocabulary
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Python', 'Python', 'language', 1.0);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('SQL', 'SQL', 'language', 0.9);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('JavaScript', 'JavaScript', 'language', 0.6);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('TypeScript', 'TypeScript', 'language', 0.6);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Go', 'Go', 'language', 0.4);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Bash', 'Bash', 'language', 0.7);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('FastAPI', 'FastAPI', 'framework', 0.8);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Flask', 'Flask', 'framework', 0.6);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Django', 'Django', 'framework', 0.5);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('asyncio', 'asyncio', 'framework', 0.9);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Docker', 'Docker', 'infrastructure', 0.9);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Kubernetes', 'Kubernetes', 'infrastructure', 0.7);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Linux', 'Linux', 'infrastructure', 0.9);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('systemd', 'systemd', 'infrastructure', 0.7);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('CI/CD', 'CI/CD', 'infrastructure', 0.8);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('GitHub Actions', 'GitHub Actions', 'infrastructure', 0.8);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('AWS', 'AWS', 'cloud', 0.8);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('GCP', 'GCP', 'cloud', 0.9);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Azure', 'Azure', 'cloud', 0.5);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Cloud Run', 'Cloud Run', 'cloud', 0.8);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Cloud SQL', 'Cloud SQL', 'cloud', 0.7);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('PostgreSQL', 'PostgreSQL', 'database', 0.8);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('SQLite', 'SQLite', 'database', 0.6);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Redis', 'Redis', 'database', 0.7);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('REST APIs', 'REST APIs', 'methodology', 0.9);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Event-Driven Architecture', 'Event-Driven Architecture', 'methodology', 0.8);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Agile', 'Agile', 'methodology', 0.7);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Payment Processing', 'Payment Processing', 'domain', 0.9);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('FinTech', 'FinTech', 'domain', 0.9);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('SaaS', 'SaaS', 'domain', 0.8);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Technical Escalation Management', 'Technical Escalation Management', 'soft_skill', 1.0);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Cross-Functional Leadership', 'Cross-Functional Leadership', 'soft_skill', 0.9);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Customer-Facing Communication', 'Customer-Facing Communication', 'soft_skill', 0.9);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Project Management', 'Project Management', 'soft_skill', 0.8);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('JIRA', 'JIRA', 'tool', 0.7);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Confluence', 'Confluence', 'tool', 0.6);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Salesforce', 'Salesforce', 'tool', 0.7);
INSERT OR IGNORE INTO skills (name, canonical_name, category, weight) VALUES ('Git', 'Git', 'tool', 0.8)
