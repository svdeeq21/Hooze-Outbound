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
