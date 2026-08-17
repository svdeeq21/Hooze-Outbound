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
