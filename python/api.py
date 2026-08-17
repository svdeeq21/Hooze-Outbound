"""
python/api.py — HTTP wrapper around every python/ module, for a Railway
deployment where n8n and Python run as two separate services in the same
Railway project instead of on one shared VPS.

WHY THIS EXISTS: the original design (see DEPLOYMENT.md) had n8n's Execute
Command nodes shell out to `python3 -m python.X.Y` directly, because n8n
and Python lived on the same machine. On Railway, every service is its own
isolated container — there's no "same machine" to shell into. The idiomatic
Railway fix is exactly what Railway is built for: run Python as its own
small service in the same project, and let n8n reach it over Railway's
*private* network (a `servicename.railway.internal` address that only
other services in the same project can reach — never exposed to the public
internet). This file is that service's entire HTTP surface.

Nothing about the underlying business logic changes. Every endpoint below
is a thin pass-through to the exact same function documented and tested in
its home module (e.g. POST /wf06/score just calls
python.scoring.engine.score_from_db() and returns its result as JSON) — see
that module's own docstring/comments for what the function actually does.
This file adds NO new logic, only a network-callable shape around logic
that already existed and was already tested.

SECURITY: this service should be deployed with Railway's "Private
Networking" only (no public domain attached) — see RAILWAY_DEPLOYMENT.md.
As defense in depth on top of that (not instead of it), every endpoint also
checks a shared-secret header, matching the pattern docs/14-security-spec.md
§3 already requires for n8n's own inbound webhooks.
"""
from __future__ import annotations

import os
from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Hooze Outbound — Python API", version="1.0")

INTERNAL_SECRET = os.environ.get("PYTHON_API_SECRET")  # see RAILWAY_DEPLOYMENT.md


def _check_secret(x_internal_secret: str | None) -> None:
    """No-op if PYTHON_API_SECRET isn't set (e.g. local dev) — but if it IS
    set (which it should be in any real Railway deployment), every request
    must present it. Fails closed once configured, never fails open."""
    if INTERNAL_SECRET and x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Internal-Secret header")


def _jsonable(value: Any) -> Any:
    """Dataclasses (e.g. ScoreResult) aren't JSON-serializable by default —
    convert them, otherwise pass dicts/lists/primitives straight through."""
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return value


def _wrap_errors(fn, *args, **kwargs) -> dict[str, Any]:
    """Every python/ module already handles its OWN expected failure modes
    internally (writes to error_log, returns a status dict — see each
    module's docstring). This catches anything unexpected so a single bad
    call returns a clean 500 with a message instead of an opaque crash,
    without swallowing or reinterpreting any of that existing error
    handling."""
    try:
        return _jsonable(fn(*args, **kwargs))
    except Exception as exc:  # noqa: BLE001 — intentionally broad, see docstring
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, str]:
    """No secret required — Railway's own health check hits this."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Request bodies — one per endpoint, matching each underlying function's
# real arguments exactly (see the docstring above: no new logic here).
# ---------------------------------------------------------------------------
class CompanyIdBody(BaseModel):
    company_id: str


class GenerateBody(BaseModel):
    company_id: str
    campaign_id: str


class ApproveBody(BaseModel):
    outreach_id: str
    edited_message: str | None = None


class RejectBody(BaseModel):
    outreach_id: str
    reason: str


class OutreachIdBody(BaseModel):
    outreach_id: str


class ClassifyBody(BaseModel):
    outreach_id: str
    response_text: str


class AdvanceBody(BaseModel):
    company_id: str
    stage: str
    notes: str | None = None


# ---------------------------------------------------------------------------
# WF-02 Lead Cleaning
# ---------------------------------------------------------------------------
@app.post("/wf02/clean")
def wf02_clean(body: CompanyIdBody, x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.enrichment.normalize import clean_company

    return _wrap_errors(clean_company, body.company_id)


# ---------------------------------------------------------------------------
# WF-03 Lead Deduplication
# ---------------------------------------------------------------------------
@app.post("/wf03/dedup")
def wf03_dedup(body: CompanyIdBody, x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.enrichment.dedup import dedup_company

    return _wrap_errors(dedup_company, body.company_id)


# ---------------------------------------------------------------------------
# WF-04 Lead Enrichment
# ---------------------------------------------------------------------------
@app.post("/wf04/enrich")
def wf04_enrich(body: CompanyIdBody, x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.enrichment.enrich import enrich_from_db

    return _wrap_errors(enrich_from_db, body.company_id)


# ---------------------------------------------------------------------------
# WF-05 Website/Evidence Research
# ---------------------------------------------------------------------------
@app.post("/wf05/research")
def wf05_research(body: CompanyIdBody, x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.research.ai_extractor import wf05_research as run

    return _wrap_errors(run, body.company_id)


# ---------------------------------------------------------------------------
# WF-06 ICP Scoring
# ---------------------------------------------------------------------------
@app.post("/wf06/score")
def wf06_score(body: CompanyIdBody, x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.scoring.engine import score_from_db

    return _wrap_errors(score_from_db, body.company_id)


# ---------------------------------------------------------------------------
# WF-07 Campaign Assignment
# ---------------------------------------------------------------------------
@app.post("/wf07/match")
def wf07_match(body: CompanyIdBody, x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.campaign.matcher import wf07_assign

    return _wrap_errors(wf07_assign, body.company_id)


# ---------------------------------------------------------------------------
# WF-08 Message Generation
# ---------------------------------------------------------------------------
@app.post("/wf08/generate")
def wf08_generate(body: GenerateBody, x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.personalization.generator import wf08_generate as run

    return _wrap_errors(run, body.company_id, body.campaign_id)


# ---------------------------------------------------------------------------
# WF-09 Human Approval
# ---------------------------------------------------------------------------
@app.post("/wf09/list")
def wf09_list(x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.review.actions import list_review_queue

    return _wrap_errors(list_review_queue)


@app.post("/wf09/approve")
def wf09_approve(body: ApproveBody, x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.review.actions import approve

    return _wrap_errors(approve, body.outreach_id, body.edited_message)


@app.post("/wf09/reject")
def wf09_reject(body: RejectBody, x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.review.actions import reject

    return _wrap_errors(reject, body.outreach_id, body.reason)


# ---------------------------------------------------------------------------
# WF-10 Outreach Queue / Send Confirmation
# ---------------------------------------------------------------------------
@app.post("/wf10/list")
def wf10_list(x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.review.actions import list_send_queue

    return _wrap_errors(list_send_queue)


@app.post("/wf10/mark_sent")
def wf10_mark_sent(body: OutreachIdBody, x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.review.actions import mark_sent

    return _wrap_errors(mark_sent, body.outreach_id)


# ---------------------------------------------------------------------------
# WF-11 Follow-up Scheduler
# ---------------------------------------------------------------------------
@app.post("/wf11/run")
def wf11_run(x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.followup.scheduler import wf11_run_daily

    return _wrap_errors(wf11_run_daily)


# ---------------------------------------------------------------------------
# WF-12 Response Processing
# ---------------------------------------------------------------------------
@app.post("/wf12/classify")
def wf12_classify(body: ClassifyBody, x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.classification.classifier import wf12_process_response

    return _wrap_errors(wf12_process_response, body.outreach_id, body.response_text)


# ---------------------------------------------------------------------------
# WF-13 Opportunity Management
# ---------------------------------------------------------------------------
@app.post("/wf13/list")
def wf13_list(x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.review.actions import list_replied_queue

    return _wrap_errors(list_replied_queue)


@app.post("/wf13/advance")
def wf13_advance(body: AdvanceBody, x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.opportunities.manager import create_or_advance

    return _wrap_errors(create_or_advance, body.company_id, body.stage, notes=body.notes)


# ---------------------------------------------------------------------------
# WF-14 Analytics
# ---------------------------------------------------------------------------
@app.post("/wf14/run")
def wf14_run(x_internal_secret: str | None = Header(default=None)):
    _check_secret(x_internal_secret)
    from python.analytics.reports import wf14_run_weekly

    return _wrap_errors(wf14_run_weekly)
