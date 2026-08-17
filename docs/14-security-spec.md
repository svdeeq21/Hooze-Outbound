# 14 — Security Specification

**Version:** 1.0 · **Depends on:** 04-database-schema.md

## 1. Credentials

| Credential | Storage | Access |
|---|---|---|
| Supabase service role key | n8n credential store (encrypted), never in workflow JSON exported to git | n8n workflows only |
| Supabase anon/public key | Dashboard frontend (if a separate web UI is built) | Dashboard only, scoped by RLS |
| Google Sheets/Gmail OAuth | n8n credential store | WF-01, WF-15 notifications |
| WhatsApp/Evolution API credentials (if outreach automation extends here later) | n8n credential store, per-instance bearer auth (consistent with existing PDR/Hooze CRM pattern) | Outreach workflows only, not exposed to dashboard |
| AI provider keys (Gemini/Groq, matching existing Hooze stack fallback pattern) | n8n credential store | WF-05, WF-08, WF-12 |

Rule: no credential ever appears in a committed n8n workflow JSON, Python file, or doc. Workflow JSONs exported to the `n8n/` repo folder must have credentials stripped/referenced by name only.

## 2. Supabase Row Level Security (RLS)

- RLS enabled on every table (04-database-schema.md §1).
- V1 is single-operator, but RLS is still enforced using a service-role key server-side (n8n) and a restricted anon key if a dashboard is public-facing.
- Policy: only the service role (used exclusively by n8n backend calls) can write; a future dashboard user role would get read + limited write (approve/edit/reject only) scoped to `outreach` and read-only elsewhere — not implemented until a second operator exists, but the schema doesn't block it (per 01-system-prd.md non-goals).

## 3. Webhook authentication

- Inbound webhooks (WF-12 response processing, WF-01 if triggered by Sheet webhook) require a shared-secret header or signature check, matching the per-instance bearer auth pattern already used in the Evolution API integration for Hooze CRM/PDR.
- No webhook accepts unauthenticated writes to `companies`, `outreach`, or `responses`.

## 4. Rate limiting

- Research engine (WF-05) enforces a per-company fetch cap (07-research-engine.md §7).
- AI calls (WF-05, WF-08, WF-12) respect the existing Gemini-primary/Groq-fallback pattern with backoff, consistent with the rest of the Hooze stack.
- Gmail sending, if used for outreach, stays well under Google's sending limits — enforced by the human-approval gate (10-outreach-sop.md) keeping volume low by design, not by a technical throttle alone.

## 5. Audit logging

- `outreach.approved_by` + `approved_at` record who approved every send (always "hooze" in V1, but the field exists for future multi-operator use).
- `responses.classification` decisions are logged with raw text preserved, enabling classifier-accuracy audits (12-response-classification.md §5).
- Score overrides (06-scoring-engine.md, if Hooze manually overrides a score) must be logged with a reason — not a silent edit.
- WF-15 error log retains all workflow failures for at least 90 days.

## 6. Data retention & PII handling

- `companies`, `contacts`: retained indefinitely while the lead is active or in an opportunity pipeline; DEAD leads retained for dedup purposes (prevents re-scraping/re-contacting) unless an UNSUBSCRIBE/removal request is received.
- On an UNSUBSCRIBE classification (12-response-classification.md §3), the company's contact fields (phone/email/whatsapp on `companies` and `contacts`) should be scrubbed to a minimal "do not contact" record rather than fully deleted, so future imports can still be checked against the do-not-contact list without retaining unnecessary personal data.
- No sensitive personal data beyond standard B2B contact info (name, title, business phone/email) is collected — no personal/home data, no data about individuals unrelated to their business role.
- Research evidence (`research_evidence`) only stores publicly observable business facts (site content, public listings), never scraped private/authenticated data.

## 7. Access boundaries

- Python scripts (`python/`) run with the same service-role credential as n8n, no separate exposed API surface in V1.
- No component of this system is publicly internet-facing except: the inbound response webhook (§3, authenticated) and, if built, the Hooze-only dashboard (auth required, single-user login).
