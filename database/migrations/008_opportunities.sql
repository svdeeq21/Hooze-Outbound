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
