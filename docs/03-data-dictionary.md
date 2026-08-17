# 03 — Lead Data Dictionary

**Version:** 1.0 · **Depends on:** 01, 02 · **Feeds:** 04-database-schema.md

Defines every field used across the pipeline, independent of which table it lives in (table mapping is in doc 04).

## companies

| Field | Type | Required | Description | Source | Validation |
|---|---|---|---|---|---|
| id | uuid | yes | Primary key | system | generated |
| name | text | yes | Business display name as found | discovery | non-empty |
| normalized_name | text | yes | Lowercased, punctuation-stripped name used for dedup | system | derived |
| domain | text | no | Root domain, no protocol/www | discovery | valid domain format |
| industry | text | yes | Maps to an ICP vertical (02-icp-spec.md §2.x) | discovery/manual | enum-like, matches active campaign industries |
| location | text | yes | City/metro | discovery | matches active campaign geography |
| phone | text | no | Primary phone, E.164 where possible | discovery | numeric + country code |
| phone_normalized | text | no | Digits-only version for dedup | system | derived |
| email | text | no | Primary business email | discovery | valid email format |
| email_normalized | text | no | Lowercased email for dedup | system | derived |
| website | text | no | Full URL | discovery | valid URL |
| linkedin | text | no | Company LinkedIn URL | discovery | valid URL |
| instagram | text | no | Handle or URL | discovery | valid URL/handle |
| youtube | text | no | Channel URL | discovery | valid URL |
| whatsapp | text | no | WhatsApp number, E.164 | discovery/research | numeric + country code |
| source | text | yes | Which discovery channel produced this lead | discovery | enum: google_maps, linkedin, website, youtube, instagram, directory, referral, manual |
| source_url | text | no | Direct link to where the lead was found | discovery | valid URL |
| status | text | yes | Lead lifecycle state | system | enum, see 05-lead-lifecycle.md |
| created_at | timestamp | yes | | system | auto |
| updated_at | timestamp | yes | | system | auto |

## contacts

| Field | Type | Required | Description | Source | Validation |
|---|---|---|---|---|---|
| id | uuid | yes | Primary key | system | generated |
| company_id | uuid | yes | FK → companies.id | system | must exist |
| name | text | no | Full name of contact | discovery/research | — |
| job_title | text | no | e.g. Managing Director | discovery/research | — |
| email | text | no | Direct email if found | research | valid email format |
| phone | text | no | Direct phone/WhatsApp if found | research | numeric + country code |
| linkedin | text | no | Personal LinkedIn URL | research | valid URL |
| contact_source | text | no | Where this contact info was found | research | free text + source_url pattern |
| confidence | text | yes | HIGH / MEDIUM / LOW per 02-icp-spec.md §2.3 | scoring | enum |
| created_at | timestamp | yes | | system | auto |

## research

| Field | Type | Required | Description | Source | Validation |
|---|---|---|---|---|---|
| id | uuid | yes | Primary key | system | generated |
| company_id | uuid | yes | FK → companies.id | system | must exist |
| website_summary | text | no | Short factual summary of what the site shows | research engine | must not contain claims without a source in research_evidence |
| services | text[] | no | List of services offered, as observed | research engine | derived from source page |
| target_market | text | no | Observed target market | research engine | derived from source page |
| whatsapp_present | boolean | no | Whether WhatsApp contact is visibly offered | research engine | derived |
| booking_process | text | no | Observed inspection/booking process, if any | research engine | derived |
| lead_capture_process | text | no | Observed inquiry capture method | research engine | derived |
| observed_problem | text | no | Hypothesis, must map to ≥1 row in research_evidence | research engine | required if used in personalization |
| pain_signals | text[] | no | Matched pain signals from 02-icp-spec.md §3 | scoring | derived |
| buying_signals | text[] | no | Matched buying signals from 02-icp-spec.md §4 | scoring | derived |
| proof | text | no | Any public proof of scale (listing count, branch count, etc.) | research engine | derived |
| research_score | int | no | 0–100 internal confidence in research completeness | research engine | 0–100 |
| researched_at | timestamp | no | | system | auto |

## research_evidence

*(Added beyond the original outline — required by the evidence/provenance principle in 01-system-prd.md §9.2 and detailed in 07-research-engine.md.)*

| Field | Type | Required | Description |
|---|---|---|---|
| id | uuid | yes | Primary key |
| company_id | uuid | yes | FK → companies.id |
| claim | text | yes | The specific factual observation |
| source_url | text | yes | Where the claim was observed |
| captured_at | timestamp | yes | When it was captured |
| confidence | text | yes | HIGH / MEDIUM / LOW |

## lead_scores

| Field | Type | Required | Description | Source |
|---|---|---|---|---|
| id | uuid | yes | Primary key | system |
| company_id | uuid | yes | FK → companies.id | system |
| icp_score | int | yes | 0–25 | scoring engine |
| pain_score | int | yes | 0–25 | scoring engine |
| buying_signal_score | int | yes | 0–20 | scoring engine |
| contactability_score | int | yes | 0–15 | scoring engine |
| personalization_score | int | yes | 0–15 | scoring engine |
| total_score | int | yes | 0–100, sum of above | scoring engine |
| priority | text | yes | A / B / C / DONT_CONTACT | scoring engine |
| reason | text | yes | Human-readable score breakdown | scoring engine |
| scored_at | timestamp | yes | | system |

## campaigns

| Field | Type | Required | Description |
|---|---|---|---|
| id | uuid | yes | Primary key |
| name | text | yes | e.g. "CAMPAIGN 001 — Abuja Real Estate" |
| industry | text | yes | Matches 02-icp-spec.md vertical |
| target_location | text | yes | |
| offer | text | yes | What's being offered |
| pain | text | yes | The pain this campaign targets |
| proof | text | no | Proof asset referenced (e.g. PDR case study) |
| cta | text | yes | Call to action used in messages |
| status | text | yes | DRAFT / ACTIVE / PAUSED / RETIRED |
| created_at | timestamp | yes | |

## outreach

| Field | Type | Required | Description |
|---|---|---|---|
| id | uuid | yes | Primary key |
| company_id | uuid | yes | FK → companies.id |
| contact_id | uuid | no | FK → contacts.id |
| campaign_id | uuid | yes | FK → campaigns.id |
| channel | text | yes | EMAIL / WHATSAPP |
| message | text | yes | Final approved/sent content |
| status | text | yes | See 10-outreach-sop.md / 11-follow-up.md state list |
| sent_at | timestamp | no | |
| follow_up_number | int | yes | 0 = initial message, 1+ = follow-up count |
| last_contact_at | timestamp | no | |
| next_follow_up_at | timestamp | no | |
| approved_by | text | no | Should always be "hooze" in V1 |
| approved_at | timestamp | no | |

## responses

| Field | Type | Required | Description |
|---|---|---|---|
| id | uuid | yes | Primary key |
| outreach_id | uuid | yes | FK → outreach.id |
| response_text | text | yes | Raw reply content |
| classification | text | yes | See 12-response-classification.md |
| sentiment | text | no | POSITIVE / NEUTRAL / NEGATIVE |
| intent | text | no | Free text summary |
| created_at | timestamp | yes | |

## opportunities

| Field | Type | Required | Description |
|---|---|---|---|
| id | uuid | yes | Primary key |
| company_id | uuid | yes | FK → companies.id |
| stage | text | yes | MEETING / PROPOSAL / WON / LOST |
| estimated_value | numeric | no | In NGN |
| notes | text | no | |
| next_action | text | no | |
| created_at | timestamp | yes | |
| updated_at | timestamp | yes | |
