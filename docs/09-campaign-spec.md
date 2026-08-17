# 09 — Campaign Specification

**Version:** 1.0 · **Depends on:** 02, 08

## 1. Purpose

Defines what a campaign is, how a qualified lead gets matched to one, and locks Campaign 001 as the first active campaign.

## 2. Campaign object

Every campaign (see `campaigns` table, 04-database-schema.md) defines:

```
ICP (reference to 02-icp-spec.md section)
pain
offer
proof
hook / opening-observation pattern
CTA
channels (email, whatsapp, or both)
follow-up strategy (reference to 11-follow-up.md cadence, can override default)
status: DRAFT / ACTIVE / PAUSED / RETIRED
```

## 3. Campaign 001 (locked, first active campaign)

```
Name:            CAMPAIGN 001 — Abuja Real Estate WhatsApp Automation
Industry:        Real estate agencies (02-icp-spec.md §2)
Location:        Abuja
Pain targeted:   Manual/slow WhatsApp inquiry handling, no automated
                 qualification or inspection booking
Offer:           Hooze CRM — WhatsApp AI sales + lead qualification +
                 inspection booking automation
Proof:           Praise Dynasty Realty (PDR) deployment — WhatsApp
                 AI sales platform live since Sprint 6, conversation
                 state machine COLD→...→CALL_INVITE
Pricing referenced in proposal stage (not in cold message):
                 Starter ₦350,000 setup + ₦75,000/month
                 Growth ₦500,000 setup + ₦150,000/month
CTA:             Offer a short (15-min) demonstration
Channels:        WhatsApp primary, email fallback if no WhatsApp found
Follow-up:       Default cadence (11-follow-up.md): Day 0, 3, 7, 14
Status:          ACTIVE
```

## 4. Campaign matching logic

A `QUALIFIED` company (05-lead-lifecycle.md) is matched to the first `ACTIVE` campaign whose:

1. `industry` matches `companies.industry`
2. `target_location` matches `companies.location`

If more than one active campaign matches, the one with the higher average historical reply rate (from 15-analytics-spec.md, once data exists) is chosen; before any data exists, the most recently activated campaign wins. If no active campaign matches, the lead stays QUALIFIED but does not enter PERSONALIZED — it's visible in the dashboard as "qualified, no active campaign."

## 5. Adding a new campaign

1. Add or confirm the relevant ICP section in 02-icp-spec.md
2. Insert a row in `campaigns` with status DRAFT
3. Write `prompts/personalizer.md` overrides if the pain/hook pattern differs meaningfully from Campaign 001
4. Test against 3–5 sample leads manually before setting status ACTIVE
5. Set status ACTIVE

## 6. Planned next campaigns (not yet built)

- **CAMPAIGN 002** — Lagos Real Estate (same offer, new geography, reuses PDR proof)
- **CAMPAIGN 003** — Nigerian clinics, Clinical Clarity offer (different product, new pain/offer/proof — will need its own ICP section 02-icp-spec.md §2.3 before activation)

These stay DRAFT until Campaign 001 has produced enough data to validate the pipeline end-to-end (per 01-system-prd.md success metrics).
