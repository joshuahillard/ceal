-- Céal Schema — PostgreSQL Edition
-- All 11 tables with PostgreSQL-native syntax
-- Equivalent to schema.sql (SQLite) — same constraints, same seed data

-- =========================================================================
-- Phase 1: Core Pipeline Tables
-- =========================================================================

-- Core job listings table
CREATE TABLE IF NOT EXISTS job_listings (
    id              SERIAL PRIMARY KEY,
    external_id     TEXT    NOT NULL,
    source          TEXT    NOT NULL CHECK(source IN ('linkedin', 'indeed', 'google_jobs', 'manual')),
    title           TEXT    NOT NULL,
    company_name    TEXT    NOT NULL,
    company_tier    INTEGER CHECK(company_tier BETWEEN 1 AND 3),
    location        TEXT,
    remote_type     TEXT    CHECK(remote_type IN ('remote', 'hybrid', 'onsite', 'unknown')),
    salary_min      DOUBLE PRECISION,
    salary_max      DOUBLE PRECISION,
    salary_currency TEXT    DEFAULT 'USD',
    url             TEXT    NOT NULL,
    description_raw TEXT,
    description_clean TEXT,
    posting_date    TEXT,
    expiry_date     TEXT,
    match_score     DOUBLE PRECISION CHECK(match_score BETWEEN 0.0 AND 1.0),
    match_reasoning TEXT,
    rank_model_version TEXT,
    status          TEXT    NOT NULL DEFAULT 'scraped'
                           CHECK(status IN ('scraped','ranked','applied','responded','interviewing','offer','rejected','archived')),
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ranked_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(external_id, source)
);

-- Skills vocabulary table
CREATE TABLE IF NOT EXISTS skills (
    id              SERIAL PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    canonical_name  TEXT,
    category        TEXT    NOT NULL CHECK(category IN (
                        'language', 'framework', 'infrastructure', 'database',
                        'cloud', 'methodology', 'soft_skill', 'domain', 'tool'
                    )),
    weight          DOUBLE PRECISION NOT NULL DEFAULT 0.5 CHECK(weight BETWEEN 0.0 AND 1.0)
);

-- Many-to-many: which skills each job requires
CREATE TABLE IF NOT EXISTS job_skills (
    id              SERIAL PRIMARY KEY,
    job_id          INTEGER NOT NULL REFERENCES job_listings(id) ON DELETE CASCADE,
    skill_id        INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    is_required     BOOLEAN NOT NULL DEFAULT TRUE,
    source_context  TEXT,
    UNIQUE(job_id, skill_id)
);

-- Resume profiles for matching
CREATE TABLE IF NOT EXISTS resume_profiles (
    id              SERIAL PRIMARY KEY,
    name            TEXT    NOT NULL,
    version         TEXT    NOT NULL DEFAULT '1.0',
    raw_text        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Resume skills with proficiency
CREATE TABLE IF NOT EXISTS resume_skills (
    id              SERIAL PRIMARY KEY,
    profile_id      INTEGER NOT NULL REFERENCES resume_profiles(id) ON DELETE CASCADE,
    skill_id        INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    proficiency     TEXT    NOT NULL CHECK(proficiency IN ('expert', 'proficient', 'familiar', 'learning')),
    years_experience DOUBLE PRECISION,
    evidence        TEXT,
    UNIQUE(profile_id, skill_id)
);

-- Operational metrics per scrape run
CREATE TABLE IF NOT EXISTS scrape_log (
    id              SERIAL PRIMARY KEY,
    source          TEXT    NOT NULL,
    query_term      TEXT    NOT NULL,
    jobs_found      INTEGER NOT NULL DEFAULT 0,
    jobs_new        INTEGER NOT NULL DEFAULT 0,
    jobs_duplicate  INTEGER NOT NULL DEFAULT 0,
    errors          INTEGER NOT NULL DEFAULT 0,
    error_details   TEXT,
    duration_seconds DOUBLE PRECISION,
    completed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Company tier lookup
CREATE TABLE IF NOT EXISTS company_tiers (
    id              SERIAL PRIMARY KEY,
    company_pattern TEXT    NOT NULL UNIQUE,
    tier            INTEGER NOT NULL CHECK(tier BETWEEN 1 AND 3),
    notes           TEXT
);

-- =========================================================================
-- Phase 2: Tailoring Pipeline Tables
-- =========================================================================

-- Parsed resume bullets (atomic units for tailoring engine)
CREATE TABLE IF NOT EXISTS parsed_bullets (
    id              SERIAL PRIMARY KEY,
    profile_id      INTEGER NOT NULL REFERENCES resume_profiles(id) ON DELETE CASCADE,
    section         TEXT    NOT NULL CHECK(section IN ('SUMMARY', 'EXPERIENCE', 'SKILLS', 'PROJECTS', 'CERTIFICATIONS')),
    original_text   TEXT    NOT NULL,
    skills_referenced TEXT,
    metrics         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(profile_id, original_text)
);

-- Tailoring requests (one per job+profile pair)
CREATE TABLE IF NOT EXISTS tailoring_requests (
    id              SERIAL PRIMARY KEY,
    job_id          INTEGER NOT NULL REFERENCES job_listings(id) ON DELETE CASCADE,
    profile_id      INTEGER NOT NULL REFERENCES resume_profiles(id) ON DELETE CASCADE,
    target_tier     INTEGER NOT NULL CHECK(target_tier BETWEEN 1 AND 3),
    emphasis_areas  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(job_id, profile_id)
);

-- Tailored bullets (rewritten per request)
CREATE TABLE IF NOT EXISTS tailored_bullets (
    id              SERIAL PRIMARY KEY,
    request_id      INTEGER NOT NULL REFERENCES tailoring_requests(id) ON DELETE CASCADE,
    original        TEXT    NOT NULL,
    rewritten_text  TEXT    NOT NULL,
    xyz_format      BOOLEAN NOT NULL DEFAULT FALSE,
    relevance_score DOUBLE PRECISION NOT NULL CHECK(relevance_score BETWEEN 0.0 AND 1.0),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Skill gap analysis (per request)
CREATE TABLE IF NOT EXISTS skill_gaps (
    id              SERIAL PRIMARY KEY,
    request_id      INTEGER NOT NULL REFERENCES tailoring_requests(id) ON DELETE CASCADE,
    skill_name      TEXT    NOT NULL,
    category        TEXT    NOT NULL CHECK(category IN ('language', 'framework', 'infrastructure', 'database', 'cloud', 'methodology', 'soft_skill', 'domain', 'tool')),
    job_requires    BOOLEAN NOT NULL DEFAULT TRUE,
    resume_has      BOOLEAN NOT NULL DEFAULT FALSE,
    proficiency     TEXT    CHECK(proficiency IS NULL OR proficiency IN ('expert', 'proficient', 'familiar', 'learning')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(request_id, skill_name)
);

-- =========================================================================
-- Indexes
-- =========================================================================

CREATE INDEX IF NOT EXISTS idx_jobs_status ON job_listings(status);
CREATE INDEX IF NOT EXISTS idx_jobs_match_score ON job_listings(match_score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_company_tier ON job_listings(company_tier);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at ON job_listings(scraped_at);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON job_listings(source);
CREATE INDEX IF NOT EXISTS idx_job_skills_job ON job_skills(job_id);
CREATE INDEX IF NOT EXISTS idx_job_skills_skill ON job_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_resume_skills_profile ON resume_skills(profile_id);
CREATE INDEX IF NOT EXISTS idx_scrape_log_source ON scrape_log(source);
CREATE INDEX IF NOT EXISTS idx_parsed_bullets_profile ON parsed_bullets(profile_id);
CREATE INDEX IF NOT EXISTS idx_tailoring_requests_job ON tailoring_requests(job_id);
CREATE INDEX IF NOT EXISTS idx_tailoring_requests_profile ON tailoring_requests(profile_id);
CREATE INDEX IF NOT EXISTS idx_tailored_bullets_request ON tailored_bullets(request_id);
CREATE INDEX IF NOT EXISTS idx_skill_gaps_request ON skill_gaps(request_id);

-- =========================================================================
-- Trigger: auto-update updated_at timestamp (PostgreSQL syntax)
-- =========================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_jobs_updated_at'
    ) THEN
        CREATE TRIGGER trg_jobs_updated_at
            BEFORE UPDATE ON job_listings
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END;
$$;

-- =========================================================================
-- Seed Data
-- =========================================================================

-- Seed Tier 1-3 companies
INSERT INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Stripe', 1, 'Tier 1 - TSE/Solutions roles'),
    ('Square', 1, 'Tier 1 - FinTech'),
    ('Plaid', 1, 'Tier 1 - FinTech APIs'),
    ('Coinbase', 1, 'Tier 1 - Crypto/FinTech'),
    ('Datadog', 1, 'Tier 1 - Observability'),
    ('Toast', 1, 'Tier 1 - Former employer, strong network'),
    ('MongoDB', 2, 'Tier 2 - Needs cloud credential'),
    ('Cloudflare', 2, 'Tier 2 - Infrastructure'),
    ('Google', 3, 'Tier 3 - L5 TPM campaign'),
    ('Amazon', 3, 'Tier 3 - Long campaign'),
    ('Microsoft', 3, 'Tier 3 - Long campaign')
ON CONFLICT DO NOTHING;

-- Seed skills vocabulary
INSERT INTO skills (name, canonical_name, category, weight) VALUES
    ('Python', 'Python', 'language', 1.0),
    ('SQL', 'SQL', 'language', 0.9),
    ('JavaScript', 'JavaScript', 'language', 0.6),
    ('TypeScript', 'TypeScript', 'language', 0.6),
    ('Go', 'Go', 'language', 0.4),
    ('Bash', 'Bash', 'language', 0.7),
    ('FastAPI', 'FastAPI', 'framework', 0.8),
    ('Flask', 'Flask', 'framework', 0.6),
    ('Django', 'Django', 'framework', 0.5),
    ('asyncio', 'asyncio', 'framework', 0.9),
    ('Docker', 'Docker', 'infrastructure', 0.9),
    ('Kubernetes', 'Kubernetes', 'infrastructure', 0.7),
    ('Linux', 'Linux', 'infrastructure', 0.9),
    ('systemd', 'systemd', 'infrastructure', 0.7),
    ('CI/CD', 'CI/CD', 'infrastructure', 0.8),
    ('GitHub Actions', 'GitHub Actions', 'infrastructure', 0.8),
    ('AWS', 'AWS', 'cloud', 0.8),
    ('GCP', 'GCP', 'cloud', 0.9),
    ('Azure', 'Azure', 'cloud', 0.5),
    ('Cloud Run', 'Cloud Run', 'cloud', 0.8),
    ('Cloud SQL', 'Cloud SQL', 'cloud', 0.7),
    ('PostgreSQL', 'PostgreSQL', 'database', 0.8),
    ('SQLite', 'SQLite', 'database', 0.6),
    ('Redis', 'Redis', 'database', 0.7),
    ('REST APIs', 'REST APIs', 'methodology', 0.9),
    ('Event-Driven Architecture', 'Event-Driven Architecture', 'methodology', 0.8),
    ('Agile', 'Agile', 'methodology', 0.7),
    ('Payment Processing', 'Payment Processing', 'domain', 0.9),
    ('FinTech', 'FinTech', 'domain', 0.9),
    ('SaaS', 'SaaS', 'domain', 0.8),
    ('Technical Escalation Management', 'Technical Escalation Management', 'soft_skill', 1.0),
    ('Cross-Functional Leadership', 'Cross-Functional Leadership', 'soft_skill', 0.9),
    ('Customer-Facing Communication', 'Customer-Facing Communication', 'soft_skill', 0.9),
    ('Project Management', 'Project Management', 'soft_skill', 0.8),
    ('JIRA', 'JIRA', 'tool', 0.7),
    ('Confluence', 'Confluence', 'tool', 0.6),
    ('Salesforce', 'Salesforce', 'tool', 0.7),
    ('Git', 'Git', 'tool', 0.8)
ON CONFLICT DO NOTHING;
