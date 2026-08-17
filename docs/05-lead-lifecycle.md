# 05 — Lead Lifecycle Specification

**Version:** 1.0 · **Depends on:** 02, 03, 04

## 1. States

```
DISCOVERED → CLEANED → RESEARCHED → QUALIFIED → PERSONALIZED
→ REVIEW → APPROVED → CONTACTED → REPLIED
                                     ├─→ MEETING → PROPOSAL → WON
                                     ├─→ PROPOSAL → LOST
                                     └─→ DEAD
(any state) → DEAD
```

`companies.status` holds exactly one of these values at any time. This is the single source of truth for where a lead is — no workflow infers status from other tables.

## 2. State definitions and entry conditions

| State | Meaning | Entry condition |
|---|---|---|
| DISCOVERED | Raw lead ingested, unprocessed | Row created by any discovery source (WF-01) |
| CLEANED | Normalized, deduplicated, passed basic validation | Normalization + dedup check passed (WF-02/03) |
| RESEARCHED | Evidence gathered and stored in `research` + `research_evidence` | Research engine completed with ≥1 evidence row (WF-05) |
| QUALIFIED | Scored ≥ 65 (tier A or B) per 06-scoring-engine.md | `lead_scores.total_score >= 65` |
| PERSONALIZED | Draft message generated, grounded in evidence | Personalization engine produced a message referencing only `research_evidence` claims (WF-08) |
| REVIEW | Sitting in Hooze's human review queue | Row appears in dashboard (WF-09) |
| APPROVED | Hooze approved the message, possibly edited | Manual action in dashboard |
| CONTACTED | Message actually sent | Hooze marks as sent (or, in later phases, automated send confirms delivery) |
| REPLIED | Prospect responded | Inbound message/reply captured and classified (WF-12) |
| MEETING | A call/meeting is scheduled | Manual promotion from REPLIED after classification = MEETING or INTERESTED handled to booking |
| PROPOSAL | Pricing/proposal sent | Manual promotion |
| WON | Client signed | Manual promotion, triggers opportunity stage WON |
| LOST | Deal did not close | Manual demotion from MEETING/PROPOSAL |
| DEAD | No longer pursued | Disqualified at any stage: failed ICP, opted out, not interested, max follow-ups reached with no reply |

## 3. Transition rules

- A company can only move **forward** through DISCOVERED→CLEANED→RESEARCHED→QUALIFIED→PERSONALIZED→REVIEW→APPROVED→CONTACTED automatically (each workflow only advances state, never skips one).
- From CONTACTED, the only automatic transitions are: → REPLIED (inbound message received) or → DEAD (max follow-ups exhausted, see 11-follow-up.md).
- MEETING / PROPOSAL / WON / LOST are **manual promotions only** — no workflow moves a lead into the sales pipeline stages automatically. This keeps Hooze as the final sales authority (01-system-prd.md §9.6).
- DEAD is reachable from any state and is terminal. A DEAD company is never re-contacted by the same campaign. Re-engagement (e.g. 6 months later, new campaign) requires a manual reset, logged with a reason.
- A company can belong to only one active campaign's outreach cycle at a time — the system checks `outreach` for any row with status in (`SENT`,`ACTIVE`) before allowing a new campaign to contact the same `company_id`.

## 4. Guardrails this prevents

- **Double contact:** the "one active outreach cycle" rule stops a lead being messaged on WhatsApp and email simultaneously by two different campaigns.
- **Contacting DEAD leads:** every outreach-triggering workflow filters `where status not in ('DEAD','WON','LOST')` before doing anything.
- **Silent skips:** because state only moves forward one step at a time (except → DEAD), a bug that tries to jump straight from RESEARCHED to CONTACTED without a human review is structurally impossible — REVIEW/APPROVED are mandatory gates in the query logic, not just UI conventions.

## 5. State ↔ table cross-reference

| State reached | Table(s) that must have a row |
|---|---|
| RESEARCHED | `research` (1 row), `research_evidence` (≥1 row) |
| QUALIFIED | `lead_scores` (latest row, total_score ≥ 65) |
| PERSONALIZED / REVIEW / APPROVED / CONTACTED | `outreach` (1 row per campaign cycle, status field tracks sub-state per 10-outreach-sop.md) |
| REPLIED | `responses` (≥1 row) |
| MEETING / PROPOSAL / WON / LOST | `opportunities` (1 row, stage field) |

Note `outreach.status` is a finer-grained sub-state machine (DRAFT/PENDING_REVIEW/APPROVED/REJECTED/SENT/ACTIVE/REPLIED/NOT_INTERESTED/DEAD) nested inside the company-level lifecycle — a company can be CONTACTED while its underlying outreach row cycles through follow-up sub-states. Detail in 11-follow-up.md.
