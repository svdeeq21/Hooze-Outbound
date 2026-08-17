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
