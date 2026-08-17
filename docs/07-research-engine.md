# 07 — Research Specification

**Version:** 1.0 · **Depends on:** 02, 03, 04

## 1. Purpose

Defines exactly what the research engine looks for, and enforces the evidence/provenance rule: **no fact enters `research` without a corresponding row in `research_evidence` carrying a source URL.**

## 2. Required interface (source-agnostic)

The research engine is defined as an interface, not a specific scraper (per 01-system-prd.md design principle #1):

```
INPUT:  company_id, website (optional), social handles (optional)
OUTPUT: {
  website_summary,
  services[],
  target_market,
  whatsapp_present,
  booking_process,
  lead_capture_process,
  proof,
  evidence[]   // each item: { claim, source_url, confidence }
}
```

Any implementation (direct HTTP fetch of public pages, a permitted API, manual research) satisfying this interface is acceptable and swappable without touching downstream workflows.

## 3. What the engine looks for

| Category | Specific checks |
|---|---|
| Website presence | Does a site exist, is it live, does it list services/properties |
| WhatsApp presence | Is a WhatsApp button/number/"chat with us" link visible |
| Listings | Number and recency of property listings, if a real estate lead |
| Booking/inquiry flow | Is there a visible booking tool (Calendly-style), form, or does it route straight to WhatsApp/phone |
| Team size signals | About page, LinkedIn company page headcount, number of agents listed |
| Social activity | Recency and frequency of posts, engagement level (qualitative, not scraped metrics unless a permitted API provides them) |
| Complaints/reviews | Public reviews (Google Business, Facebook) mentioning response time or service issues |
| Hiring activity | Public job posts (LinkedIn, Jobberman, etc.) for roles matching buying signals in 02-icp-spec.md §4 |
| Named decision-maker | About/Team page, LinkedIn, WHOIS (if permitted), public director listings |

## 4. Evidence rule (mandatory)

Every row written to `research_evidence` must have:

- `claim` — one specific, falsifiable observation (not an inference)
- `source_url` — where it was observed
- `confidence` — HIGH (directly stated on the source), MEDIUM (reasonably inferred from the source), LOW (weak/indirect signal)

**Example — correct:**
```
claim: "WhatsApp contact button visible on homepage"
source_url: "https://example.com"
confidence: HIGH
```

**Example — not allowed to be written as a bare claim without evidence:**
```
"Leads probably get lost because they don't have automation"
```
This is a hypothesis, not evidence. It belongs in `research.observed_problem` as a labeled hypothesis, and it must reference which evidence rows support it — see §5.

## 5. observed_problem vs. evidence

`research.observed_problem` is allowed to be an inferential hypothesis (e.g. "WhatsApp inquiries may require repeated manual qualification"), but:

- It must be phrased as an observation-grounded hypothesis, not a stated fact.
- It must be traceable to at least one `research_evidence` row (e.g. "no visible automated qualification" + "WhatsApp prominent").
- The personalization engine (08-personalization-spec.md) is only allowed to use `observed_problem` as a *hypothesis to open with*, never to assert as established fact in the message to the prospect.

## 6. Research completeness score

`research.research_score` (0–100, internal use only, not shown to prospect) reflects how much usable evidence was found:

| Evidence volume | Score |
|---|---|
| 5+ HIGH/MEDIUM evidence rows across ≥3 categories | 80–100 |
| 3–4 evidence rows across ≥2 categories | 50–79 |
| 1–2 evidence rows | 20–49 |
| 0 evidence rows | 0 — company cannot proceed past RESEARCHED with a usable QUALIFIED status (personalization_score in 06-scoring-engine.md will also be 0) |

## 7. Rate/quota discipline

Per 01-system-prd.md §7 (free ≠ unlimited): the research engine must batch requests, respect robots.txt and each source's terms, and cap requests per company (a hard ceiling, e.g. no more than N page fetches per company) so a single lead can't consume a disproportionate share of quota. Exact N is an implementation parameter set in `python/research/config`, not fixed in this spec.

## 8. Refresh policy

Research is not re-run automatically once `RESEARCHED` unless: (a) the company is re-entering the pipeline after being reset from DEAD, or (b) it's part of the weekly re-score pass for near-threshold leads (06-scoring-engine.md §4). Stale research (>90 days old) should be flagged in the dashboard before any send.
