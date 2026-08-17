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
