# 02 — ICP Specification

**Version:** 1.0 · **Depends on:** 01-system-prd.md

## 1. Purpose

Defines who the Hooze Outbound OS is allowed to contact. Every lead is scored against this document (see 06-scoring-engine.md). No lead skips ICP evaluation.

## 2. Primary ICP (Campaign 001 — locked first vertical)

**Industry:** Real estate agencies / property management firms
**Geography:** Abuja first, Lagos second (matches existing PDR proof asset)
**Company size:** Small–mid: 1–20 staff, actively listing properties
**Qualifying signal:** Business is customer-facing on WhatsApp for inquiries/inspections

### 2.1 Firmographic filters

| Field | Requirement |
|---|---|
| Industry | Real estate agency, property management, or real estate developer with active sales arm |
| Location | Abuja or Lagos metro (V1); other cities excluded until a campaign is defined for them |
| Online presence | Has a website OR active Instagram/Facebook business page with listings |
| Contact channel | WhatsApp number visible/inferable (button, "chat with us", number in bio) |
| Activity | Evidence of active listings within the last ~90 days (not a dormant page) |

### 2.2 Disqualifiers (auto-reject, score = 0, status = DEAD)

- No public contact channel of any kind (can't reach them without cold-calling, out of scope)
- Business is clearly defunct (broken site, no posts in 12+ months, disconnected number)
- Already a Hooze Enterprises client or in active conversation outside this system
- Individual/personal listing (not a business) — e.g. one person selling their own house
- Industries explicitly out of scope for the current campaign set (see 09-campaign-spec.md for the campaign list; a lead outside every active campaign's ICP does not enter the pipeline)

### 2.3 Decision-maker profile

| Attribute | Value |
|---|---|
| Title | Managing Director, Principal Partner, Head of Sales, or Owner |
| Reachability | Direct WhatsApp or email preferred over generic info@ inbox |
| Confidence tiers | HIGH (named person + direct contact), MEDIUM (named person, generic contact), LOW (business only, no named contact) |

LOW-confidence contacts are still qualified but scored down on **contactability** (see 06-scoring-engine.md).

## 3. Pain Signals (real estate vertical)

Presence of any of these increases pain score:

- WhatsApp is the primary inquiry channel but responses appear slow/manual (e.g. business hours only, inconsistent reply patterns visible in public reviews/comments)
- No visible automated qualification or booking flow (inquiries go straight to a human with no structure)
- High listing volume relative to visible team size (implies inquiry volume may outstrip manual handling capacity)
- Public complaints/reviews mentioning slow response, missed follow-up, or disorganized communication
- No CRM/booking tool evidence (no Calendly-style links, no visible ticketing)

## 4. Buying Signals

- Recently posted a hiring ad for "customer service," "sales agent," or "WhatsApp/inquiries handler" (proxy for volume pain, budget exists)
- Recently increased marketing activity (paid ads, boosted posts, new listings pushed frequently)
- Multiple branches/locations (proxy for scale and budget)
- Site or page recently redesigned/relaunched (proxy for active investment in growth)

## 5. Contactability Requirements

A lead must have at least one of:

- Direct WhatsApp number
- Direct email of a named decision-maker
- A generic business email/WhatsApp AND a named decision-maker findable via LinkedIn/site "About" page

Leads with none of the above do not proceed past CLEANED (see 05-lead-lifecycle.md).

## 6. Out-of-Scope for V1 (revisit later)

- Enterprise real estate firms (50+ staff) — different sales motion, longer cycle, not the first proof point
- Individual agents without a registered business
- Non-real-estate industries — held for future campaigns (restaurants, clinics for Clinical Clarity, etc.) once Campaign 001 has usable conversion data

## 7. Adding a New Vertical

To open a new campaign (e.g. restaurants for WhatsApp ordering, clinics for Clinical Clarity), this document gets a new numbered section (2.x) with its own firmographic filters, pain signals, and buying signals — the scoring model in 06 stays the same, only the inputs change. See 09-campaign-spec.md for how a new vertical becomes an active campaign.
