-- Hooze Outbound OS — Database Schema v1.2
-- Source of truth. See docs/04-database-schema.md for the human-readable reference.
-- Target: Supabase PostgreSQL
--
-- This file is a straight concatenation of database/migrations/*.sql in order.
-- If you are standing up a fresh Supabase project, running THIS file once does
-- everything. If you are evolving an existing database, run new files under
-- migrations/ individually instead — do not re-run this whole file against a
-- live database that already has data.
--
-- v1.2 change log (vs v1.1):
--   - added outreach.draft_history + outreach.rejection_reason (docs/10 §3,
--     missed in the original draft — see BUILD_LOG.md item #5)
-- v1.1 change log (vs the original v1.0 draft):
--   - added set_updated_at() trigger on companies + opportunities
--   - added analytics_snapshots table (WF-14 output, docs/13 + docs/15)
--   - opportunities.company_id now 'on delete restrict' per docs/04 §1 guidance

-- Migration 001: companies
-- Depends on: nothing (root table)
-- Reference: docs/04-database-schema.md §2 companies, docs/03-data-dictionary.md
--
-- companies is the anchor table for the whole pipeline. companies.status is the
-- single source of truth for lead lifecycle state (docs/05-lead-lifecycle.md §1) —
-- no other table's rows should ever be used to *infer* a company's status.

create extension if not exists pgcrypto;

create table if not exists companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  normalized_name text not null,
  domain text,
  industry text not null,
  location text not null,
  phone text,
  phone_normalized text,
  email text,
  email_normalized text,
  website text,
  linkedin text,
  instagram text,
  youtube text,
  whatsapp text,
  source text not null check (source in
    ('google_maps','linkedin','website','youtube','instagram','directory','referral','manual')),
  source_url text,
  status text not null default 'DISCOVERED' check (status in
    ('DISCOVERED','CLEANED','RESEARCHED','QUALIFIED','PERSONALIZED','REVIEW',
     'APPROVED','CONTACTED','REPLIED','MEETING','PROPOSAL','WON','LOST','DEAD')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Dedup index: docs/05-lead-lifecycle.md relies on this to stop the same
-- business entering the pipeline twice under a slightly different casing/spacing.
create unique index if not exists idx_companies_dedup
  on companies (normalized_name, location);
create index if not exists idx_companies_domain on companies (domain);
create index if not exists idx_companies_phone on companies (phone_normalized);
create index if not exists idx_companies_email on companies (email_normalized);
create index if not exists idx_companies_status on companies (status);

-- Keep updated_at current on every write. Every later migration that touches
-- companies.status (WF-02 through WF-13) relies on this trigger rather than
-- each workflow remembering to set updated_at itself.
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_companies_updated_at on companies;
create trigger trg_companies_updated_at
  before update on companies
  for each row execute function set_updated_at();

-- Migration 002: contacts
-- Depends on: 001_companies.sql
-- Reference: docs/04-database-schema.md §2 contacts, docs/02-icp-spec.md §2.3
--
-- confidence (HIGH/MEDIUM/LOW) drives contactability_score in the scoring
-- engine (docs/06-scoring-engine.md §2.4) — it is not cosmetic metadata.

create table if not exists contacts (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  name text,
  job_title text,
  email text,
  phone text,
  linkedin text,
  contact_source text,
  confidence text not null check (confidence in ('HIGH','MEDIUM','LOW')),
  created_at timestamptz not null default now()
);

create index if not exists idx_contacts_company on contacts (company_id);

-- Migration 003: research, research_evidence
-- Depends on: 001_companies.sql
-- Reference: docs/04-database-schema.md §2, docs/07-research-engine.md
--
-- research_evidence is the provenance table required by the "no claim, no
-- send" principle (docs/01-system-prd.md §9.2). EVERY fact used anywhere
-- downstream (scoring pain/buying signals, personalization messages) must
-- trace back to a row here with a source_url. research holds the *rolled-up*
-- summary; research_evidence holds the atomic, sourced facts behind it.

create table if not exists research (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  website_summary text,
  services text[],
  target_market text,
  whatsapp_present boolean,
  booking_process text,
  lead_capture_process text,
  observed_problem text,
  pain_signals text[],
  buying_signals text[],
  proof text,
  research_score int check (research_score between 0 and 100),
  researched_at timestamptz default now()
);

create index if not exists idx_research_company on research (company_id);

create table if not exists research_evidence (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  claim text not null,
  source_url text not null,
  captured_at timestamptz not null default now(),
  confidence text not null check (confidence in ('HIGH','MEDIUM','LOW'))
);

create index if not exists idx_evidence_company on research_evidence (company_id);

-- Migration 004: lead_scores
-- Depends on: 001_companies.sql (and logically on 002/003, though no FK to them)
-- Reference: docs/04-database-schema.md §2, docs/06-scoring-engine.md
--
-- One row per scoring run (re-scoring per docs/06-scoring-engine.md §4 inserts
-- a NEW row rather than updating in place, so score history is auditable —
-- always query "latest row per company_id" for the current score).

create table if not exists lead_scores (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  icp_score int not null check (icp_score between 0 and 25),
  pain_score int not null check (pain_score between 0 and 25),
  buying_signal_score int not null check (buying_signal_score between 0 and 20),
  contactability_score int not null check (contactability_score between 0 and 15),
  personalization_score int not null check (personalization_score between 0 and 15),
  total_score int not null check (total_score between 0 and 100),
  priority text not null check (priority in ('A','B','C','DONT_CONTACT')),
  reason text not null,
  scored_at timestamptz not null default now()
);

create index if not exists idx_scores_company on lead_scores (company_id);
create index if not exists idx_scores_priority on lead_scores (priority);

-- Migration 005: campaigns
-- Depends on: nothing (referenced BY outreach, but references nothing itself)
-- Reference: docs/04-database-schema.md §2, docs/09-campaign-spec.md
--
-- Seeded with Campaign 001 (Abuja Real Estate) via database/seed.sql, not here —
-- migrations define structure only, seed.sql owns starting data.

create table if not exists campaigns (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  industry text not null,
  target_location text not null,
  offer text not null,
  pain text not null,
  proof text,
  cta text not null,
  status text not null default 'DRAFT' check (status in ('DRAFT','ACTIVE','PAUSED','RETIRED')),
  created_at timestamptz not null default now()
);

-- Migration 006: outreach
-- Depends on: 001_companies.sql, 002_contacts.sql, 005_campaigns.sql
-- Reference: docs/04-database-schema.md §2, docs/10-outreach-sop.md §2,
--            docs/11-follow-up.md
--
-- outreach.status is a FINER sub-state machine nested inside companies.status
-- (docs/05-lead-lifecycle.md §5 note). One row per message (initial send AND
-- each follow-up gets its own row, follow_up_number distinguishes them).
--
-- The "one active outreach cycle per company" guardrail (docs/05-lead-lifecycle.md
-- §3) is enforced at the application/workflow layer via a query
-- (`select 1 from outreach where company_id = ? and status in ('SENT','ACTIVE')`)
-- rather than a DB constraint, because a company legitimately accumulates
-- multiple outreach rows over time (initial + follow-ups + possibly a later
-- campaign after DEAD-reset) — a hard uniqueness constraint would be wrong.

create table if not exists outreach (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  contact_id uuid references contacts(id),
  campaign_id uuid not null references campaigns(id),
  channel text not null check (channel in ('EMAIL','WHATSAPP')),
  message text not null,
  status text not null default 'DRAFT' check (status in
    ('DRAFT','PENDING_REVIEW','APPROVED','REJECTED','SENT','ACTIVE',
     'REPLIED','NOT_INTERESTED','DEAD')),
  sent_at timestamptz,
  follow_up_number int not null default 0,
  last_contact_at timestamptz,
  next_follow_up_at timestamptz,
  approved_by text,
  approved_at timestamptz
);

create index if not exists idx_outreach_company on outreach (company_id);
create index if not exists idx_outreach_status on outreach (status);
create index if not exists idx_outreach_next_followup on outreach (next_follow_up_at);

-- Migration 007: responses
-- Depends on: 006_outreach.sql
-- Reference: docs/04-database-schema.md §2, docs/12-response-classification.md
--
-- raw response_text is stored verbatim (never overwritten) so classifier
-- accuracy can be audited later (docs/12-response-classification.md §5).

create table if not exists responses (
  id uuid primary key default gen_random_uuid(),
  outreach_id uuid not null references outreach(id) on delete cascade,
  response_text text not null,
  classification text not null check (classification in
    ('INTERESTED','QUESTION','NOT_INTERESTED','LATER','PRICE',
     'MEETING','WRONG_PERSON','UNSUBSCRIBE','UNKNOWN')),
  sentiment text check (sentiment in ('POSITIVE','NEUTRAL','NEGATIVE')),
  intent text,
  created_at timestamptz not null default now()
);

create index if not exists idx_responses_outreach on responses (outreach_id);

-- Migration 008: opportunities
-- Depends on: 001_companies.sql
-- Reference: docs/04-database-schema.md §2, docs/13-n8n-architecture.md WF-13
--
-- on delete restrict (not cascade): opportunities are a historical sales
-- record and per docs/04-database-schema.md §1 should survive even if a
-- company row were ever removed (in practice companies are never hard-deleted
-- in this system — see docs/14-security-spec.md §6 — but this is defensive).

create table if not exists opportunities (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete restrict,
  stage text not null check (stage in ('MEETING','PROPOSAL','WON','LOST')),
  estimated_value numeric,
  notes text,
  next_action text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_opportunities_company on opportunities (company_id);
create index if not exists idx_opportunities_stage on opportunities (stage);

drop trigger if exists trg_opportunities_updated_at on opportunities;
create trigger trg_opportunities_updated_at
  before update on opportunities
  for each row execute function set_updated_at();

-- Migration 009: error_log
-- Depends on: 001_companies.sql
-- Reference: docs/13-n8n-architecture.md WF-15, docs/14-security-spec.md §5
--
-- Every workflow's error path (WF-01 through WF-14) writes here instead of
-- silently dropping a failure — this is what WF-15 (Error Monitoring) reads.
-- Retained >= 90 days per docs/14-security-spec.md §5 (no automated purge is
-- implemented in V1; if one is added later it must respect that floor).

create table if not exists error_log (
  id uuid primary key default gen_random_uuid(),
  workflow text not null,
  company_id uuid references companies(id),
  error_message text not null,
  payload jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_error_log_workflow on error_log (workflow);
create index if not exists idx_error_log_created on error_log (created_at);

-- Migration 010: analytics_snapshots
-- Depends on: nothing directly (aggregates read from all pipeline tables)
-- Reference: docs/13-n8n-architecture.md WF-14, docs/15-analytics-spec.md
--
-- WF-14 runs weekly and writes one row per (period, slice) here rather than
-- computing the funnel live on every dashboard load — keeps the dashboard
-- fast and gives Hooze a historical trend, not just a current snapshot.
-- `slice_type`/`slice_value` implement the "sliced by campaign, channel,
-- source, message variant" requirement in docs/15-analytics-spec.md §2
-- without needing a separate table per slice dimension.

create table if not exists analytics_snapshots (
  id uuid primary key default gen_random_uuid(),
  period_start date not null,
  period_end date not null,
  slice_type text not null check (slice_type in ('OVERALL','CAMPAIGN','CHANNEL','SOURCE','VARIANT')),
  slice_value text not null default 'ALL',
  metrics jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_analytics_period on analytics_snapshots (period_start, period_end);
create index if not exists idx_analytics_slice on analytics_snapshots (slice_type, slice_value);

-- Migration 011: Row Level Security
-- Depends on: all prior migrations (needs every table to exist)
-- Reference: docs/14-security-spec.md §2, docs/04-database-schema.md §1
--
-- V1 is single-operator (docs/01-system-prd.md §4) and all writes come from
-- n8n using the Supabase SERVICE ROLE key, which bypasses RLS by default —
-- so enabling RLS with no policies does not break WF-01..WF-15. What it does
-- do: if an ANON key is ever exposed (e.g. embedding the review dashboard
-- directly against Supabase instead of proxying through n8n/a backend),
-- nothing is readable or writable without an explicit policy below.
--
-- A future second-operator/public-dashboard phase adds a scoped policy here
-- (read + approve/edit/reject on outreach only, read-only elsewhere) per
-- docs/14-security-spec.md §2 — intentionally not implemented yet.

alter table companies enable row level security;
alter table contacts enable row level security;
alter table research enable row level security;
alter table research_evidence enable row level security;
alter table lead_scores enable row level security;
alter table campaigns enable row level security;
alter table outreach enable row level security;
alter table responses enable row level security;
alter table opportunities enable row level security;
alter table error_log enable row level security;
alter table analytics_snapshots enable row level security;

-- No policies are created for the anon/public role in V1 — this is
-- deliberate default-deny. Service role writes (n8n) are unaffected.

-- Migration 012: outreach review-workflow fields
-- Depends on: 006_outreach.sql
-- Reference: docs/10-outreach-sop.md §3
--
-- Added after the initial schema draft: §3 requires (a) preserving the
-- original AI-drafted message when Hooze edits it before approving ("kept
-- in a draft_history note field"), and (b) logging WHY a message was
-- rejected ("A rejection reason is logged... feeds scoring/research
-- quality improvements"). Neither had a column in the v1.0 draft schema —
-- this migration closes that gap. See BUILD_LOG.md item #5.

alter table outreach add column if not exists draft_history text;
alter table outreach add column if not exists rejection_reason text;

comment on column outreach.draft_history is
  'Original AI-generated message text, preserved verbatim if Hooze edits outreach.message before approving (docs/10-outreach-sop.md §3). NULL if never edited.';
comment on column outreach.rejection_reason is
  'Free-text reason logged when outreach.status -> REJECTED (docs/10-outreach-sop.md §3). Feeds scoring/research quality review (docs/15-analytics-spec.md §3 rejection rate).';

