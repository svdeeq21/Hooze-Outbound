#!/usr/bin/env python3
"""
n8n/generate_workflows.py

Generates all 15 workflow JSON files under n8n/ from the contracts in
docs/13-n8n-architecture.md. This script is committed alongside its output
so a future change to a workflow's shape can be made here (one place) and
regenerated, rather than hand-editing 15 divergent JSON files.

Every generated workflow follows the same skeleton:
  1. A Sticky Note node (n8n-nodes-base.stickyNote) at the top documenting
     trigger / input / output / DB ops / error path — satisfying docs/13
     §4's "every workflow JSON file... should include a header comment."
  2. A trigger node (Schedule / Webhook / Manual, per the workflow's
     contract).
  3. A Supabase node (or HTTP Request against PostgREST) fetching the rows
     that need processing.
  4. A Split In Batches loop over those rows.
  5. An Execute Command node invoking the relevant `python -m python.X.Y`
     entry point (see each module's `if __name__ == "__main__"` block).
  6. An IF node checking the command's exit code, routing failures to an
     Error Log node (HTTP POST to Supabase `error_log`) rather than
     silently stopping the whole run — matching every python/ module's own
     internal error_log writes, this is the OUTER safety net for failures
     that happen before Python even gets a chance to log them itself (e.g.
     Python isn't installed, wrong path, OOM).

Import these into n8n via Workflows -> Import from File. Two things to set
per-environment after import (see README.md "n8n setup"):
  - The Supabase credential on every Supabase-typed node
  - The `PYTHONPATH`/working-directory environment for Execute Command nodes
    (must be the repo root so `python -m python.scoring.engine` resolves)
"""
from __future__ import annotations

import json
import os

OUT_DIR = os.path.join(os.path.dirname(__file__))


def sticky(text: str, width: int = 420, height: int = 380) -> dict:
    return {
        "parameters": {"content": text, "height": height, "width": width},
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [-680, -120],
        "id": "sticky-note-header",
        "name": "Workflow Contract (docs/13-n8n-architecture.md)",
    }


def schedule_trigger(name: str, cron_expr: str, node_id: str, position=(-420, 80)) -> dict:
    return {
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": cron_expr}]}
        },
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": list(position),
        "id": node_id,
        "name": name,
    }


def manual_trigger(node_id: str, position=(-420, 80)) -> dict:
    return {
        "parameters": {},
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": list(position),
        "id": node_id,
        "name": "Manual / on-demand run",
    }


def webhook_trigger(name: str, path: str, node_id: str, position=(-420, 80)) -> dict:
    return {
        "parameters": {
            "httpMethod": "POST",
            "path": path,
            "responseMode": "lastNode",
            "options": {},
        },
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": list(position),
        "id": node_id,
        "name": name,
        "webhookId": path,
    }


def supabase_get_many(name: str, table: str, filter_desc: str, node_id: str, position, filters=None) -> dict:
    """A Supabase node in 'getAll' mode. `filters` is a human-readable
    description embedded as a note since the exact filter UI fields vary by
    n8n Supabase node version — operators should confirm/adjust filter
    fields in the n8n editor against this note on first import."""
    return {
        "parameters": {
            "resource": "row",
            "operation": "getAll",
            "tableId": table,
            "returnAll": True,
            "filterType": "manual",
            "matchType": "allFilters",
            "notesInFlow": filter_desc,
        },
        "type": "n8n-nodes-base.supabase",
        "typeVersion": 1,
        "position": list(position),
        "id": node_id,
        "name": name,
        "credentials": {"supabaseApi": {"id": "SUPABASE_CREDENTIAL_ID", "name": "Hooze Supabase"}},
    }


def split_in_batches(node_id: str, position, batch_size: int = 1) -> dict:
    return {
        "parameters": {"batchSize": batch_size, "options": {}},
        "type": "n8n-nodes-base.splitInBatches",
        "typeVersion": 3,
        "position": list(position),
        "id": node_id,
        "name": "Loop Over Rows",
    }


def http_request(name: str, method: str, path: str, node_id: str, position, body_expr: str | None = None) -> dict:
    """POSTs to the Python API service (python/api.py), reached over
    Railway's PRIVATE network — see RAILWAY_DEPLOYMENT.md. The base URL is
    an n8n environment variable (PYTHON_API_URL, set to something like
    `http://python-api.railway.internal:8000`) so this JSON never hard-codes
    a specific Railway project's internal hostname.

    `body_expr` is a raw n8n expression string for the JSON body (already
    using {{ }} syntax) — passed as-is since each endpoint's body shape
    differs by workflow.
    """
    params: dict = {
        "method": method,
        "url": "={{ $env.PYTHON_API_URL }}" + path,
        "sendHeaders": True,
        "headerParameters": {
            "parameters": [
                {"name": "X-Internal-Secret", "value": "={{ $env.PYTHON_API_SECRET }}"},
                {"name": "Content-Type", "value": "application/json"},
            ]
        },
        "options": {"timeout": 60000},
    }
    if body_expr is not None:
        params["sendBody"] = True
        params["specifyBody"] = "json"
        params["jsonBody"] = body_expr
    return {
        "parameters": params,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": list(position),
        "id": node_id,
        "name": name,
        "continueOnFail": True,
        "alwaysOutputData": True,
    }


def if_node(name: str, node_id: str, position, condition_note: str) -> dict:
    return {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.exitCode }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "notEquals"},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
            "notesInFlow": condition_note,
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": list(position),
        "id": node_id,
        "name": name,
    }


def supabase_insert(name: str, table: str, node_id: str, position, fields_desc: str) -> dict:
    return {
        "parameters": {
            "resource": "row",
            "operation": "create",
            "tableId": table,
            "notesInFlow": fields_desc,
        },
        "type": "n8n-nodes-base.supabase",
        "typeVersion": 1,
        "position": list(position),
        "id": node_id,
        "name": name,
        "credentials": {"supabaseApi": {"id": "SUPABASE_CREDENTIAL_ID", "name": "Hooze Supabase"}},
    }


def notify_node(name: str, node_id: str, position, message_note: str) -> dict:
    """Telegram notification, matching the existing Hooze n8n stack pattern
    (docs/13-n8n-architecture.md WF-15: 'Telegram/Gmail, consistent with
    the existing n8n content pipeline pattern')."""
    return {
        "parameters": {
            "chatId": "={{ $env.HOOZE_TELEGRAM_CHAT_ID }}",
            "text": message_note,
            "additionalFields": {},
        },
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": list(position),
        "id": node_id,
        "name": name,
        "credentials": {"telegramApi": {"id": "TELEGRAM_CREDENTIAL_ID", "name": "Hooze Telegram Bot"}},
    }


def connect(nodes_by_name: dict, *pairs) -> dict:
    """pairs: list of (from_name, to_name) or (from_name, to_name, output_index)."""
    connections: dict = {}
    for pair in pairs:
        if len(pair) == 2:
            src, dst = pair
            out_idx = 0
        else:
            src, dst, out_idx = pair
        connections.setdefault(src, {"main": []})
        while len(connections[src]["main"]) <= out_idx:
            connections[src]["main"].append([])
        connections[src]["main"][out_idx].append({"node": dst, "type": "main", "index": 0})
    return connections


def workflow(name: str, nodes: list, connections: dict) -> dict:
    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "meta": {"templateCredsSetupCompleted": False},
    }


def write(filename: str, wf: dict) -> None:
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w") as f:
        json.dump(wf, f, indent=2)
    print(f"wrote {filename}")


CONTRACT = """{title}

TRIGGER: {trigger}
INPUT: {input}
PROCESSING: {processing}
OUTPUT: {output}
DB OPS: {db_ops}
ERROR PATH: {error_path}

Setup: point every Supabase node's credential at your project, and set
Execute Command nodes' working directory to the repo root (needs
`pip install -r python/requirements.txt` done first, and SUPABASE_URL /
SUPABASE_SERVICE_ROLE_KEY / GEMINI_API_KEY / GROQ_API_KEY set as
environment variables n8n can see)."""


# ===========================================================================
# WF-01 — Lead Import
# ===========================================================================
def build_wf01():
    sticky_text = CONTRACT.format(
        title="WF-01 — LEAD IMPORT",
        trigger="Manual run / scheduled (daily) — reads a Google Sheets staging tab",
        input="Raw rows from Google Sheets staging tab (name, industry, location, phone/whatsapp/email/website/socials, source)",
        processing="Maps sheet columns to the companies schema shape 1:1 — no cleaning/validation here, that's WF-02's job",
        output="New companies rows, status=DISCOVERED",
        db_ops="Insert into companies",
        error_path="Malformed rows (missing name) logged to an 'import_errors' tab in the same sheet, not silently dropped; workflow continues with valid rows",
    )
    nodes = [
        sticky(sticky_text),
        schedule_trigger("Daily 8am staging check", "0 8 * * *", "trigger"),
        {
            "parameters": {
                "operation": "read",
                "documentId": {"__rl": True, "value": "GOOGLE_SHEET_ID", "mode": "id"},
                "sheetName": {"__rl": True, "value": "Staging", "mode": "name"},
                "options": {},
            },
            "type": "n8n-nodes-base.googleSheets",
            "typeVersion": 4.5,
            "position": [-160, 80],
            "id": "read_sheet",
            "name": "Read Staging Sheet",
            "credentials": {"googleSheetsOAuth2Api": {"id": "GOOGLE_CREDENTIAL_ID", "name": "Hooze Google"}},
        },
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "conditions": [
                        {"leftValue": "={{ $json.name }}", "rightValue": "", "operator": {"type": "string", "operation": "notEquals"}}
                    ],
                    "combinator": "and",
                },
                "options": {},
                "notesInFlow": "Valid rows need at minimum a non-empty 'name' column; everything else is optional at import time",
            },
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [80, 80],
            "id": "has_name",
            "name": "Has name?",
        },
        supabase_insert("Insert companies row", "companies", "insert_company", (320, 0),
                         "Maps: name, industry, location, phone, email, website, linkedin, instagram, youtube, whatsapp, source, source_url. status defaults to DISCOVERED per the table default."),
        {
            "parameters": {
                "operation": "append",
                "documentId": {"__rl": True, "value": "GOOGLE_SHEET_ID", "mode": "id"},
                "sheetName": {"__rl": True, "value": "import_errors", "mode": "name"},
                "columns": {"mappingMode": "autoMapInputData"},
                "options": {},
            },
            "type": "n8n-nodes-base.googleSheets",
            "typeVersion": 4.5,
            "position": [320, 200],
            "id": "log_import_error",
            "name": "Log to import_errors tab",
            "credentials": {"googleSheetsOAuth2Api": {"id": "GOOGLE_CREDENTIAL_ID", "name": "Hooze Google"}},
        },
    ]
    conns = connect(
        {},
        ("Daily 8am staging check", "Read Staging Sheet"),
        ("Read Staging Sheet", "Has name?"),
        ("Has name?", "Insert companies row", 0),
        ("Has name?", "Log to import_errors tab", 1),
    )
    return workflow("WF-01 - Lead Import", nodes, conns)


# ===========================================================================
# WF-02 — Lead Cleaning
# ===========================================================================
def build_wf02():
    sticky_text = CONTRACT.format(
        title="WF-02 — LEAD CLEANING",
        trigger="New row with status=DISCOVERED (polled on a schedule; n8n has no native Postgres row-insert trigger without Supabase Realtime/webhooks configured separately)",
        input="companies row",
        processing="Calls python/enrichment/normalize.py (python -m python.enrichment.normalize <company_id>) — computes normalized_name, phone_normalized, email_normalized",
        output="Updated row, status=CLEANED (pending dedup in WF-03)",
        db_ops="Update companies",
        error_path="Rows failing normalization flagged (module writes to error_log itself), status stays DISCOVERED, surfaced in WF-15",
    )
    nodes = [
        sticky(sticky_text),
        schedule_trigger("Every 15 min", "*/15 * * * *", "trigger"),
        supabase_get_many("Get DISCOVERED companies", "companies", "Filter: status = 'DISCOVERED'", "get_discovered", (-160, 80)),
        split_in_batches("Loop Over Rows", (80, 80)),
        http_request(
            "Run normalize.py",
            "POST",
            "/wf02/clean",
            "run_normalize",
            (320, 0),
            body_expr='={\n  "company_id": "{{ $json.id }}"\n}',
        ),
    ]
    conns = connect(
        {},
        ("Every 15 min", "Get DISCOVERED companies"),
        ("Get DISCOVERED companies", "Loop Over Rows"),
        ("Loop Over Rows", "Run normalize.py", 1),
        ("Run normalize.py", "Loop Over Rows"),
    )
    return workflow("WF-02 - Lead Cleaning", nodes, conns)


# ===========================================================================
# WF-03 — Lead Deduplication
# ===========================================================================
def build_wf03():
    sticky_text = CONTRACT.format(
        title="WF-03 — LEAD DEDUPLICATION",
        trigger="After WF-02 (polls status=CLEANED rows not yet dedup-checked — see note below)",
        input="Normalized companies row",
        processing="Calls the Python API's /wf03/dedup endpoint (python/enrichment/dedup.py) — matches on normalized_name+location, phone_normalized, or email_normalized",
        output="Duplicate -> discarded (row deleted, survivor logged); unique -> proceeds, status stays CLEANED; ambiguous -> flagged, not auto-merged",
        db_ops="Select + conditional delete on companies, insert to error_log",
        error_path="Ambiguous matches (partial overlap across different rows) flagged for manual review in error_log, not auto-merged",
    )
    nodes = [
        sticky(sticky_text, height=420),
        schedule_trigger("Every 15 min, offset +5", "5-59/15 * * * *", "trigger"),
        supabase_get_many(
            "Get CLEANED companies", "companies",
            "Filter: status = 'CLEANED'. NOTE: dedup.py is idempotent-safe to re-run (a row that survives once won't match itself), but for efficiency at scale add a 'dedup_checked' boolean column in a later migration if this table grows large.",
            "get_cleaned", (-160, 80),
        ),
        split_in_batches("Loop Over Rows", (80, 80)),
        http_request(
            "Run dedup.py",
            "POST",
            "/wf03/dedup",
            "run_dedup",
            (320, 0),
            body_expr='={\n  "company_id": "{{ $json.id }}"\n}',
        ),
    ]
    conns = connect(
        {},
        ("Every 15 min, offset +5", "Get CLEANED companies"),
        ("Get CLEANED companies", "Loop Over Rows"),
        ("Loop Over Rows", "Run dedup.py", 1),
        ("Run dedup.py", "Loop Over Rows"),
    )
    return workflow("WF-03 - Lead Deduplication", nodes, conns)


# ===========================================================================
# WF-04 — Lead Enrichment
# ===========================================================================
def build_wf04():
    sticky_text = CONTRACT.format(
        title="WF-04 — LEAD ENRICHMENT",
        trigger="After WF-03, status=CLEANED (survived dedup)",
        input="companies row",
        processing="Calls the Python API's /wf04/enrich endpoint (python/enrichment/enrich.py) — fills gaps: domain from website, website from domain, WhatsApp candidate flagging",
        output="Enriched companies row (status unchanged — still CLEANED, WF-05 advances it to RESEARCHED)",
        db_ops="Update companies",
        error_path="Enrichment failures don't block progression — the module never raises, just returns fewer updates; proceeds to research with whatever's available",
    )
    nodes = [
        sticky(sticky_text),
        schedule_trigger("Every 15 min, offset +10", "10-59/15 * * * *", "trigger"),
        supabase_get_many("Get CLEANED companies (post-dedup)", "companies", "Filter: status = 'CLEANED'", "get_cleaned", (-160, 80)),
        split_in_batches("Loop Over Rows", (80, 80)),
        http_request(
            "Run enrich.py",
            "POST",
            "/wf04/enrich",
            "run_enrich",
            (320, 0),
            body_expr='={\n  "company_id": "{{ $json.id }}"\n}',
        ),
    ]
    conns = connect(
        {},
        ("Every 15 min, offset +10", "Get CLEANED companies (post-dedup)"),
        ("Get CLEANED companies (post-dedup)", "Loop Over Rows"),
        ("Loop Over Rows", "Run enrich.py", 1),
        ("Run enrich.py", "Loop Over Rows"),
    )
    return workflow("WF-04 - Lead Enrichment", nodes, conns)


# ===========================================================================
# WF-05 — Website/Evidence Research
# ===========================================================================
def build_wf05():
    sticky_text = CONTRACT.format(
        title="WF-05 — WEBSITE/EVIDENCE RESEARCH",
        trigger="After WF-04 (status still CLEANED, now enriched)",
        input="companies row (website, socials)",
        processing="Calls the Python API's /wf05/research endpoint (python/research/ai_extractor.py) — fetches public pages, extracts evidence via prompts/researcher.md, validates provenance in code before writing anything",
        output="research + research_evidence rows, status=RESEARCHED",
        db_ops="Insert research, insert research_evidence (multiple rows)",
        error_path="Zero evidence found -> status still advances to RESEARCHED but flagged low-quality in error_log; scores near 0 on personalization component per docs/06 §2.5",
    )
    nodes = [
        sticky(sticky_text, height=440),
        schedule_trigger("Every 30 min", "*/30 * * * *", "trigger"),
        supabase_get_many("Get enriched CLEANED companies", "companies", "Filter: status = 'CLEANED'", "get_cleaned", (-160, 80)),
        split_in_batches("Loop Over Rows", (80, 80)),
        http_request(
            "Run ai_extractor.py (WF-05)",
            "POST",
            "/wf05/research",
            "run_research",
            (320, 0),
            body_expr='={\n  "company_id": "{{ $json.id }}"\n}',
        ),
    ]
    conns = connect(
        {},
        ("Every 30 min", "Get enriched CLEANED companies"),
        ("Get enriched CLEANED companies", "Loop Over Rows"),
        ("Loop Over Rows", "Run ai_extractor.py (WF-05)", 1),
        ("Run ai_extractor.py (WF-05)", "Loop Over Rows"),
    )
    return workflow("WF-05 - Website Evidence Research", nodes, conns)


# ===========================================================================
# WF-06 — ICP Scoring
# ===========================================================================
def build_wf06():
    sticky_text = CONTRACT.format(
        title="WF-06 — ICP SCORING",
        trigger="After WF-05, status=RESEARCHED",
        input="companies, research, research_evidence, contacts (all fetched inside the python module, not by n8n)",
        processing="Calls the Python API's /wf06/score endpoint (python/scoring/engine.py) — deterministic, NO AI call, implements docs/06-scoring-engine.md exactly. Also runs python/scoring/signal_matcher.py internally to derive pain_signals/buying_signals from evidence before scoring.",
        output="lead_scores row; companies.status -> QUALIFIED if total >= 65, else stays RESEARCHED (visible as tier C/DONT_CONTACT in dashboard)",
        db_ops="Insert lead_scores, update companies.status",
        error_path="Missing inputs (e.g. no contacts row) -> contactability_score=0, scoring proceeds with the rest, does not fail the whole run",
    )
    nodes = [
        sticky(sticky_text, height=440),
        schedule_trigger("Every 30 min, offset +10", "10-59/30 * * * *", "trigger"),
        supabase_get_many("Get RESEARCHED companies not yet scored", "companies",
                           "Filter: status = 'RESEARCHED'. lead_scores has no unique constraint on company_id by design (re-scoring inserts a new history row, docs/06 §4) — this query naturally won't re-select QUALIFIED companies since WF-06 already advanced them.",
                           "get_researched", (-160, 80)),
        split_in_batches("Loop Over Rows", (80, 80)),
        http_request(
            "Run scoring engine.py",
            "POST",
            "/wf06/score",
            "run_scoring",
            (320, 0),
            body_expr='={\n  "company_id": "{{ $json.id }}"\n}',
        ),
    ]
    conns = connect(
        {},
        ("Every 30 min, offset +10", "Get RESEARCHED companies not yet scored"),
        ("Get RESEARCHED companies not yet scored", "Loop Over Rows"),
        ("Loop Over Rows", "Run scoring engine.py", 1),
        ("Run scoring engine.py", "Loop Over Rows"),
    )
    return workflow("WF-06 - ICP Scoring", nodes, conns)


# ===========================================================================
# WF-07 — Campaign Assignment
# ===========================================================================
def build_wf07():
    sticky_text = CONTRACT.format(
        title="WF-07 — CAMPAIGN ASSIGNMENT",
        trigger="After WF-06, status=QUALIFIED",
        input="companies row, active campaigns",
        processing="Calls the Python API's /wf07/match endpoint (python/campaign/matcher.py) — matching logic from docs/09-campaign-spec.md §4",
        output="Campaign match returned as JSON ({matched, campaign_id, campaign_name}) for WF-08 to consume in the SAME run; if no match, lead stays QUALIFIED, visible as unmatched. No DB write here per docs/13 (write happens in WF-08).",
        db_ops="Read campaigns only — no write until WF-08 creates the outreach row",
        error_path="No active campaign matches -> endpoint returns matched=false, this workflow simply does not chain into WF-08 for that company",
    )
    nodes = [
        sticky(sticky_text, height=420),
        schedule_trigger("Every 30 min, offset +20", "20-59/30 * * * *", "trigger"),
        supabase_get_many("Get QUALIFIED companies", "companies", "Filter: status = 'QUALIFIED'", "get_qualified", (-160, 80)),
        split_in_batches("Loop Over Rows", (80, 80)),
        http_request(
            "Run campaign matcher.py",
            "POST",
            "/wf07/match",
            "run_match",
            (320, 0),
            body_expr='={\n  "company_id": "{{ $json.id }}"\n}',
        ),
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "conditions": [{"leftValue": "={{ $json.matched }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
                    "combinator": "and",
                },
                "options": {},
                "notesInFlow": "Only matched=true rows should chain into WF-08 (Message Generation) as a sub-workflow call — wire an Execute Workflow node here pointing at WF-08 in your n8n instance once both are imported. $json.campaign_id is already present directly on this node's output — the Python API returns matched/campaign_id/campaign_name as real JSON, no parsing step needed.",
            },
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [560, 0],
            "id": "matched_check",
            "name": "Matched?",
        },
    ]
    conns = connect(
        {},
        ("Every 30 min, offset +20", "Get QUALIFIED companies"),
        ("Get QUALIFIED companies", "Loop Over Rows"),
        ("Loop Over Rows", "Run campaign matcher.py", 1),
        ("Run campaign matcher.py", "Matched?"),
        ("Matched?", "Loop Over Rows", 0),
    )
    return workflow("WF-07 - Campaign Assignment", nodes, conns)


# ===========================================================================
# WF-08 — Message Generation
# ===========================================================================
def build_wf08():
    sticky_text = CONTRACT.format(
        title="WF-08 — MESSAGE GENERATION",
        trigger="After WF-07 finds a match (chained via Execute Workflow, or standalone poll below)",
        input="Structured object per docs/08-personalization-spec.md §2 (built inside the python module from company_id + campaign_id)",
        processing="Calls the Python API's /wf08/generate endpoint (python/personalization/generator.py) -> AI call using prompts/personalizer.md, then python/personalization/validator.py checks (docs/08 §6)",
        output="outreach row(s), status=PENDING_REVIEW; companies.status -> REVIEW",
        db_ops="Insert outreach",
        error_path="Validation failures flagged in error_log (warning field) but still routed to review, per docs/08-personalization-spec.md §6 (never silently blocked)",
    )
    nodes = [
        sticky(sticky_text, height=440),
        webhook_trigger("From WF-07 (company_id + campaign_id) or standalone poll", "wf08-generate", "trigger"),
        http_request(
            "Run personalization generator.py",
            "POST",
            "/wf08/generate",
            "run_generate",
            (80, 80),
            body_expr='={\n  "company_id": "{{ $json.body.company_id }}",\n  "campaign_id": "{{ $json.body.campaign_id }}"\n}',
        ),
    ]
    conns = connect(
        {},
        ("From WF-07 (company_id + campaign_id) or standalone poll", "Run personalization generator.py"),
    )
    return workflow("WF-08 - Message Generation", nodes, conns)


# ===========================================================================
# WF-09 — Human Approval
# ===========================================================================
def build_wf09():
    sticky_text = CONTRACT.format(
        title="WF-09 — HUMAN APPROVAL (dashboard-backed)",
        trigger="Webhook, called by dashboard/index.html — 'list' action for reads, 'approve'/'reject' for writes",
        input="{action: 'list'|'approve'|'reject', outreach_id?, edited_message?, reason?} — per docs/10-outreach-sop.md §3",
        processing="'list' calls the Python API's /wf09/list endpoint; 'approve'/'reject' call /wf09/approve and /wf09/reject. This workflow just routes and forwards — no business logic lives in n8n itself, matching docs/14-security-spec.md §7 ('no separate exposed API surface') since the Python API is the only thing that ever touches Supabase.",
        output="'list' returns the REVIEW-state queue sorted by priority; 'approve'/'reject' update outreach.status (APPROVED or REJECTED); companies.status reverts to QUALIFIED on reject",
        db_ops="Read (list) or update (approve/reject) outreach + companies",
        error_path="ReviewActionError (e.g. wrong current status, empty rejection reason) returned as a 400/500 response to the dashboard, nothing is written",
    )
    nodes = [
        sticky(sticky_text, height=440),
        webhook_trigger("Dashboard action (list/approve/reject)", "wf09-review-action", "trigger"),
        {
            "parameters": {
                "rules": {
                    "values": [
                        {"conditions": {"conditions": [{"leftValue": "={{ $json.body.action }}", "rightValue": "list", "operator": {"type": "string", "operation": "equals"}}]}, "outputKey": "list"},
                        {"conditions": {"conditions": [{"leftValue": "={{ $json.body.action }}", "rightValue": "approve", "operator": {"type": "string", "operation": "equals"}}]}, "outputKey": "approve"},
                        {"conditions": {"conditions": [{"leftValue": "={{ $json.body.action }}", "rightValue": "reject", "operator": {"type": "string", "operation": "equals"}}]}, "outputKey": "reject"},
                    ]
                },
                "options": {},
            },
            "type": "n8n-nodes-base.switch",
            "typeVersion": 3,
            "position": [80, 80],
            "id": "route_action",
            "name": "Route by action",
        },
        http_request("Run actions.list_review_queue()", "POST", "/wf09/list", "run_list", (320, -120)),
        http_request(
            "Run actions.approve()",
            "POST",
            "/wf09/approve",
            "run_approve",
            (320, 60),
            body_expr='={\n  "outreach_id": "{{ $json.body.outreach_id }}",\n  "edited_message": {{ JSON.stringify($json.body.edited_message || null) }}\n}',
        ),
        http_request(
            "Run actions.reject()",
            "POST",
            "/wf09/reject",
            "run_reject",
            (320, 240),
            body_expr='={\n  "outreach_id": "{{ $json.body.outreach_id }}",\n  "reason": "{{ $json.body.reason }}"\n}',
        ),
    ]
    conns = connect(
        {},
        ("Dashboard action (list/approve/reject)", "Route by action"),
        ("Route by action", "Run actions.list_review_queue()", 0),
        ("Route by action", "Run actions.approve()", 1),
        ("Route by action", "Run actions.reject()", 2),
    )
    return workflow("WF-09 - Human Approval", nodes, conns)


# ===========================================================================
# WF-10 — Outreach Queue / Send Confirmation
# ===========================================================================
def build_wf10():
    sticky_text = CONTRACT.format(
        title="WF-10 — OUTREACH QUEUE / SEND CONFIRMATION",
        trigger="Webhook, called by dashboard — 'list' action for the send queue, 'mark_sent' for the confirm button",
        input="{action: 'list'|'mark_sent', outreach_id?} — per docs/10-outreach-sop.md §4",
        processing="'list' calls the Python API's /wf10/list endpoint (APPROVED rows waiting to be sent manually); 'mark_sent' calls /wf10/mark_sent — enforces the 'no concurrent active outreach per company' guardrail (docs/05-lead-lifecycle.md §4) and schedules the first follow-up",
        output="'list' returns APPROVED rows; 'mark_sent' sets outreach.status = SENT -> ACTIVE, next_follow_up_at set, companies.status = CONTACTED",
        db_ops="Read or update outreach, update companies",
        error_path="ReviewActionError (wrong status, or a concurrent active outreach already exists) returned as a 400/500 to the dashboard, nothing is written",
    )
    nodes = [
        sticky(sticky_text, height=440),
        webhook_trigger("Dashboard action (list/mark_sent)", "wf10-outreach-queue", "trigger"),
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "conditions": [{"leftValue": "={{ $json.body.action }}", "rightValue": "list", "operator": {"type": "string", "operation": "equals"}}],
                    "combinator": "and",
                },
                "options": {},
            },
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [80, 80],
            "id": "is_list",
            "name": "List or Mark Sent?",
        },
        http_request("Run actions.list_send_queue()", "POST", "/wf10/list", "run_list", (320, 0)),
        http_request(
            "Run actions.mark_sent()",
            "POST",
            "/wf10/mark_sent",
            "run_mark_sent",
            (320, 200),
            body_expr='={\n  "outreach_id": "{{ $json.body.outreach_id }}"\n}',
        ),
    ]
    conns = connect(
        {},
        ("Dashboard action (list/mark_sent)", "List or Mark Sent?"),
        ("List or Mark Sent?", "Run actions.list_send_queue()", 0),
        ("List or Mark Sent?", "Run actions.mark_sent()", 1),
    )
    return workflow("WF-10 - Outreach Queue Send Confirmation", nodes, conns)


# ===========================================================================
# WF-11 — Follow-up Scheduler
# ===========================================================================
def build_wf11():
    sticky_text = CONTRACT.format(
        title="WF-11 — FOLLOW-UP SCHEDULER",
        trigger="Scheduled, daily",
        input="outreach rows where status=ACTIVE and next_follow_up_at <= now() (queried inside the python module)",
        processing="Calls the Python API's /wf11/run endpoint (python/followup/scheduler.py) — implements docs/11-follow-up.md §2 cadence and max-attempts logic, drafts follow-ups via the personalization engine",
        output="New follow-up outreach row in PENDING_REVIEW, or outreach.status -> DEAD at max attempts (and companies.status -> DEAD if no other active campaign/opportunity)",
        db_ops="Update outreach, insert new draft row if generating a follow-up",
        error_path="Follow-up generation AI failures logged to error_log, that row simply isn't advanced this run (retried next day since next_follow_up_at wasn't cleared)",
    )
    nodes = [
        sticky(sticky_text, height=440),
        schedule_trigger("Daily 7am", "0 7 * * *", "trigger"),
        http_request("Run followup scheduler.py", "POST", "/wf11/run", "run_followup", (80, 80)),
    ]
    conns = connect({}, ("Daily 7am", "Run followup scheduler.py"))
    return workflow("WF-11 - Follow-up Scheduler", nodes, conns)


# ===========================================================================
# WF-12 — Response Processing
# ===========================================================================
def build_wf12():
    sticky_text = CONTRACT.format(
        title="WF-12 — RESPONSE PROCESSING",
        trigger="Inbound message webhook (WhatsApp Business API / email parser), or manual entry from the dashboard",
        input="{outreach_id, response_text}",
        processing="Calls the Python API's /wf12/classify endpoint (python/classification/classifier.py) — hard UNSUBSCRIBE keyword pre-check runs BEFORE any AI call, then classifies via prompts/classifier.md, then routes per docs/12-response-classification.md §1",
        output="responses row; outreach.status updated; follow-ups stopped; companies.status updated per the classification's routing rule",
        db_ops="Insert responses, update outreach, update companies",
        error_path="Classification failures (AI error or invalid category) default to UNKNOWN, never guess INTERESTED/NOT_INTERESTED — docs/12 §4",
    )
    nodes = [
        sticky(sticky_text, height=440),
        webhook_trigger("Inbound reply (WhatsApp/email/manual)", "wf12-inbound-reply", "trigger"),
        http_request(
            "Run classifier.py",
            "POST",
            "/wf12/classify",
            "run_classify",
            (80, 80),
            body_expr='={\n  "outreach_id": "{{ $json.body.outreach_id }}",\n  "response_text": {{ JSON.stringify($json.body.response_text) }}\n}',
        ),
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "conditions": [{"leftValue": "={{ $json.notify_immediately }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
                    "combinator": "and",
                },
                "options": {},
                "notesInFlow": "docs/12 §1: INTERESTED, PRICE, MEETING notify Hooze immediately rather than waiting for the daily review",
            },
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [320, 80],
            "id": "should_notify",
            "name": "High-value reply?",
        },
        notify_node(
            "Notify Hooze immediately",
            "notify_hooze",
            (560, 0),
            "=🔥 High-value reply received! Check the dashboard now — classification: {{ $json.classification }}",
        ),
    ]
    conns = connect(
        {},
        ("Inbound reply (WhatsApp/email/manual)", "Run classifier.py"),
        ("Run classifier.py", "High-value reply?"),
        ("High-value reply?", "Notify Hooze immediately", 0),
    )
    return workflow("WF-12 - Response Processing", nodes, conns)


# ===========================================================================
# WF-13 — Opportunity Management
# ===========================================================================
def build_wf13():
    sticky_text = CONTRACT.format(
        title="WF-13 — OPPORTUNITY MANAGEMENT",
        trigger="Webhook, dashboard action ('list' for the REPLIED queue + open opportunities, 'advance' for stage changes). Note: the MEETING auto-create path is handled directly inside python/classification/classifier.py (WF-12), not here — this workflow covers the manual dashboard path (PROPOSAL/WON/LOST stage changes Hooze makes personally) plus the read side.",
        input="{action: 'list'|'advance', company_id?, stage?, notes?}",
        processing="'list' calls the Python API's /wf13/list endpoint; 'advance' calls /wf13/advance (python/opportunities/manager.py create_or_advance()) — enforces stages only move forward",
        output="'list' returns REPLIED companies + their latest response; 'advance' creates/updates an opportunities row; companies.status updated (MEETING/PROPOSAL/WON/LOST)",
        db_ops="Read, or insert/update opportunities + update companies",
        error_path="OpportunityError (invalid stage, or attempting to move backward) returned as a 400/500 to the dashboard",
    )
    nodes = [
        sticky(sticky_text, height=460),
        webhook_trigger("Dashboard action (list/advance)", "wf13-opportunities", "trigger"),
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "conditions": [{"leftValue": "={{ $json.body.action }}", "rightValue": "list", "operator": {"type": "string", "operation": "equals"}}],
                    "combinator": "and",
                },
                "options": {},
            },
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [80, 80],
            "id": "is_list",
            "name": "List or Advance?",
        },
        http_request("Run actions.list_replied_queue()", "POST", "/wf13/list", "run_list", (320, 0)),
        http_request(
            "Run opportunities manager.py",
            "POST",
            "/wf13/advance",
            "run_advance",
            (320, 200),
            body_expr='={\n  "company_id": "{{ $json.body.company_id }}",\n  "stage": "{{ $json.body.stage }}",\n  "notes": {{ JSON.stringify($json.body.notes || null) }}\n}',
        ),
    ]
    conns = connect(
        {},
        ("Dashboard action (list/advance)", "List or Advance?"),
        ("List or Advance?", "Run actions.list_replied_queue()", 0),
        ("List or Advance?", "Run opportunities manager.py", 1),
    )
    return workflow("WF-13 - Opportunity Management", nodes, conns)


# ===========================================================================
# WF-14 — Analytics
# ===========================================================================
def build_wf14():
    sticky_text = CONTRACT.format(
        title="WF-14 — ANALYTICS",
        trigger="Scheduled, weekly (docs/15-analytics-spec.md §8: 'weekly check, not a daily distraction')",
        input="All pipeline tables (read inside the python module)",
        processing="Calls the Python API's /wf14/run endpoint (python/analytics/reports.py) — computes docs/15-analytics-spec.md §2/§3 funnel + metrics, sliced by source",
        output="Rows written to analytics_snapshots, surfaced on dashboard",
        db_ops="Read all tables, write aggregates to analytics_snapshots",
        error_path="If a metric's denominator is 0, that metric is stored as null (not fabricated as 0%) — see python/analytics/reports.py safe_div()",
    )
    nodes = [
        sticky(sticky_text, height=420),
        schedule_trigger("Weekly, Monday 6am", "0 6 * * 1", "trigger"),
        http_request("Run analytics reports.py", "POST", "/wf14/run", "run_analytics", (80, 80)),
    ]
    conns = connect({}, ("Weekly, Monday 6am", "Run analytics reports.py"))
    return workflow("WF-14 - Analytics", nodes, conns)


# ===========================================================================
# WF-15 — Error Monitoring
# ===========================================================================
def build_wf15():
    sticky_text = CONTRACT.format(
        title="WF-15 — ERROR MONITORING",
        trigger="Scheduled health check (every 30 min) — reads the error_log table every other workflow's Python module already writes to on failure. (True per-workflow n8n Error Triggers can ALSO be wired to point here for immediate notification; this scheduled poll is the safety net that works even if an individual workflow's Error Trigger isn't wired up yet.)",
        input="error_log rows created since the last check, plus a stuck-lead health check (companies sitting in one status too long)",
        processing="Aggregates failures, flags data-quality issues per docs/13-n8n-architecture.md WF-15",
        output="Telegram notification to Hooze; error_log rows are the dashboard's error log view directly (no separate table needed)",
        db_ops="Select from error_log and companies (for the stuck-lead check); no writes",
        error_path="N/A — this workflow IS the error path for every other workflow.",
    )
    nodes = [
        sticky(sticky_text, height=460),
        schedule_trigger("Every 30 min", "*/30 * * * *", "trigger"),
        supabase_get_many(
            "Get recent error_log rows", "error_log",
            "Filter: created_at >= now() - interval '30 minutes'",
            "get_errors", (-160, 0),
        ),
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "conditions": [{"leftValue": "={{ $json.length }}", "rightValue": 0, "operator": {"type": "number", "operation": "gt"}}],
                    "combinator": "and",
                },
                "options": {},
            },
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [80, 0],
            "id": "has_errors",
            "name": "Any new errors?",
        },
        notify_node(
            "Notify Hooze of errors",
            "notify_errors",
            (320, -80),
            "=⚠️ {{ $json.length }} new pipeline error(s) in the last 30 min. Check the dashboard error log.",
        ),
        supabase_get_many(
            "Check for stuck leads", "companies",
            "Filter: status NOT IN ('WON','LOST','DEAD') AND updated_at < now() - interval '7 days' — a lead sitting untouched for a week in an active pipeline status is a data-quality smell worth flagging (docs/13 WF-15: 'flags data-quality issues (e.g. leads stuck in one state too long)')",
            "get_stuck", (-160, 160),
        ),
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "conditions": [{"leftValue": "={{ $json.length }}", "rightValue": 0, "operator": {"type": "number", "operation": "gt"}}],
                    "combinator": "and",
                },
                "options": {},
            },
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [80, 160],
            "id": "has_stuck",
            "name": "Any stuck leads?",
        },
        notify_node(
            "Notify Hooze of stuck leads",
            "notify_stuck",
            (320, 240),
            "=🐌 {{ $json.length }} lead(s) have been stuck in the same status for 7+ days. Check the dashboard.",
        ),
    ]
    conns = connect(
        {},
        ("Every 30 min", "Get recent error_log rows"),
        ("Every 30 min", "Check for stuck leads"),
        ("Get recent error_log rows", "Any new errors?"),
        ("Any new errors?", "Notify Hooze of errors", 0),
        ("Check for stuck leads", "Any stuck leads?"),
        ("Any stuck leads?", "Notify Hooze of stuck leads", 0),
    )
    return workflow("WF-15 - Error Monitoring", nodes, conns)


if __name__ == "__main__":
    builders = {
        "WF-01-lead-import.json": build_wf01,
        "WF-02-lead-cleaning.json": build_wf02,
        "WF-03-lead-deduplication.json": build_wf03,
        "WF-04-lead-enrichment.json": build_wf04,
        "WF-05-website-evidence-research.json": build_wf05,
        "WF-06-icp-scoring.json": build_wf06,
        "WF-07-campaign-assignment.json": build_wf07,
        "WF-08-message-generation.json": build_wf08,
        "WF-09-human-approval.json": build_wf09,
        "WF-10-outreach-queue-send-confirmation.json": build_wf10,
        "WF-11-follow-up-scheduler.json": build_wf11,
        "WF-12-response-processing.json": build_wf12,
        "WF-13-opportunity-management.json": build_wf13,
        "WF-14-analytics.json": build_wf14,
        "WF-15-error-monitoring.json": build_wf15,
    }
    for filename, builder in builders.items():
        write(filename, builder())
