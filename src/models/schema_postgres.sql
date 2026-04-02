-- Céal PostgreSQL Schema
-- Event-driven job matching pipeline with ATS-proof data model
-- Translated from schema.sql (SQLite) for Cloud Run / Cloud SQL production

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
    scraped_at      TEXT    NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    ranked_at       TEXT,
    created_at      TEXT    NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    updated_at      TEXT    NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
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
    created_at      TEXT    NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
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
    completed_at    TEXT    NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
);

-- Company tier lookup
CREATE TABLE IF NOT EXISTS company_tiers (
    id              SERIAL PRIMARY KEY,
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

-- Trigger function: auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION trg_jobs_updated_at_fn()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_jobs_updated_at ON job_listings;
CREATE TRIGGER trg_jobs_updated_at
    BEFORE UPDATE ON job_listings
    FOR EACH ROW
    EXECUTE FUNCTION trg_jobs_updated_at_fn();

-- Seed Tier 1-3 companies
INSERT INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Stripe', 1, 'Tier 1 - TSE/Solutions roles')
    ON CONFLICT(company_pattern) DO NOTHING;
INSERT INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Square', 1, 'Tier 1 - FinTech')
    ON CONFLICT(company_pattern) DO NOTHING;
INSERT INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Plaid', 1, 'Tier 1 - FinTech APIs')
    ON CONFLICT(company_pattern) DO NOTHING;
INSERT INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Coinbase', 1, 'Tier 1 - Crypto/FinTech')
    ON CONFLICT(company_pattern) DO NOTHING;
INSERT INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Datadog', 1, 'Tier 1 - Observability')
    ON CONFLICT(company_pattern) DO NOTHING;
INSERT INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Toast', 1, 'Tier 1 - Former employer, strong network')
    ON CONFLICT(company_pattern) DO NOTHING;
INSERT INTO company_tiers (company_pattern, tier, notes) VALUES
    ('MongoDB', 2, 'Tier 2 - Needs cloud credential')
    ON CONFLICT(company_pattern) DO NOTHING;
INSERT INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Cloudflare', 2, 'Tier 2 - Infrastructure')
    ON CONFLICT(company_pattern) DO NOTHING;
INSERT INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Google', 3, 'Tier 3 - L5 TPM campaign')
    ON CONFLICT(company_pattern) DO NOTHING;
INSERT INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Amazon', 3, 'Tier 3 - Long campaign')
    ON CONFLICT(company_pattern) DO NOTHING;
INSERT INTO company_tiers (company_pattern, tier, notes) VALUES
    ('Microsoft', 3, 'Tier 3 - Long campaign')
    ON CONFLICT(company_pattern) DO NOTHING;

-- Seed skills vocabulary
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Python', 'Python', 'language', 1.0) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('SQL', 'SQL', 'language', 0.9) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('JavaScript', 'JavaScript', 'language', 0.6) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('TypeScript', 'TypeScript', 'language', 0.6) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Go', 'Go', 'language', 0.4) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Bash', 'Bash', 'language', 0.7) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('FastAPI', 'FastAPI', 'framework', 0.8) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Flask', 'Flask', 'framework', 0.6) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Django', 'Django', 'framework', 0.5) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('asyncio', 'asyncio', 'framework', 0.9) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Docker', 'Docker', 'infrastructure', 0.9) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Kubernetes', 'Kubernetes', 'infrastructure', 0.7) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Linux', 'Linux', 'infrastructure', 0.9) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('systemd', 'systemd', 'infrastructure', 0.7) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('CI/CD', 'CI/CD', 'infrastructure', 0.8) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('GitHub Actions', 'GitHub Actions', 'infrastructure', 0.8) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('AWS', 'AWS', 'cloud', 0.8) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('GCP', 'GCP', 'cloud', 0.9) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Azure', 'Azure', 'cloud', 0.5) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Cloud Run', 'Cloud Run', 'cloud', 0.8) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Cloud SQL', 'Cloud SQL', 'cloud', 0.7) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('PostgreSQL', 'PostgreSQL', 'database', 0.8) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('SQLite', 'SQLite', 'database', 0.6) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Redis', 'Redis', 'database', 0.7) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('REST APIs', 'REST APIs', 'methodology', 0.9) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Event-Driven Architecture', 'Event-Driven Architecture', 'methodology', 0.8) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Agile', 'Agile', 'methodology', 0.7) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Payment Processing', 'Payment Processing', 'domain', 0.9) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('FinTech', 'FinTech', 'domain', 0.9) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('SaaS', 'SaaS', 'domain', 0.8) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Technical Escalation Management', 'Technical Escalation Management', 'soft_skill', 1.0) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Cross-Functional Leadership', 'Cross-Functional Leadership', 'soft_skill', 0.9) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Customer-Facing Communication', 'Customer-Facing Communication', 'soft_skill', 0.9) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Project Management', 'Project Management', 'soft_skill', 0.8) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('JIRA', 'JIRA', 'tool', 0.7) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Confluence', 'Confluence', 'tool', 0.6) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Salesforce', 'Salesforce', 'tool', 0.7) ON CONFLICT(name) DO NOTHING;
INSERT INTO skills (name, canonical_name, category, weight) VALUES ('Git', 'Git', 'tool', 0.8) ON CONFLICT(name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Phase 4: Auto-Apply
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES job_listings(id),
    profile_id INTEGER NOT NULL REFERENCES resume_profiles(id),
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'ready', 'approved', 'submitted', 'withdrawn')),
    cover_letter TEXT,
    confidence_score DOUBLE PRECISION CHECK(confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    updated_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    submitted_at TEXT,
    UNIQUE(job_id, profile_id)
);

CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);

CREATE TABLE IF NOT EXISTS application_fields (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    field_type TEXT NOT NULL DEFAULT 'text' CHECK(field_type IN ('text', 'textarea', 'select', 'checkbox', 'radio', 'file', 'date', 'email', 'phone', 'url')),
    field_value TEXT,
    confidence DOUBLE PRECISION CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    source TEXT CHECK(source IS NULL OR source IN ('resume', 'profile', 'tailored', 'manual', 'ai_generated')),
    created_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    UNIQUE(application_id, field_name)
);

CREATE INDEX IF NOT EXISTS idx_appfields_application_id ON application_fields(application_id);

-- Trigger function: auto-update applications.updated_at
CREATE OR REPLACE FUNCTION trg_applications_updated_at_fn()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_applications_updated_at ON applications;
CREATE TRIGGER trg_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW
    EXECUTE FUNCTION trg_applications_updated_at_fn();

-- ---------------------------------------------------------------------------
-- Document Templates & Generated Documents
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS document_templates (
    id SERIAL PRIMARY KEY,
    doc_type TEXT NOT NULL CHECK(doc_type IN ('resume', 'cover_letter')),
    filename TEXT NOT NULL,
    file_blob BYTEA NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    uploaded_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    UNIQUE(doc_type)
);

CREATE TABLE IF NOT EXISTS generated_documents (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    doc_type TEXT NOT NULL CHECK(doc_type IN ('resume', 'cover_letter')),
    filename TEXT NOT NULL,
    file_blob BYTEA NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    generated_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    UNIQUE(application_id, doc_type)
);

CREATE INDEX IF NOT EXISTS idx_generated_docs_app_id ON generated_documents(application_id);
