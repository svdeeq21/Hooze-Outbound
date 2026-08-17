# BUILD_LOG.md

This documents what was built, in what order, and — more importantly —
every place a judgment call had to be made because the spec was silent,
ambiguous, or (in a couple of cases) internally inconsistent. Read this
before changing scoring, schema, or the review/send flow; it explains *why*
things are shaped the way they are, not just what they do.

Everything below was actually run, not just written: the full schema was
applied to a live PostgreSQL instance, seeded, and queried; all 56 unit
tests pass (`python3 -m pytest tests/ -v`); all 15 n8n workflow JSON files
were validated for structural correctness (every connection points at a
real node).

---

## 1. Build order followed

Per `README.md` / `docs/13-n8n-architecture.md`:

1. Database (`database/migrations/`, `schema.sql`, `seed.sql`) — built and
   verified against a live Postgres instance.
2. Scoring engine (`python/scoring/engine.py`) — built early against seed
   data, per the README's explicit instruction, before research automation.
3. Enrichment layer (`python/enrichment/normalize.py`, `dedup.py`,
   `enrich.py`) — WF-02/03/04.
4. Research engine (`python/research/`) — interface, reference HTTP
   fetcher, AI extractor — WF-05.
5. Campaign matcher (`python/campaign/matcher.py`) — WF-07.
6. Personalization engine (`python/personalization/`) — generator +
   validator — WF-08.
7. Review/send actions (`python/review/actions.py`) — WF-09/WF-10.
8. Follow-up scheduler (`python/followup/scheduler.py`) — WF-11.
9. Response classifier (`python/classification/classifier.py`) — WF-12.
10. Opportunity manager (`python/opportunities/manager.py`) — WF-13.
11. Analytics (`python/analytics/reports.py`) — WF-14.
12. All 15 n8n workflow JSONs (`n8n/*.json`), generated from
    `n8n/generate_workflows.py`.
13. Review dashboard (`dashboard/index.html`) — WF-09/10/13 frontend.

`python/ai_client.py` (shared Gemini/Groq wrapper) was pulled out during
step 6 once it became clear three separate modules (research,
personalization, classification) needed the identical
call-with-fallback-and-backoff logic — better to have one implementation
than three slightly different ones.

---

## 2. Database: two fields added that weren't in the original schema draft

Reading `docs/10-outreach-sop.md` §3 closely (after the initial schema was
already drafted from `docs/04`) surfaced two requirements with no backing
column:

- **`outreach.draft_history`** — §3: "Edited text is what gets logged as
  `outreach.message` (original AI draft is not overwritten in logs — kept
  in a `draft_history` note field...)". The original schema had no such
  field. Added in `database/migrations/012_outreach_review_fields.sql`.
- **`outreach.rejection_reason`** — §3: "A rejection reason is logged...
  this reason feeds scoring/research quality improvements." Also missing.
  Same migration.

`schema.sql` was regenerated (not hand-patched) after adding this migration
so it stays a literal concatenation of `migrations/*.sql` — see the header
comment in that file. Re-ran the full schema + seed against a clean
Postgres instance afterward to confirm nothing broke.

## 3. `docs/06-scoring-engine.md` §6 worked examples aren't literally reachable

The worked examples show ICP scores of "23/25" and "18/25". Under the
literal point rule in §2.1 (four flat conditions worth 10/5/5/5 points),
every achievable total is one of {0, 5, 10, 15, 20, 25} — 23 and 18 are not
reachable. I implemented the rule *as written in §2.1* (see
`python/scoring/engine.py::_score_icp_fit`), not the example's numbers,
since the numbered rule is presumably the source of truth and the example
looks like an illustrative draft that wasn't updated to match. Documented
inline in `database/seed.sql` and in the engine's tests
(`tests/scoring/test_engine.py`) so this isn't mistaken for a bug later —
the seed fixture reproduces the worked example's *evidence*, and the
resulting score (80/100 → Tier A) is asserted directly rather than
hand-matched to the doc's illustrative "23/25".

## 4. `research.pain_signals` / `buying_signals`: derivation clarified

`docs/03-data-dictionary.md` lists the *Source* of `research.pain_signals`
and `research.buying_signals` as **"scoring"**, not "research engine" —
i.e. WF-05 (research) gathers raw evidence, and WF-06 (scoring) is what
matches that evidence against the known signal catalogue
(`docs/02-icp-spec.md` §3/§4) to produce the signal-key arrays that
`docs/06-scoring-engine.md` §2.2/§2.3 then counts.

This is a subtlety easy to miss reading `docs/07-research-engine.md` alone
(which reads as if research produces the signals). I implemented it per the
data dictionary: `python/scoring/signal_matcher.py` does simple, precise
keyword matching against `research_evidence.claim` text, is called from
inside `score_from_db()` before `score_company()` runs, and writes the
matched signals back onto the `research` row — so the dashboard/audit trail
shows *which* evidence produced *which* signal, not just the resulting
score.

## 5. Personalization validator: two heuristics needed a second pass

`python/personalization/validator.py` implements `docs/08-personalization-
spec.md` §6's five checks in code. Two of them needed correction after
writing tests against realistic (not toy) message text:

- **Number check.** `docs/08` §3 explicitly allows "general statements
  about Hooze Enterprises' offer, proof, and CTA (these are Hooze's own
  claims, not claims about the prospect)". The CTA itself often contains a
  number (Campaign 001's CTA: "a short 15-min demonstration"). The first
  version of the check flagged that "15" as an unsupported claim, which is
  wrong — it's Hooze's own offer detail, not an invented fact about the
  prospect. Fixed by excluding numbers present in `campaign.cta` from the
  "unsupported" set.
- **CTA match.** Exact/near-exact keyword overlap between the message and
  `campaign.cta` was too strict for natural paraphrasing ("a quick 15-min
  demo" vs. CTA text "a short (15-min) demonstration" — zero literal
  keyword overlap despite conveying the same ask). Added a small synonym
  expansion (demo/demonstration/walkthrough, call/chat/meeting/talk,
  short/quick/brief). This is still a heuristic, which is exactly why §6
  specifies these checks as *warnings* that route to review, never hard
  blocks — Hooze makes the final call either way.

Both were caught by `tests/personalization/test_validator.py` using message
text modeled on what the AI would plausibly draft, not synthetic edge
cases — worth remembering when extending this validator: test against
realistic paraphrasing, not just the literal spec wording.

## 6. Analytics: three metrics the current schema cannot compute correctly

Documented directly in `python/analytics/reports.py`'s module docstring,
repeated here because it matters for anyone tuning `docs/15-analytics-
spec.md` metrics later:

- **Time-to-review** (`docs/15` §3: `avg(REVIEW timestamp − RESEARCHED
  timestamp)`) — `companies.status` is a single current-state field with no
  history log, so there's no stored timestamp for *when* a company entered
  REVIEW or RESEARCHED specifically.
- **Edit rate** (`docs/15` §3: `EDITED approvals / total APPROVED`) — solved
  *partially* by `outreach.draft_history` (§2 above; a non-null
  `draft_history` means the row was edited before approval), but the
  analytics module doesn't compute this yet — it's a straightforward query
  once you know to check `draft_history IS NOT NULL`, left as a clear
  next step rather than guessed at.
- **Per-message-variant breakdown** (`docs/15` §5) — `outreach` has no
  `variant`/`variant_group` column tying two AI-generated alternatives for
  the *same* company back together as a single A/B test. Each variant is
  just a separate `outreach` row today.

None of these are silently approximated with invented numbers — the
funnel/rate metrics that ARE computable (`python/analytics/reports.py`)
return `null` for a zero denominator rather than fabricating `0%`, matching
the "no invented facts" discipline that governs the research/personalization
layers too.

`compute_funnel_metrics()` also documents its own core assumption plainly:
since `companies.status` only ever moves forward (`docs/05-lead-lifecycle.md`
§1), "reached stage X" is computed as "current status is X or later in the
funnel" — correct for companies still progressing, but a company later
marked DEAD/LOST is excluded from "reached" counts for any stage beyond
its terminal status, which under-counts historical peak-stage reach. A real
status-history table would remove this limitation; not added in V1 to avoid
a schema change with no doc backing it.

## 7. n8n workflows: how Python gets invoked

`docs/13-n8n-architecture.md` says n8n orchestrates and Python does the
processing, but doesn't specify the *mechanism* n8n uses to call Python.
Went with **Execute Command nodes** (`python3 -m python.<module> <args>`,
or a one-line `python3 -c "..."` for functions with no CLI entry point)
rather than standing up a separate FastAPI/Flask service, because:

- It's the simplest thing that satisfies "n8n orchestrates, Python
  processes" with zero extra infrastructure (matches the ₦0-infra
  constraint in `docs/01-system-prd.md`).
- Every module already has a working `if __name__ == "__main__":` CLI
  entry point (built and tested that way from the start), so this wasn't
  extra work — it's just wiring what already exists into a node.

Every workflow JSON's Execute Command nodes assume the repo lives at
`/opt/hooze-outbound` on the n8n host and that
`pip install -r python/requirements.txt --break-system-packages` has been
run there — see `README.md` "n8n setup" for the actual steps. Adjust the
path in each Execute Command node after import if your deployment differs.

`n8n/generate_workflows.py` is committed alongside its 15 JSON outputs —
regenerate with `python3 n8n/generate_workflows.py` after changing it,
rather than hand-editing the JSON files (they'll be overwritten).

Each workflow JSON's first node is a Sticky Note with the full trigger /
input / processing / output / DB-ops / error-path contract from
`docs/13-n8n-architecture.md` §2, satisfying that doc's own §4 requirement
("every workflow JSON file... should include a header comment").

## 8. Dashboard: no Supabase credential in the browser, by design

`docs/14-security-spec.md` §2 mentions an anon/public Supabase key as an
option "if a separate web UI is built," but `migration
011_row_level_security.sql` deliberately enables RLS with **zero** anon
policies (default-deny) — see that migration's own comment for the
reasoning. Rather than add anon SELECT policies (a real schema/security
decision that deserves its own review, not a side-effect of building the
dashboard), `dashboard/index.html` holds no Supabase credential of any
kind. Every read and write goes through the n8n webhooks
(WF-09/WF-10/WF-13), which already run with the service-role credential —
consistent with `docs/14-security-spec.md` §7: "Python scripts run with the
same service-role credential as n8n, no separate exposed API surface in
V1." `python/review/actions.py` gained three read-only helpers
(`list_review_queue`, `list_send_queue`, `list_replied_queue`) to support
this.

The dashboard is a static single HTML file with no build step — open it
directly or serve it from any static host. It needs the three webhook URLs
filled in at the top of its `<script>` block after you import and activate
the corresponding n8n workflows (see the file's own header comment).
`docs/14-security-spec.md` §3 requires webhook auth (shared secret); the
dashboard sends an `X-Hooze-Secret` header on every request, but *enforcing*
it is an n8n-side node you add after import (an IF/Function node comparing
the header to an environment variable) — not scaffolded automatically since
n8n credential/env setup is environment-specific.

## 9. What was NOT built / explicitly deferred

- **Live Supabase/AI provider testing.** Every DB-touching function was
  validated against a real local Postgres instance (schema + seed data);
  every pure-logic function has unit tests. The Supabase-client and
  AI-provider *call* paths (`get_client()`, `call_ai()`) are exercised by
  code review and by the fact the same interfaces are used consistently
  everywhere, but not by an end-to-end run against a live Supabase project
  or live Gemini/Groq credentials — those need real credentials this
  environment doesn't have. `python/config.py`'s `ConfigError` fails loudly
  and immediately if a required env var is missing, rather than failing
  silently deep in a workflow.
- **WF-01's Google Sheets `import_errors` tab.** The n8n workflow JSON
  wires the node; the actual Google Sheet (with a "Staging" and
  "import_errors" tab) needs to be created by whoever deploys this, with
  its ID substituted into the workflow.
- **Webhook shared-secret enforcement inside n8n** (see §8) — the dashboard
  sends the header, the n8n-side check isn't pre-built into the generated
  workflow JSON since it depends on how you store the secret in your n8n
  instance (credential vs. environment variable).
- **Analytics gaps** — time-to-review, edit rate, variant breakdown. See §6.
- Everything already listed as explicitly out of scope in `README.md`
  ("What's intentionally not built yet"): auto-send, multi-operator roles,
  score decay, AI-assisted scoring, Campaigns 002/003.

## 10. Verification performed (initial build)

- `database/schema.sql` and `database/seed.sql` applied to a fresh local
  PostgreSQL 16 instance with zero errors; spot-checked the resulting rows.
- `python3 -m pytest tests/ -v` — 56 tests, all passing, covering: scoring
  engine (including the exact worked-example score), signal matching,
  normalization/dedup, research evidence/provenance rules, personalization
  validation, response classification hard rules, follow-up cadence math,
  campaign matching, and analytics funnel math.
- All 15 `n8n/*.json` files parsed as valid JSON and structurally checked
  (every connection references a real node by name, no dangling
  references).
- `dashboard/index.html`'s embedded JavaScript checked with `node --check`
  for syntax errors; HTML tag balance checked.

## 11. Railway deployment: Python as its own service, not Execute Command

After the initial build, the person deploying this already had n8n running
on Railway. Railway services are isolated containers — there's no "same
machine" for an Execute Command node to shell into, so the original
Execute Command approach (§7 above) doesn't work there.

Added:
- `python/api.py` — a thin FastAPI wrapper. Every route is a direct
  pass-through to the exact same function already built and tested (e.g.
  `POST /wf06/score` just calls `python.scoring.engine.score_from_db()`) —
  no new business logic, only an HTTP shape around logic that already
  existed. Verified locally: `/health` responds correctly, calling an
  endpoint with no Supabase credentials configured returns a clean 500
  with `ConfigError`'s message (not a crash), and the `X-Internal-Secret`
  header check correctly returns 401 when missing/wrong and passes through
  to the real handler when correct.
- `Procfile` — `web: uvicorn python.api:app --host 0.0.0.0 --port $PORT`,
  which Railway's Nixpacks builder auto-detects for a Python service with
  no further configuration needed in the common case.
- `n8n/generate_workflows.py`'s `execute_command()` helper was replaced
  with `http_request()`, and all 13 workflows that call Python (everything
  except WF-01 and WF-15, which only ever touched Supabase/Google Sheets
  directly) were regenerated to call `$env.PYTHON_API_URL` instead of
  shelling out. WF-07's builder also dropped a Code node that used to
  parse Python's stdout as JSON — no longer needed, since an HTTP response
  is already structured JSON.
- `RAILWAY_DEPLOYMENT.md` — step-by-step for this specific setup: add
  `python-api` as a second Railway service in the same project, private-
  networked only (never given a public domain), reachable from n8n at
  `python-api.railway.internal` for free. This is arguably a security
  improvement over the original single-VPS design: the Python layer now
  has zero public exposure by construction, rather than relying on it just
  not being firewalled open on a shared machine.

`DEPLOYMENT.md` (the original single-VPS guide) is unchanged and still
valid for anyone NOT using Railway — both are kept since they solve for
different starting points, not because one superseded the other.

## 12. Verification performed (Railway addition)

- Ran `python/api.py` locally with `uvicorn`, confirmed:
  - `GET /health` → `{"status":"ok"}` with no credentials needed at all.
  - `POST /wf06/score` with no `SUPABASE_URL` set → clean 500 with the
    exact `ConfigError` message, not a stack trace or hang.
  - With `PYTHON_API_SECRET` set: request with no header → 401; request
    with wrong header value → 401; request with correct header → passes
    auth and proceeds to the real handler (which then fails at the same
    `ConfigError` as above, since Supabase creds still weren't set in that
    test — confirming the auth check and the business logic are properly
    separated, not accidentally short-circuiting each other).
- All 56 existing unit tests still pass after adding `python/api.py` — it
  only wraps existing functions, so this was a regression check, not new
  coverage.
- All 15 `n8n/*.json` files re-validated after regeneration: valid JSON,
  every connection resolves to a real node by name, zero `executeCommand`
  nodes remain anywhere in the 13 Python-calling workflows, and every one
  of those 13 has at least one `httpRequest` node referencing
  `PYTHON_API_URL`.
