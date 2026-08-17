# 13 — n8n Workflow Architecture

**Version:** 1.0 · **Depends on:** all prior docs

## 1. Principle

15 small, independently testable workflows, not one monolith. Each has a defined trigger, input, processing summary, output, database operations, and error path. n8n is the orchestrator; Python (14 modules under `python/`) does the heavy processing; Supabase is the source of truth.

## 2. Workflow contracts

### WF-01 — Lead Import
- **Trigger:** Manual run / scheduled (daily), or webhook from a staging Google Sheet update
- **Input:** Raw rows from Google Sheets staging tab
- **Processing:** Basic field mapping to `companies` schema shape
- **Output:** New `companies` rows, `status = DISCOVERED`
- **DB ops:** Insert into `companies`
- **Error path:** Malformed rows logged to an `import_errors` sheet tab, not silently dropped; workflow continues with valid rows
- **Credentials:** Google Sheets API

### WF-02 — Lead Cleaning
- **Trigger:** New row with `status = DISCOVERED`
- **Input:** `companies` row
- **Processing:** Calls `python/enrichment/normalize.py` — computes `normalized_name`, `phone_normalized`, `email_normalized`
- **Output:** Updated row, `status = CLEANED` (pending dedup in WF-03)
- **DB ops:** Update `companies`
- **Error path:** Rows failing normalization (e.g. unusable phone format) flagged, status stays DISCOVERED, surfaced in WF-15 error monitor

### WF-03 — Lead Deduplication
- **Trigger:** After WF-02
- **Input:** Normalized `companies` row
- **Processing:** Query existing `companies` for matches on `normalized_name`+`location`, `phone_normalized`, or `email_normalized`
- **Output:** Duplicate → merged/discarded (log which survived); unique → proceeds, `status` stays CLEANED
- **DB ops:** Select + conditional delete/merge on `companies`
- **Error path:** Ambiguous matches (partial overlap) flagged for manual review, not auto-merged

### WF-04 — Lead Enrichment
- **Trigger:** After WF-03, `status = CLEANED`
- **Input:** `companies` row
- **Processing:** Calls `python/enrichment/` to fill gaps (e.g. resolve domain from name, find social handles)
- **Output:** Enriched `companies` row
- **DB ops:** Update `companies`
- **Error path:** Enrichment failures don't block progression — proceeds to research with whatever's available

### WF-05 — Website/Evidence Research
- **Trigger:** After WF-04
- **Input:** `companies` row (website, socials)
- **Processing:** Calls `python/research/` per the interface in 07-research-engine.md
- **Output:** `research` + `research_evidence` rows, `status = RESEARCHED`
- **DB ops:** Insert `research`, insert `research_evidence` (multiple rows)
- **Error path:** Zero evidence found → status stays RESEARCHED but flagged low-quality; will score near 0 on personalization component (06-scoring-engine.md)

### WF-06 — ICP Scoring
- **Trigger:** After WF-05
- **Input:** `companies`, `research`, `research_evidence`, `contacts`
- **Processing:** Calls `python/scoring/` implementing 06-scoring-engine.md rules exactly (deterministic, no AI)
- **Output:** `lead_scores` row, `companies.status = QUALIFIED` if total ≥ 65, else stays RESEARCHED (visible as tier C/DONT_CONTACT in dashboard)
- **DB ops:** Insert `lead_scores`, update `companies.status`
- **Error path:** Missing required inputs (e.g. no contacts row) → contactability_score = 0, scoring proceeds with the rest, does not fail the whole workflow

### WF-07 — Campaign Assignment
- **Trigger:** After WF-06, `status = QUALIFIED`
- **Input:** `companies`, active `campaigns`
- **Processing:** Matching logic from 09-campaign-spec.md §4
- **Output:** Campaign match recorded (used by WF-08); if no match, lead stays QUALIFIED and visible as unmatched
- **DB ops:** Read `campaigns`, no write until WF-08 creates the `outreach` row

### WF-08 — Message Generation
- **Trigger:** After WF-07 match found
- **Input:** Structured object per 08-personalization-spec.md §2
- **Processing:** Calls `python/personalization/` → AI call using `prompts/personalizer.md`, then automated validation (08-personalization-spec.md §6)
- **Output:** `outreach` row, `status = DRAFT` → `PENDING_REVIEW`; `companies.status = PERSONALIZED` → `REVIEW`
- **DB ops:** Insert `outreach`
- **Error path:** Validation failures flagged in the row (warning field) but still routed to review, per 08-personalization-spec.md §6

### WF-09 — Human Approval (dashboard-backed)
- **Trigger:** Dashboard action (Approve/Edit/Reject)
- **Input:** Hooze's decision
- **Processing:** Per 10-outreach-sop.md §3
- **Output:** `outreach.status` updated accordingly
- **DB ops:** Update `outreach`, update `companies.status`

### WF-10 — Outreach Queue / Send Confirmation
- **Trigger:** Dashboard action ("mark as sent")
- **Input:** `outreach` row id
- **Processing:** Per 10-outreach-sop.md §4; schedules first follow-up
- **Output:** `outreach.status = SENT → ACTIVE`, `next_follow_up_at` set, `companies.status = CONTACTED`
- **DB ops:** Update `outreach`

### WF-11 — Follow-up Scheduler
- **Trigger:** Scheduled, daily
- **Input:** `outreach` rows where `status = ACTIVE` and `next_follow_up_at <= now()`
- **Processing:** Per 11-follow-up.md §2
- **Output:** New follow-up drafted into review queue, or status → DEAD
- **DB ops:** Update `outreach`, insert new draft row if generating a follow-up

### WF-12 — Response Processing
- **Trigger:** Inbound message webhook (WhatsApp/email) or manual entry
- **Input:** Raw reply text + reference to `outreach_id`
- **Processing:** Calls `python/classification/` using `prompts/classifier.md`, per 12-response-classification.md
- **Output:** `responses` row, `outreach.status` updated, follow-ups stopped
- **DB ops:** Insert `responses`, update `outreach`, update `companies.status = REPLIED`
- **Error path:** Classification failures default to UNKNOWN (safe default per 12-response-classification.md §4)

### WF-13 — Opportunity Management
- **Trigger:** Manual dashboard action, or automatic on classification = INTERESTED/MEETING/PRICE
- **Input:** `company_id`, stage
- **Processing:** Create/update `opportunities` row
- **Output:** `opportunities` row, `companies.status` updated (MEETING/PROPOSAL/WON/LOST)
- **DB ops:** Insert/update `opportunities`

### WF-14 — Analytics
- **Trigger:** Scheduled (daily/weekly aggregation)
- **Input:** All pipeline tables
- **Processing:** Computes funnel metrics per 15-analytics-spec.md
- **Output:** Aggregated metrics written to an `analytics_snapshots` table or view, surfaced on dashboard
- **DB ops:** Read all tables, write aggregates

### WF-15 — Error Monitoring
- **Trigger:** Runs on every other workflow's error path (n8n error-trigger pattern), plus scheduled health check
- **Input:** Error events from WF-01 through WF-14
- **Processing:** Aggregates failures, flags data-quality issues (e.g. leads stuck in one state too long)
- **Output:** Notification to Hooze (Telegram/Gmail, consistent with existing n8n content pipeline pattern), dashboard error log
- **DB ops:** Insert into an `error_log` table (see 04-database-schema.md extension if needed)

## 3. Master orchestrator (optional convenience layer)

```
DAILY OUTBOUND CONTROLLER
  ├── WF-01 Discover
  ├── WF-02→04 Clean/Enrich
  ├── WF-05 Research
  ├── WF-06 Score
  ├── WF-07 Assign
  ├── WF-08 Generate
  ├── (WF-09/10 wait on Hooze — not orchestrated)
  ├── WF-11 Follow-up check
  └── WF-14 Analytics (weekly)
```

This can be a single scheduled n8n workflow that calls WF-01 through WF-08 in sequence via sub-workflow execution, but each remains independently runnable and testable on its own for debugging — matching the existing pattern already used in the "Building 100 Automations" n8n system (Main Orchestrator + separate workflow JSONs).

## 4. Inter-workflow contract format

Every workflow JSON file under `n8n/` should include a header comment (n8n sticky note) stating: trigger, expected input shape, expected output shape, and which tables it touches — so any workflow can be understood and modified without re-reading this whole document.
