-- Migration 007: responses
-- Depends on: 006_outreach.sql
-- Reference: docs/04-database-schema.md §2, docs/12-response-classification.md
--
-- raw response_text is stored verbatim (never overwritten) so classifier
-- accuracy can be audited later (docs/12-response-classification.md §5).

create table if not exists responses (
  id uuid primary key default gen_random_uuid(),
  outreach_id uuid not null references outreach(id) on delete cascade,
  response_text text not null,
  classification text not null check (classification in
    ('INTERESTED','QUESTION','NOT_INTERESTED','LATER','PRICE',
     'MEETING','WRONG_PERSON','UNSUBSCRIBE','UNKNOWN')),
  sentiment text check (sentiment in ('POSITIVE','NEUTRAL','NEGATIVE')),
  intent text,
  created_at timestamptz not null default now()
);

create index if not exists idx_responses_outreach on responses (outreach_id);
