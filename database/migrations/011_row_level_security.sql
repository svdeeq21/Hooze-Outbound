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
