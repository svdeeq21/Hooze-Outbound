# 08 — Personalization Specification

**Version:** 1.0 · **Depends on:** 03, 06, 07, 09-campaign-spec.md

## 1. Purpose

Defines exactly how a personalized message is generated and what it is and isn't allowed to say. This is the anti-hallucination control layer referenced throughout the PRD.

## 2. Input contract to the AI layer

The personalization engine is **never** given a free-text "write a personalized message" prompt. It receives a structured object:

```json
{
  "company": "Prime Estate",
  "industry": "Real Estate",
  "location": "Abuja",
  "campaign": {
    "offer": "WhatsApp lead qualification and inspection booking automation",
    "pain": "Manual, slow WhatsApp inquiry handling",
    "proof": "Praise Dynasty Realty case study",
    "cta": "Offer a short demonstration"
  },
  "evidence": [
    { "claim": "WhatsApp contact button visible on homepage", "source_url": "...", "confidence": "HIGH" },
    { "claim": "40+ active property listings", "source_url": "...", "confidence": "HIGH" },
    { "claim": "No visible automated qualification or booking flow", "source_url": "...", "confidence": "MEDIUM" }
  ],
  "observed_problem": "WhatsApp inquiries may require repeated manual qualification",
  "contact": { "name": "Mr. Sunday", "title": "Managing Director", "confidence": "HIGH" }
}
```

The full researcher/scorer/personalizer/classifier prompt text lives in `prompts/personalizer.md` — this document defines the rules that prompt must enforce, not the prompt itself.

## 3. Allowed claims

- Any claim present in `evidence[]` with confidence HIGH or MEDIUM
- The `observed_problem` hypothesis, phrased as a hypothesis ("I noticed X — wondering if that means Y"), never as an asserted fact
- General statements about Hooze Enterprises' offer, proof, and CTA (these are Hooze's own claims, not claims about the prospect)

## 4. Forbidden claims

- Any statement about the prospect not present in `evidence[]`
- Numbers not present in evidence (e.g. inventing "your team of 5 agents" without a source)
- Assuming pain not evidenced ("I know your leads are falling through the cracks" when observed_problem is only a hypothesis)
- Fabricated familiarity ("I saw we have mutual connections") unless evidenced
- Claims about competitors, market conditions, or anything outside the evidence set and campaign object

## 5. Message structure

```
1. Opening observation   — grounded in 1 (max 2) evidence claims
2. Pain hypothesis        — phrased as a question or soft observation, not asserted
3. Offer                  — from campaign.offer
4. Proof (optional)       — from campaign.proof, one line
5. CTA                    — from campaign.cta
```

Target length: WhatsApp messages ≤ 80 words; email ≤ 150 words. Longer drafts get flagged for edit at review, not auto-shortened by the AI (shortening can silently drop evidence grounding).

## 6. Message validation (automated, pre-review)

Before a draft reaches the human review queue, an automated check verifies:

- [ ] Every specific factual claim in the message text can be matched to an `evidence[]` entry (fuzzy match on key phrases/numbers)
- [ ] No numbers appear in the message that don't appear in `evidence[]`
- [ ] The CTA matches `campaign.cta`
- [ ] Message length within the channel limit in §5
- [ ] No competitor names, no unrelated claims

Any failed check routes the draft to REVIEW with a warning flag rather than blocking it outright — Hooze makes the final call, per the human-review-queue principle in 01-system-prd.md.

## 7. Variants

The personalization engine may generate up to 2 message variants per lead (e.g. different opening observation) so Hooze can pick or A/B test. Variant performance feeds 15-analytics-spec.md.

## 8. Tone

- Direct, specific, no generic flattery ("I hope this finds you well" is banned — matches Hooze's own communication style: direct, minimal, no filler)
- No exclamation-mark-heavy sales language
- Written to read like it came from a founder who actually looked at the business, not a template
