# Hooze Outbound OS

A free, self-hosted outbound operating system for Hooze Enterprises: Find →
Research → Personalize → Review → Send → Track → Learn.

Built for ₦0 infrastructure cost (n8n Community Edition, Supabase free
tier, Google Sheets/Gmail within quota). No autonomous sending — every
message is approved by Hooze before it goes out.

**This repo is built, not just specced.** The database schema, the full
Python processing layer, all 15 n8n workflows, and the review dashboard
exist and are tested. See `BUILD_LOG.md` for exactly what was verified, how,
and every judgment call made while turning the spec into working code —
read that before changing scoring, schema, or the review/send flow.

## Start here

Read `docs/01-system-prd.md` first — it's the contract every other
document (and every line of code in this repo) stays consistent with. Then
read `BUILD_LOG.md` for what building it actually required.

## Document order

| # | Doc | Covers |
|---|---|---|
| 01 | system-prd.md | Purpose, goals, non-goals, constraints, success metrics |
| 02 | icp-spec.md | Who gets contacted — firmographics, pain/buying signals, disqualifiers |
| 03 | data-dictionary.md | Every field, table-agnostic |
| 04 | database-schema.md | Table definitions, relationships, indexes |
| 05 | lead-lifecycle.md | The company status state machine |
| 06 | scoring-engine.md | Deterministic 0–100 scoring, tiering |
| 07 | research-engine.md | Evidence-gathering interface + provenance rule |
| 08 | personalization-spec.md | Anti-hallucination message generation rules |
| 09 | campaign-spec.md | Campaign object, Campaign 001 (Abuja real estate) locked |
| 10 | outreach-sop.md | What Hooze does manually at review/send |
| 11 | follow-up.md | Cadence, stop conditions |
| 12 | response-classification.md | Reply categories and routing |
| 13 | n8n-architecture.md | All 15 workflow contracts |
| 14 | security-spec.md | Credentials, RLS, PII, retention |
| 15 | analytics-spec.md | Funnel metrics, feedback loop |

## Repo structure

```
hooze-outbound/
├── docs/                 15 specification documents (above)
├── BUILD_LOG.md          what was built, verified, and every judgment call made
├── database/
│   ├── schema.sql         full DDL, source of truth — a literal concatenation
│   │                      of migrations/*.sql, regenerate after editing those
│   ├── seed.sql           Campaign 001 + two sample leads (Tier A + DONT_CONTACT)
│   └── migrations/        12 files, one (or a few related) table(s) each,
│                          in dependency order
├── python/                processing layer — one package per pipeline stage
│   ├── config.py           Supabase client + env var handling, one place only
│   ├── ai_client.py        shared Gemini-primary/Groq-fallback wrapper
│   ├── api.py               HTTP wrapper around every module below, only
│   │                        needed for a Railway-style split deployment
│   │                        (see RAILWAY_DEPLOYMENT.md) — thin pass-through,
│   │                        no logic of its own
│   ├── discovery/          placeholder (V1 discovery is a manual staging sheet)
│   ├── enrichment/         normalize.py (WF-02), dedup.py (WF-03), enrich.py (WF-04)
│   ├── research/           interface.py, fetcher.py, ai_extractor.py (WF-05)
│   ├── scoring/            engine.py, signal_matcher.py (WF-06, deterministic)
│   ├── campaign/           matcher.py (WF-07)
│   ├── personalization/    generator.py, validator.py (WF-08)
│   ├── review/             actions.py — approve/reject/mark_sent + dashboard reads (WF-09/10)
│   ├── followup/           scheduler.py (WF-11)
│   ├── classification/     classifier.py (WF-12)
│   ├── opportunities/      manager.py (WF-13)
│   └── analytics/          reports.py (WF-14)
├── n8n/
│   ├── generate_workflows.py  generates every WF-*.json below — edit this,
│   │                          not the JSON files directly, then regenerate
│   └── WF-01 … WF-15.json     15 importable n8n workflows, each with a
│                              sticky-note header documenting its contract
├── dashboard/
│   └── index.html          WF-09/10/13 frontend — static file, no build step,
│                            no Supabase credential (calls n8n webhooks only)
├── external-templates/      Google Sheets templates (WF-01 staging + errors),
│                            daily checklist, campaign intake form, rejection
│                            reason taxonomy — see external-templates/README.md
├── prompts/                researcher.md, personalizer.md, classifier.md (AI
│                            prompts), scorer.md (reference only — scoring is
│                            deterministic, see python/scoring/engine.py)
└── tests/                  56 tests, mirrors the python/ package structure
```

## Deploying this

Two guides, pick whichever matches your situation:

- **`DEPLOYMENT.md`** — get one VPS, run n8n and Python together on it
  (n8n's Execute Command nodes call Python directly, since they share a
  machine). Start here if you have nothing set up yet.
- **`RAILWAY_DEPLOYMENT.md`** — if you're already hosting n8n on Railway.
  Adds Python as a second, private-networked Railway service in the same
  project; n8n calls it over HTTP instead of shelling out to it (Railway
  services can't shell into each other). Both guides assume you've done
  Supabase setup (below) and read `external-templates/README.md` for the
  Google Sheet either way.

## Setup

### 1. Database

```bash
# Fresh Supabase project (or any Postgres): run once
psql "$DATABASE_URL" -f database/schema.sql
psql "$DATABASE_URL" -f database/seed.sql   # optional, dev/test data
```

If you're evolving an existing database instead of starting fresh, run new
files under `database/migrations/` individually — don't re-run all of
`schema.sql` against a live database that already has data.

### 2. Python

```bash
cd hooze-outbound
pip install -r python/requirements.txt --break-system-packages
```

Set these environment variables (a local `.env` works for dev — see
`python/config.py`'s module docstring — or set them directly in your n8n
instance's environment for production):

```
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
AI_PROVIDER=gemini            # or groq
GEMINI_API_KEY
GROQ_API_KEY
RESEARCH_MAX_FETCHES_PER_COMPANY=6   # optional, defaults to 6
```

Run the tests (no live Supabase/AI credentials needed — see "Testing"
below):

```bash
python3 -m pytest tests/ -v
```

### 3. n8n

1. Import each `n8n/WF-*.json` file (Workflows → Import from File).
2. On every Supabase-typed node, point the credential at your project.
3. On every Execute Command node, confirm the working directory
   (`/opt/hooze-outbound` by default in the generated JSON — edit if your
   deployment path differs) has this repo checked out with
   `pip install -r python/requirements.txt` already run, and that
   `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` / `GEMINI_API_KEY` /
   `GROQ_API_KEY` are visible to the n8n process's environment.
4. Activate WF-02 through WF-15. WF-01 needs a Google Sheets staging tab —
   see `external-templates/README.md` for the exact tab names, columns, and
   how to wire the Sheet ID into the workflow.
5. Add a shared-secret check to the WF-09/WF-10/WF-13 webhook nodes per
   `docs/14-security-spec.md` §3 — see `BUILD_LOG.md` §8 for what's already
   wired vs. what's left to you here.

To change a workflow, edit `n8n/generate_workflows.py` and re-run
`python3 n8n/generate_workflows.py` — don't hand-edit the JSON files, they
get overwritten.

### 4. Dashboard

Open `dashboard/index.html` in a browser, or serve it from any static host.
Edit the `WEBHOOKS` object near the top of its `<script>` block with the
three webhook URLs from your activated WF-09/WF-10/WF-13 workflows. It
holds no Supabase credential of its own — see `BUILD_LOG.md` §8 for why.

## Testing without live Supabase

Every module is split into pure functions (unit-testable with no network)
plus a thin DB-touching wrapper at the bottom of the file (not tested here,
since it needs real credentials). `tests/` covers the pure-function side:
scoring math, evidence/provenance rules, personalization validation,
classification's hard rules, dedup/normalization logic, follow-up cadence,
campaign matching, and analytics formulas. Run with:

```bash
python3 -m pytest tests/ -v
```

56 tests, all passing as of this build. The database layer was separately
verified end-to-end against a real local PostgreSQL instance (schema +
seed data applied cleanly) — see `BUILD_LOG.md` §10.

## Build order (per docs/01 §7 and docs/13) — status

1. ✅ Database
2. ✅ Lead ingestion (WF-01) — n8n workflow built; needs your Google Sheet ID
3. ✅ Cleaning + deduplication (WF-02, WF-03)
4. ✅ ICP scoring (WF-06) — deterministic, tested against seed data
5. ✅ Research engine (WF-05)
6. ✅ Personalization engine (WF-08)
7. ✅ Human review dashboard (WF-09)
8. ✅ Outreach logging (WF-10)
9. ✅ Follow-up engine (WF-11)
10. ✅ Response classification (WF-12)
11. ✅ Sales pipeline (WF-13)
12. ✅ Analytics (WF-14) — with three documented, non-fabricated metric gaps, see BUILD_LOG.md §6
13. ✅ Error monitoring (WF-15)

**Do not automate sending before steps 1–7 work end-to-end against real
data.** See `docs/01-system-prd.md` §9.6 — this remains true regardless of
what's built; human approval on every send is a design invariant, not a
placeholder.

## First campaign

Campaign 001 is locked in `docs/09-campaign-spec.md`: Abuja real estate
agencies, WhatsApp lead qualification + inspection booking automation
(Hooze CRM), proof = Praise Dynasty Realty deployment. Seeded in
`database/seed.sql` alongside two sample leads for testing the pipeline
end-to-end.

## What's intentionally not built

- Auto-send (V1 requires human approval on every message, including
  follow-ups) — enforced structurally (`outreach.status` state machine),
  not just by convention.
- Multi-operator roles/permissions.
- Score decay / re-verification of stale leads.
- AI-assisted scoring (scoring is deterministic by design — see
  `python/scoring/engine.py` and `prompts/scorer.md`).
- Campaigns 002/003 (drafted in docs, not activated — see docs/09 §6).
- Three analytics metrics the current schema can't correctly compute
  (time-to-review, edit rate, per-variant breakdown) — documented rather
  than approximated with invented numbers. See `BUILD_LOG.md` §6.
- Live end-to-end testing against a real Supabase project and real
  Gemini/Groq credentials (this environment doesn't have them) — every
  code path was verified by unit test, live local database test, or code
  review instead. See `BUILD_LOG.md` §9–10.
