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
