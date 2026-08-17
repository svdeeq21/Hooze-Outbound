# 11 — Follow-up Specification

**Version:** 1.0 · **Depends on:** 04, 10

## 1. Default cadence

```
Day 0  → Initial message (sent manually per 10-outreach-sop.md)
Day 3  → Follow-up 1
Day 7  → Follow-up 2
Day 14 → Follow-up 3 (final)
```

A campaign may override this cadence in its `campaigns` row config (09-campaign-spec.md), but Campaign 001 uses the default.

## 2. Scheduler logic (runs daily — WF-11)

```
SELECT * FROM outreach
WHERE status = 'ACTIVE'
AND next_follow_up_at <= NOW()
```

For each matching row:

```
IF a response exists (responses.outreach_id = this row)
    → STOP (do not generate a follow-up; status already moved to
      REPLIED/NOT_INTERESTED via WF-12)

IF follow_up_number >= 3 (max attempts reached)
    → outreach.status = 'DEAD'
    → companies.status = 'DEAD' (only if no other active
      campaign/opportunity exists for this company)

ELSE
    → generate follow-up message (personalization engine, using
      original evidence + campaign, referencing it's a follow-up)
    → follow_up_number += 1
    → new outreach sub-row enters PENDING_REVIEW (same review gate
      as initial message — follow-ups are approved too, not
      auto-sent)
    → next_follow_up_at = NOW() + cadence interval for the next step
```

## 3. Stop conditions (any of these halts follow-ups immediately)

- A `responses` row exists for this `outreach_id` (any classification)
- Classification = UNSUBSCRIBE (immediate hard stop, company → DEAD, never re-contacted by any campaign — see 12-response-classification.md)
- Classification = NOT_INTERESTED (stop this campaign's follow-ups; company may still be eligible for a different campaign later, but not this one)
- Max follow-up count reached (3, per §1)
- Company manually marked DEAD by Hooze for any reason

## 4. Follow-up message rules

- Must acknowledge it's a follow-up (not repeat the exact opening line)
- Still bound by 08-personalization-spec.md evidence rules — no new unevidenced claims
- Each follow-up still goes through the human review queue (10-outreach-sop.md §3) — V1 does not auto-send follow-ups either

## 5. Timing adjustment (future, not V1)

Cadence is fixed in V1. Once enough data exists (15-analytics-spec.md), the interval between follow-ups should be tuned per campaign based on actual reply-timing distribution rather than the flat 3/7/14 default. Flagged for V2.
