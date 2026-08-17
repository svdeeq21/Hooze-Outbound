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
