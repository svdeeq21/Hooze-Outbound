# 06 — Scoring Specification

**Version:** 1.0 · **Depends on:** 02-icp-spec.md, 03-data-dictionary.md

## 1. Purpose

Deterministic, auditable scoring — no black-box AI scoring in V1. Every point awarded traces to a rule in this document so `lead_scores.reason` can always explain itself in plain language.

## 2. Score components

```
ICP FIT              0–25
PAIN SIGNAL           0–25
BUYING SIGNAL         0–20
CONTACTABILITY        0–15
PERSONALIZATION       0–15
──────────────────────────
TOTAL                 0–100
```

### 2.1 ICP Fit (0–25)

| Condition (from 02-icp-spec.md §2) | Points |
|---|---|
| Industry matches an active campaign's vertical exactly | +10 |
| Location matches active campaign geography | +5 |
| Online presence requirement met (website or active social with listings) | +5 |
| Contact channel (WhatsApp) visible/inferable | +5 |
| Any disqualifier present (§2.2) | Score forced to 0, priority = DONT_CONTACT, all other components skipped |

### 2.2 Pain Signal (0–25)

+5 per matched pain signal from 02-icp-spec.md §3, up to 5 signals (25 max). Each match must have a corresponding `research_evidence` row — an unsupported pain signal does not count.

### 2.3 Buying Signal (0–20)

+5 per matched buying signal from 02-icp-spec.md §4, up to 4 signals (20 max). Same evidence requirement as pain signals.

### 2.4 Contactability (0–15)

| Contact confidence (03-data-dictionary.md `contacts.confidence`) | Points |
|---|---|
| HIGH (named person + direct contact) | 15 |
| MEDIUM (named person, generic contact) | 10 |
| LOW (business only, no named contact) | 5 |
| None found | 0 (and lead does not progress past CLEANED per 05-lead-lifecycle.md) |

### 2.5 Personalization Potential (0–15)

Based on volume of usable, sourced evidence in `research_evidence`:

| Evidence rows with confidence HIGH or MEDIUM | Points |
|---|---|
| 5+ | 15 |
| 3–4 | 10 |
| 1–2 | 5 |
| 0 | 0 (lead cannot enter PERSONALIZED state per 05-lead-lifecycle.md — personalization engine has nothing to ground a message in) |

## 3. Tiering

| Total score | Tier | Action |
|---|---|---|
| 80–100 | A | Top of review queue, prioritized for send |
| 65–79 | B | Qualified, standard queue |
| 50–64 | C | Held — visible in dashboard as "below threshold," not auto-queued for personalization; Hooze can manually promote |
| < 50 | DONT_CONTACT | Excluded from all outreach workflows; status may still advance for record-keeping but no `outreach` row is ever created |

`QUALIFIED` lifecycle state (05-lead-lifecycle.md) requires total_score ≥ 65 (tier A or B).

## 4. Re-scoring

A company is re-scored whenever `research` or `research_evidence` changes materially (new evidence added), or on a scheduled weekly re-score pass for companies still sitting below QUALIFIED — pain/buying signals can appear later (e.g. a hiring ad posted after initial research).

## 5. Score decay (future, not V1)

Not implemented in V1. Flagged here for V2: leads sitting unreached for 60+ days should have contactability/buying-signal confidence re-verified before send, since a phone number or hiring signal can go stale.

## 6. Worked examples

**Example — high score:**
```
Company: Prime Estate
ICP:              23/25  (industry+location+presence+channel all match)
Pain:             20/25  (4 evidenced pain signals)
Buying signal:    15/20  (3 evidenced buying signals)
Contactability:   14/15  (HIGH-confidence named contact via LinkedIn)
Personalization:  13/15  (4 usable evidence rows)
TOTAL:            85/100 → Tier A
```

**Example — below threshold:**
```
Company: Random Realty Page
ICP:              18/25  (industry+location match, weak online presence)
Pain:               6/25  (1 evidenced pain signal)
Buying signal:       3/20  (0 evidenced, partial credit for weak proxy)
Contactability:      7/15  (LOW confidence, generic inbox only)
Personalization:     5/15  (1 evidence row)
TOTAL:              39/100 → DONT_CONTACT
```
