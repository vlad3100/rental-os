-- Munich Rental Copilot v0.1 schema (SQLite).
-- Every row carries org_id; every query in store.py filters by it (tenant isolation).
-- is_synthetic is constrained to 1: this database cannot hold real data in v0.1.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS organizations (
    org_id        TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    is_synthetic  INTEGER NOT NULL CHECK (is_synthetic = 1)
);

CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES organizations(org_id),
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('operator', 'viewer'))
);

CREATE TABLE IF NOT EXISTS units (
    unit_id       TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES organizations(org_id),
    title         TEXT NOT NULL,
    district      TEXT NOT NULL,
    is_synthetic  INTEGER NOT NULL CHECK (is_synthetic = 1)
);

-- A verified fact must have a value and a source. Inferred facts must explain themselves.
CREATE TABLE IF NOT EXISTS facts (
    fact_id       TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES organizations(org_id),
    unit_id       TEXT NOT NULL REFERENCES units(unit_id),
    field         TEXT NOT NULL,
    label_de      TEXT NOT NULL,
    label_en      TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('money', 'area', 'count', 'bool', 'date', 'text')),
    value         TEXT,
    value_en      TEXT,
    status        TEXT NOT NULL CHECK (status IN ('verified', 'extracted', 'user_entered', 'inferred', 'unknown')),
    source_ref    TEXT,
    note          TEXT,
    recorded_at   TEXT NOT NULL,
    CHECK (status != 'verified' OR (value IS NOT NULL AND source_ref IS NOT NULL)),
    CHECK (status != 'inferred' OR (note IS NOT NULL AND source_ref IS NOT NULL)),
    CHECK (status != 'unknown' OR value IS NULL),
    UNIQUE (unit_id, field)
);

CREATE TABLE IF NOT EXISTS knowledge (
    org_id        TEXT NOT NULL REFERENCES organizations(org_id),
    knowledge_id  TEXT NOT NULL,
    language      TEXT NOT NULL CHECK (language IN ('de', 'en')),
    text          TEXT NOT NULL,
    PRIMARY KEY (org_id, knowledge_id, language)
);

CREATE TABLE IF NOT EXISTS inquiries (
    inquiry_id              TEXT PRIMARY KEY,
    org_id                  TEXT NOT NULL REFERENCES organizations(org_id),
    unit_id                 TEXT NOT NULL REFERENCES units(unit_id),
    received_at             TEXT NOT NULL,
    channel                 TEXT NOT NULL,
    applicant_ref           TEXT NOT NULL,
    applicant_display_name  TEXT,
    contact_channel         TEXT CHECK (contact_channel IN ('email', 'phone', 'address')),
    message                 TEXT NOT NULL,
    state                   TEXT NOT NULL,
    tool_failures           INTEGER NOT NULL DEFAULT 0,
    erased_at               TEXT,
    is_synthetic            INTEGER NOT NULL CHECK (is_synthetic = 1)
);

CREATE TABLE IF NOT EXISTS drafts (
    draft_id           TEXT PRIMARY KEY,
    org_id             TEXT NOT NULL REFERENCES organizations(org_id),
    inquiry_id         TEXT NOT NULL REFERENCES inquiries(inquiry_id),
    created_at         TEXT NOT NULL,
    author             TEXT NOT NULL CHECK (author IN ('agent', 'operator')),
    status             TEXT NOT NULL CHECK (status IN ('pending_review', 'blocked', 'approved', 'rejected', 'sent')),
    text               TEXT,
    final_text         TEXT,
    fact_ids_used      TEXT NOT NULL DEFAULT '[]',
    proposed_slot_ids  TEXT NOT NULL DEFAULT '[]',
    findings_json      TEXT NOT NULL DEFAULT '[]',
    reviewed_by        TEXT,
    reviewed_at        TEXT,
    override_reason    TEXT
);

-- One row per agent run: the full structured output contract (agent_output.v1).
CREATE TABLE IF NOT EXISTS agent_runs (
    run_id       TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL REFERENCES organizations(org_id),
    inquiry_id   TEXT NOT NULL REFERENCES inquiries(inquiry_id),
    created_at   TEXT NOT NULL,
    output_json  TEXT
);

CREATE TABLE IF NOT EXISTS slots (
    slot_id    TEXT PRIMARY KEY,
    org_id     TEXT NOT NULL REFERENCES organizations(org_id),
    unit_id    TEXT NOT NULL REFERENCES units(unit_id),
    starts_at  TEXT NOT NULL,
    capacity   INTEGER NOT NULL CHECK (capacity > 0)
);

-- Primary key makes booking idempotent: the same inquiry cannot book the same slot twice.
CREATE TABLE IF NOT EXISTS bookings (
    slot_id     TEXT NOT NULL REFERENCES slots(slot_id),
    inquiry_id  TEXT NOT NULL REFERENCES inquiries(inquiry_id),
    org_id      TEXT NOT NULL REFERENCES organizations(org_id),
    booked_at   TEXT NOT NULL,
    PRIMARY KEY (slot_id, inquiry_id)
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id     TEXT PRIMARY KEY,
    org_id      TEXT NOT NULL REFERENCES organizations(org_id),
    inquiry_id  TEXT,
    kind        TEXT NOT NULL,
    reason      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done'))
);

-- Suppression list: pseudonymous reference only, so a stop or deletion is honoured later.
CREATE TABLE IF NOT EXISTS contact_blocks (
    org_id         TEXT NOT NULL REFERENCES organizations(org_id),
    applicant_ref  TEXT NOT NULL,
    kind           TEXT NOT NULL CHECK (kind IN ('opt_out', 'deletion')),
    recorded_at    TEXT NOT NULL,
    PRIMARY KEY (org_id, applicant_ref, kind)
);

-- Audit payloads never contain message text or contact data (see audit.py).
CREATE TABLE IF NOT EXISTS audit_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id       TEXT NOT NULL,
    at           TEXT NOT NULL,
    actor        TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inquiries_org ON inquiries (org_id, received_at);
CREATE INDEX IF NOT EXISTS idx_drafts_inquiry ON drafts (org_id, inquiry_id, created_at);
CREATE INDEX IF NOT EXISTS idx_runs_inquiry ON agent_runs (org_id, inquiry_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events (org_id, entity_id, event_id);
