# 15 — Analytics Specification

**Version:** 1.0 · **Depends on:** all prior docs

## 1. Purpose

Turns pipeline data into the conversion numbers referenced in 01-system-prd.md §8 success metrics. This is what tells Hooze whether to change the ICP, offer, research process, or message — not just "send more."

## 2. Core funnel

```
DISCOVERED → CLEANED → RESEARCHED → QUALIFIED → PERSONALIZED
→ APPROVED → CONTACTED → REPLIED → MEETING → PROPOSAL → WON
```

Computed weekly (WF-14) as both absolute counts and stage-to-stage conversion percentages, overall and sliced by:

- **Campaign** (`campaigns.name`)
- **Channel** (EMAIL vs WHATSAPP)
- **Source** (`companies.source`)
- **Message variant** (if 08-personalization-spec.md §7 variants are used)

## 3. Key metrics

| Metric | Formula | Purpose |
|---|---|---|
| Qualification rate | QUALIFIED / CLEANED | Is the ICP/scoring model too strict or too loose |
| Reply rate | REPLIED / CONTACTED | Overall message + targeting quality |
| Positive rate | (INTERESTED+MEETING+PRICE) / REPLIED | Quality of replies, not just volume |
| Meeting rate | MEETING / CONTACTED | End-to-end effectiveness |
| Win rate | WON / MEETING | Sales close effectiveness (less about the OS, more a sales-skill signal, still tracked) |
| Time-to-review | avg(REVIEW timestamp − RESEARCHED timestamp) | Pipeline speed, target < 24h per PRD |
| Edit rate | EDITED approvals / total APPROVED | Personalization engine quality — high edit rate signals prompt/evidence problems |
| Rejection rate | REJECTED / (APPROVED+REJECTED) | Same, plus rejection reasons (10-outreach-sop.md §3) categorized and reviewed monthly |
| Unsubscribe rate | UNSUBSCRIBE / CONTACTED | Message/targeting quality ceiling check — rising rate is a hard stop signal |

## 4. Campaign performance view

For each campaign: qualification rate, reply rate, positive rate, meeting rate, and sample size — displayed together so Hooze doesn't over-react to small-sample noise (e.g. a campaign with 8 sends shouldn't be judged the same as one with 80).

## 5. Message performance view

Per message variant (where used): reply rate and positive rate, to determine which opening-observation pattern or CTA phrasing performs better. Feeds back into `prompts/personalizer.md` iteration.

## 6. Source quality view

Per `companies.source`: qualification rate and eventual reply rate, to determine which discovery channel (Google Maps, LinkedIn, etc.) produces the best leads — informs where to spend limited manual discovery time.

## 7. Experimentation framework (lightweight, V1)

- Campaigns and message variants are the only formal "experiments" in V1 — no statistical significance tooling, just sample-size-aware reporting per §4.
- Any deliberate test (e.g. new CTA wording) should be logged with a start date so before/after comparison is possible.

## 8. Dashboard surfacing

Weekly summary (not daily — per 10-outreach-sop.md §7, analytics is a weekly check, not a daily distraction) showing: funnel snapshot, campaign comparison table, and any metric crossing a concerning threshold (e.g. unsubscribe rate spike, rejection rate spike) flagged at the top.

## 9. Feedback loop (explicit, closes the system)

```
Analytics reveals a weak stage
        ↓
Qualification rate low   → revisit 02-icp-spec.md / 06-scoring-engine.md
Reply rate low            → revisit 08-personalization-spec.md / 09-campaign-spec.md offer-pain fit
Positive rate low but
reply rate ok              → revisit CTA / offer framing, not targeting
Meeting rate low despite
positive replies           → revisit 10-outreach-sop.md response speed/handling
Edit/rejection rate high   → revisit 07-research-engine.md evidence quality
                              and prompts/personalizer.md
```

This loop is the point of the entire system — per 01-system-prd.md, the primary success metric is learning velocity, and this document is where that learning becomes actionable.
