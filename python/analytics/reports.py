"""
python/analytics/reports.py — WF-14 Weekly Analytics

Computes the funnel and metrics from docs/15-analytics-spec.md §2/§3 and
writes one row per (period, slice) to `analytics_snapshots`
(database/migrations/010_analytics_snapshots.sql).

IMPORTANT SCHEMA LIMITATION (documented here deliberately, not hidden):
`companies.status` is a single CURRENT-state field, not a status-history
log — there is no table recording WHEN a company entered each funnel stage.
Because docs/05-lead-lifecycle.md's status machine only moves forward
(never regresses), "how many companies REACHED stage X" is still correctly
computable as "how many companies have a CURRENT status that is X or any
later stage in the funnel" — a company currently WON necessarily passed
through CONTACTED. That's the technique this module uses. What it CANNOT
compute correctly from this schema:
  - Time-to-review (needs a REVIEW-entry timestamp, not just current status)
  - Edit rate (needs an "was this message edited before approval" flag —
    outreach has no such column in V1)
  - Per-message-variant breakdown (outreach has no `variant` column — only
    channel is tracked; personalization currently just creates N outreach
    rows without a shared variant/group identifier)
These three are flagged as V2 schema additions in BUILD_LOG.md rather than
silently approximated with fabricated numbers, per the same "no invented
facts" principle that governs docs/07/08.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

# docs/15-analytics-spec.md §2 — the funnel, in order. Used to compute
# "reached stage X" as "current status in FUNNEL[FUNNEL.index(X):]".
FUNNEL = [
    "DISCOVERED", "CLEANED", "RESEARCHED", "QUALIFIED", "PERSONALIZED",
    "REVIEW", "APPROVED", "CONTACTED", "REPLIED", "MEETING", "PROPOSAL", "WON",
]
# DEAD and LOST are terminal off-funnel states — a company that reached
# QUALIFIED and was later marked DEAD should still count as "reached
# QUALIFIED" for historical funnel purposes, but since status is
# current-state-only, a DEAD/LOST company's peak stage is unrecoverable from
# this schema. They're excluded from "reached X" counts for X beyond
# whatever their terminal status was — a known undercount, see module
# docstring. This is the honest, non-fabricated interpretation of a single
# mutable status field.


def _reached_counts(companies: list[dict[str, Any]]) -> dict[str, int]:
    counts = {stage: 0 for stage in FUNNEL}
    for c in companies:
        status = c.get("status")
        if status not in FUNNEL:
            continue  # DEAD/LOST — see docstring
        idx = FUNNEL.index(status)
        for stage in FUNNEL[: idx + 1]:
            counts[stage] += 1
    return counts


def compute_funnel_metrics(companies: list[dict[str, Any]], outreach: list[dict[str, Any]]) -> dict[str, Any]:
    reached = _reached_counts(companies)

    cleaned = reached["CLEANED"] or 0
    qualified = reached["QUALIFIED"] or 0
    contacted = reached["CONTACTED"] or 0
    replied = reached["REPLIED"] or 0
    meeting = reached["MEETING"] or 0
    won = reached["WON"] or 0

    outreach_sent = sum(1 for o in outreach if o.get("status") not in ("DRAFT", "PENDING_REVIEW", "REJECTED"))
    approved = sum(1 for o in outreach if o.get("status") not in ("DRAFT", "PENDING_REVIEW", "REJECTED"))
    rejected = sum(1 for o in outreach if o.get("status") == "REJECTED")
    unsubscribed = sum(1 for o in outreach if o.get("status") == "NOT_INTERESTED" and o.get("company_id") in {
        c["id"] for c in companies if c.get("status") == "DEAD"
    })

    positive_replies = sum(
        1 for o in outreach if o.get("status") == "REPLIED"
    )  # approximation: see note below

    def safe_div(n: int, d: int) -> float | None:
        return round(n / d, 4) if d else None

    return {
        "funnel_counts": reached,
        "qualification_rate": safe_div(qualified, cleaned),
        "reply_rate": safe_div(replied, contacted),
        "meeting_rate": safe_div(meeting, contacted),
        "win_rate": safe_div(won, meeting),
        "rejection_rate": safe_div(rejected, approved + rejected),
        "unsubscribe_rate": safe_div(unsubscribed, contacted),
        # positive_rate needs responses.classification breakdown, computed
        # separately in compute_positive_rate() below (needs `responses`
        # table data, not just `outreach`/`companies`).
    }


def compute_positive_rate(responses: list[dict[str, Any]]) -> float | None:
    total = len(responses)
    if total == 0:
        return None
    positive = sum(1 for r in responses if r.get("classification") in ("INTERESTED", "MEETING", "PRICE"))
    return round(positive / total, 4)


def slice_by(companies: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    """Groups companies by a slice key (e.g. 'source') for the sliced views
    in docs/15-analytics-spec.md §2/§6."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for c in companies:
        value = c.get(key) or "UNKNOWN"
        groups.setdefault(value, []).append(c)
    return groups


# ---------------------------------------------------------------------------
# I/O wrapper (WF-14 entry point) — runs weekly
# ---------------------------------------------------------------------------
def wf14_run_weekly() -> dict[str, Any]:
    from python.config import get_client

    client = get_client()
    companies = client.table("companies").select("*").execute().data
    outreach = client.table("outreach").select("*").execute().data
    responses = client.table("responses").select("*").execute().data

    today = date.today()
    period_start = today - timedelta(days=7)

    overall = compute_funnel_metrics(companies, outreach)
    overall["positive_rate"] = compute_positive_rate(responses)

    snapshots = [{"slice_type": "OVERALL", "slice_value": "ALL", "metrics": overall}]

    # Sliced by source (docs/15-analytics-spec.md §6)
    for source, group in slice_by(companies, "source").items():
        group_ids = {c["id"] for c in group}
        group_outreach = [o for o in outreach if o.get("company_id") in group_ids]
        metrics = compute_funnel_metrics(group, group_outreach)
        snapshots.append({"slice_type": "SOURCE", "slice_value": source, "metrics": metrics})

    client.table("analytics_snapshots").insert(
        [
            {
                "period_start": period_start.isoformat(),
                "period_end": today.isoformat(),
                "slice_type": s["slice_type"],
                "slice_value": s["slice_value"],
                "metrics": s["metrics"],
            }
            for s in snapshots
        ]
    ).execute()

    return {"snapshots_written": len(snapshots), "period_start": period_start.isoformat(), "period_end": today.isoformat()}


if __name__ == "__main__":
    print(wf14_run_weekly())
