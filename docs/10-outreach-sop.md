# 10 — Outreach SOP

**Version:** 1.0 · **Depends on:** 05, 08, 09

## 1. Purpose

Defines exactly what Hooze does at each manual step. The system prepares; this document is Hooze's own operating procedure.

## 2. `outreach.status` sub-state machine

```
DRAFT → PENDING_REVIEW → APPROVED → SENT → ACTIVE
                       ↘ REJECTED (terminal, company stays QUALIFIED,
                                    can be re-personalized later)

ACTIVE → REPLIED (on inbound response, see 12-response-classification.md)
ACTIVE → NOT_INTERESTED (explicit negative reply)
ACTIVE → DEAD (max follow-ups reached, no reply — see 11-follow-up.md)
```

## 3. Review queue procedure (daily)

1. Open dashboard, filter to `REVIEW` state, sorted by `lead_scores.priority` (A before B).
2. For each lead, read: score breakdown + reason, evidence list, draft message(s).
3. Decide:
   - **APPROVE** — message sent as-is. `outreach.status → APPROVED`, `approved_by = "hooze"`, `approved_at = now()`.
   - **EDIT** — modify message text in the dashboard, then approve. Edited text is what gets logged as `outreach.message` (original AI draft is not overwritten in logs — kept in a `draft_history` note field or workflow log for personalization-quality tracking, see 15-analytics-spec.md).
   - **REJECT** — `outreach.status → REJECTED`. Company `status` reverts to `QUALIFIED`. A rejection reason is logged (bad evidence, wrong tone, not actually a fit, etc.) — this reason feeds scoring/research quality improvements.
4. No message is sent from this step directly — approval queues it for §4.

## 4. Sending procedure (manual, V1)

1. For each `APPROVED` outreach row, Hooze sends the message via the actual channel (WhatsApp Web/Business app, or Gmail).
2. Immediately after sending, Hooze marks it sent in the dashboard: `outreach.status → SENT`, `sent_at = now()`, then system auto-transitions to `ACTIVE` and schedules the first follow-up per 11-follow-up.md.
3. Company `status → CONTACTED`.
4. **Never send the same company through two channels or two campaigns concurrently** — the dashboard blocks this per the lifecycle guardrail in 05-lead-lifecycle.md §4, but Hooze should also visually confirm no other ACTIVE outreach exists for that company before sending.

## 5. What Hooze does NOT do in V1

- Does not write messages from scratch (comes from personalization engine)
- Does not manually score leads (comes from scoring engine) — but can override a score with a documented reason if the engine is clearly wrong, logged for scoring-rule improvement
- Does not send without an APPROVED row existing first

## 6. Escalation

If a reply arrives that's clearly high-value (classification = MEETING or INTERESTED, see 12-response-classification.md), the follow-up engine stops automatically and the lead surfaces at the top of Hooze's daily review, flagged for immediate personal handling — not left in the automated queue.

## 7. Daily operating checklist

```
[ ] Check WF-15 error monitor for failed workflow runs
[ ] Review REVIEW queue (approve/edit/reject)
[ ] Send all APPROVED messages
[ ] Mark sent messages as SENT in dashboard
[ ] Check REPLIED leads — classify/confirm classification, act on
    INTERESTED/MEETING/PRICE immediately
[ ] Check analytics dashboard weekly (not daily) for funnel movement
```
