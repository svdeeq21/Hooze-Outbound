# 12 — Response Classification Specification

**Version:** 1.0 · **Depends on:** 03, 04, 11

## 1. Categories

| Classification | Meaning | Routing |
|---|---|---|
| INTERESTED | Positive engagement, wants to know more | → create/promote `opportunities` row, notify Hooze immediately, stop follow-ups |
| QUESTION | Asking for clarification, not yet a clear yes/no | → surface in review queue for a direct human reply (not automated), stop follow-ups |
| PRICE | Asking about cost | → create sales task, notify Hooze immediately, stop follow-ups |
| MEETING | Explicitly agreeing to or requesting a call/meeting | → create `opportunities` row (stage=MEETING), notify Hooze immediately, stop follow-ups |
| LATER | Interested but not now ("check back in X") | → stop current follow-up cadence, schedule a single re-engagement reminder for Hooze at the stated time (or +30 days if unspecified); company stays CONTACTED, not DEAD |
| NOT_INTERESTED | Explicit decline | → stop follow-ups for this campaign, company status per 11-follow-up.md §3 |
| WRONG_PERSON | Reached the wrong contact | → update `contacts` confidence/flag, do not mark company DEAD — allow re-research for correct contact, stop this outreach cycle |
| UNSUBSCRIBE | Explicit opt-out request | → hard stop, company → DEAD permanently, never re-contacted by any campaign (see §3) |
| UNKNOWN | Doesn't clearly fit any category | → surface to Hooze for manual classification, stop automated follow-ups pending manual review |

## 2. Classification input

The classifier (prompt in `prompts/classifier.md`) receives:

```json
{
  "outreach_message": "the original sent message",
  "response_text": "the prospect's reply",
  "campaign": { "offer": "...", "cta": "..." }
}
```

Output must be exactly one of the nine categories above, plus a `sentiment` (POSITIVE/NEUTRAL/NEGATIVE) and a short `intent` free-text summary.

## 3. UNSUBSCRIBE handling (hard rule)

Any reply containing an explicit opt-out ("stop messaging me," "remove me," "unsubscribe," "don't contact again," or equivalent) must be classified UNSUBSCRIBE regardless of any other content in the message, and this overrides every other rule in this document and in 11-follow-up.md. The company is set DEAD across all campaigns, not just the current one, and this is enforced at the `companies` level, not the `outreach` level, so no future campaign can re-add them without a manual, logged override.

## 4. Ambiguous cases

If confidence in the classification is low, the classifier should prefer UNKNOWN over guessing INTERESTED or NOT_INTERESTED — a false positive on INTERESTED wastes Hooze's time on a dead end, a false positive on NOT_INTERESTED loses a real opportunity. UNKNOWN always routes to a human, which is the safe default.

## 5. Logging

Every classification decision is stored in `responses.classification` with the raw `response_text` preserved verbatim, so classifier accuracy can be audited and improved over time (feeds 15-analytics-spec.md).
