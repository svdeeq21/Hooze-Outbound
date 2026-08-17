# 04 — Database Schema

**Version:** 1.0 · **Depends on:** 03-data-dictionary.md · **Target:** Supabase PostgreSQL

## 1. Design notes

- All primary keys are `uuid default gen_random_uuid()`.
- All FKs cascade on delete of the parent `companies` row only where it makes sense (contacts, research, lead_scores, outreach cascade; opportunities and responses are kept for historical record — `on delete restrict` recommended, revisit in 14-security-spec.md).
- Enums are implemented as `text` with a `check` constraint rather than native Postgres enums, so values can be extended without a migration that locks the table (matches the "interfaces before implementations" principle in 01-system-prd.md).
- Row Level Security (RLS) is enabled on every table; policy detail lives in 14-security-spec.md. This doc defines structure only.
- Full SQL lives in `database/schema.sql` in the repo — this doc is the human-readable reference; schema.sql is the source of truth if they ever diverge.

## 2. Tables

### companies

```sql
create table companies (
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

create unique index idx_companies_dedup
  on companies (normalized_name, location);
create index idx_companies_domain on companies (domain);
create index idx_companies_phone on companies (phone_normalized);
create index idx_companies_email on companies (email_normalized);
create index idx_companies_status on companies (status);
```

### contacts

```sql
create table contacts (
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

create index idx_contacts_company on contacts (company_id);
```

### research

```sql
create table research (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  website_summary text,
  services text[],
  target_market text,
  whatsapp_present boolean,
  booking_process text,
  lead_capture_process text,
  observed_problem text,
  pain_signals text[],
  buying_signals text[],
  proof text,
  research_score int check (research_score between 0 and 100),
  researched_at timestamptz default now()
);

create index idx_research_company on research (company_id);
```

### research_evidence

```sql
create table research_evidence (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  claim text not null,
  source_url text not null,
  captured_at timestamptz not null default now(),
  confidence text not null check (confidence in ('HIGH','MEDIUM','LOW'))
);

create index idx_evidence_company on research_evidence (company_id);
```

### lead_scores

```sql
create table lead_scores (
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

create index idx_scores_company on lead_scores (company_id);
create index idx_scores_priority on lead_scores (priority);
```

### campaigns

```sql
create table campaigns (
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
```

### outreach

```sql
create table outreach (
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

create index idx_outreach_company on outreach (company_id);
create index idx_outreach_status on outreach (status);
create index idx_outreach_next_followup on outreach (next_follow_up_at);
```

### responses

```sql
create table responses (
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

create index idx_responses_outreach on responses (outreach_id);
```

### opportunities

```sql
create table opportunities (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id),
  stage text not null check (stage in ('MEETING','PROPOSAL','WON','LOST')),
  estimated_value numeric,
  notes text,
  next_action text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_opportunities_company on opportunities (company_id);
create index idx_opportunities_stage on opportunities (stage);
```

## 3. Relationships (ERD summary)

```
companies 1───* contacts
companies 1───1 research
companies 1───* research_evidence
companies 1───* lead_scores
companies 1───* outreach ───* responses
companies 1───* opportunities
campaigns 1───* outreach
```

## 4. Migration order

1. `companies`
2. `contacts`
3. `research`, `research_evidence`
4. `lead_scores`
5. `campaigns`
6. `outreach`
7. `responses`
8. `opportunities`

Each as a separate file under `database/migrations/NNN_description.sql` so the history is auditable and any single migration can be rolled back.
