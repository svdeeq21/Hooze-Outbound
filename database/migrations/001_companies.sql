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
