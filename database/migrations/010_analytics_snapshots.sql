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
