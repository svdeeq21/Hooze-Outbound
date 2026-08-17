# Hooze Outbound OS — System PRD

**Version:** 1.0
**Owner:** Sadiq Shehu Musa (Hooze), Hooze Enterprises
**Status:** Draft — foundational contract for all downstream specs
**Last updated:** 2026-08-16

---

## 1. Purpose

Hooze Enterprises needs a repeatable way to find, research, and reach the right prospects for its AI/automation products (Hooze CRM, Hooze AI, Clinical Clarity, and done-for-you automation services) without buying tools, ad spend, or scraping infrastructure.

The Hooze Outbound OS is a self-hosted, free-tier outbound operating system that turns a defined ICP into a stream of qualified, evidence-based, personalized outreach — with a human approving every message before it goes out in V1.

It is not a cold-email blaster. It is a controlled pipeline: **Find → Research → Personalize → Review → Send → Track → Learn.**

## 2. Goals

- Produce a steady stream of qualified leads for Hooze Enterprises' target industries (starting with real estate, expanding by campaign) at ₦0 infrastructure cost.
- Attach verifiable evidence to every personalization claim — no hallucinated observations about a prospect.
- Give Hooze a single review queue where he approves/edits/rejects every outbound message before send.
- Track the full lifecycle of a lead from discovery to client, with enough data to compute real conversion rates per campaign, channel, and message variant.
- Keep the system operable by one person, part-time, without a dedicated ops team.
- Establish a state machine and data model that later phases (auto-send, richer scoring, more channels) can extend without a rebuild.

## 3. Non-Goals (V1)

- **No autonomous sending.** The system prepares; Hooze sends. Auto-send is a later phase, gated on data from V1.
- **No paid scraping, paid enrichment, paid email/WhatsApp infra.** Every default component must run on a free tier or self-hosted open-source software.
- **No high-volume spray-and-pray.** The system is explicitly designed for low volume, high personalization — tens of messages per week, not thousands.
- **Not a full CRM replacement.** Hooze CRM (the product) is separate from Hooze Outbound OS (the internal tool used to sell it). Outbound OS may eventually feed opportunities into Hooze CRM, but V1 keeps its own lightweight `opportunities` table.
- **No multi-user permissions system.** V1 is single-operator (Hooze). Roles/permissions are out of scope until there's a second operator.

## 4. Users

| User | Role |
|---|---|
| Hooze (Sadiq Shehu Musa) | Sole operator. Runs discovery, reviews/approves/edits every message, sends manually (V1), closes deals. |
| Future: VA / junior sales hire | Would use the review queue and outreach logging only — not in scope for V1 build but the schema should not block it. |

## 5. Core Workflow (End-to-End)

```
ICP definition
   → Discovery (find raw leads)
   → Clean + deduplicate
   → Enrich
   → Research (evidence-gathering, with sources)
   → Score (ICP, pain, buying signal, contactability, personalization)
   → Campaign match
   → Personalize (AI-generated message, grounded in research evidence only)
   → Human review queue (approve / edit / reject)
   → Outreach (manual send via email or WhatsApp, logged)
   → Response tracking + classification
   → Follow-up engine (scheduled, stops on reply/opt-out)
   → Opportunity pipeline (meeting → proposal → won/lost)
   → Analytics + feedback into ICP/offer/message optimization
```

A lead's state machine (full detail in doc 05):

```
DISCOVERED → CLEANED → RESEARCHED → QUALIFIED → PERSONALIZED
→ REVIEW → APPROVED → CONTACTED → REPLIED → (QUALIFIED | MEETING
→ PROPOSAL → WON/LOST) | DEAD
```

## 6. Feature List (V1 scope)

1. **Discovery intake** — manual or semi-automated import of raw leads from free sources (Google Maps, LinkedIn, websites, directories) into a staging area (Google Sheets), then into Supabase.
2. **Cleaning & deduplication** — canonical company name/domain/phone/email normalization; duplicate detection before a lead enters the pipeline.
3. **Research engine** — structured, source-linked evidence gathering per company (website, WhatsApp presence, listings, social activity, observed gaps). Every claim stored with its source URL.
4. **Scoring engine** — deterministic 0–100 score across ICP fit, pain signal, buying signal, contactability, and personalization potential, producing an A/B/C/Don't-Contact tier.
5. **Campaign management** — named campaigns (industry × location × pain × offer × CTA) that qualified leads are matched against.
6. **Personalization engine** — AI-generated message drafts that may only use facts present in the research evidence table; no invented claims.
7. **Human review queue** — dashboard showing lead, score, evidence, and draft message with Approve / Edit / Reject actions.
8. **Outreach logging** — every sent message recorded (channel, content, timestamp, campaign, follow-up number).
9. **Follow-up engine** — scheduled follow-up cadence (e.g. day 0 / 3 / 7 / 14) that stops automatically on reply, opt-out, or max attempts.
10. **Response classification** — incoming replies tagged (interested, question, not interested, later, price, meeting, wrong person, unsubscribe, unknown) and routed.
11. **Opportunity pipeline** — lightweight stage tracking from meeting through won/lost.
12. **Analytics** — funnel metrics (discovered → contacted → replied → positive → meeting → client) sliced by campaign, channel, source, and message variant.
13. **Error monitoring** — failed workflow runs and data-quality issues surfaced, not silently dropped.

## 7. Constraints

- **Cost:** ₦0 for software/infrastructure. Free tiers only (n8n Community Edition self-hosted, Supabase free tier, Google Sheets/APIs within quota, Gmail within Google's sending limits, existing free hosting).
- **Volume discipline:** the system must be architected assuming quotas exist (Gmail sending limits, Sheets API quotas, free-tier DB storage caps) — not unlimited free anything.
- **Human-in-the-loop for sending:** no message leaves the system without explicit approval in V1.
- **Evidence-only personalization:** the AI layer is never given an open-ended "write a personalized message" prompt; it receives structured, sourced facts and must ground every claim in them.
- **One operator:** workflows and dashboard must be usable by a single non-technical-hours-constrained person (Hooze is a final-year student running this alongside Hooze Enterprises).
- **Composable, not monolithic:** built as ~15 separable n8n workflows plus a Python processing layer, not one giant workflow — so any single piece can be tested, replaced, or debugged in isolation.

## 8. Success Metrics (V1)

Primary metric: **learning velocity**, not volume. The system succeeds if it produces enough qualified, evidence-based outreach to generate reliable conversion data — not if it sends the most messages.

| Metric | V1 target (first 90 days) |
|---|---|
| Leads discovered per week | 50–100 |
| Leads reaching QUALIFIED (score ≥ 65) | ≥ 30% of discovered |
| Personalized messages requiring no edit at review | tracked as a quality signal, no fixed target yet |
| Reply rate on sent outreach | tracked as baseline (industry cold outreach is typically low single digits to ~10–20% with high personalization — establish Hooze's own number) |
| Positive-reply → meeting conversion | tracked as baseline |
| Meetings → won client | tracked as baseline |
| Time from lead discovery to human-reviewable message | < 24 hours |
| System uptime / workflow failure rate | failures visible within the same day, not silently dropped |

Secondary success condition: the database schema, scoring model, and campaign structure from V1 should not need to be rebuilt when moving to V2 (auto-send, more channels, more sources) — only extended.

## 9. Explicit Design Principles (carried into every downstream doc)

1. **Interfaces before implementations.** Discovery, research, and enrichment are defined as required interfaces first; the exact scraping/data source is chosen after, and can be swapped without touching the rest of the system.
2. **Evidence over inference.** Every personalization claim traces to a stored fact with a source. No claim, no send.
3. **State machine discipline.** A lead's status is always one explicit value; nothing gets contacted twice through different channels because status wasn't checked.
4. **Free ≠ unlimited.** Every component assumes a quota or limit exists and designs around it (batching, low volume, human gating).
5. **Small, testable workflows.** ~15 n8n workflows with clear inputs/outputs/error paths rather than one large workflow.
6. **Human authority preserved.** Hooze is the final approver and sender in V1. Automation removes research and drafting labor, not decision authority.

## 10. Downstream Documents (to be built against this PRD)

02 ICP Specification · 03 Data Dictionary · 04 Database Schema · 05 Lead Lifecycle · 06 Scoring Engine · 07 Research Engine · 08 Personalization Spec · 09 Campaign Spec · 10 Outreach SOP · 11 Follow-up Spec · 12 Response Classification · 13 n8n Workflow Architecture · 14 Security Spec · 15 Analytics Spec.

Each must stay consistent with the constraints, non-goals, and design principles in this document. Any conflict gets resolved in favor of this PRD, or this PRD gets explicitly revised first.
