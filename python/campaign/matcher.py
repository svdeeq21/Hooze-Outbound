"""
python/campaign/matcher.py — WF-07 Campaign Assignment

Implements docs/09-campaign-spec.md §4 exactly. Pure function
(`match_campaign`) over plain dicts, same pattern as every other module in
this layer — no DB dependency in the decision logic itself.
"""
from __future__ import annotations

from typing import Any


def match_campaign(
    company: dict[str, Any],
    active_campaigns: list[dict[str, Any]],
    reply_rates: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    """Returns the matching campaign dict, or None if no active campaign
    matches (docs/09 §4: "the lead stays QUALIFIED but does not enter
    PERSONALIZED... visible as 'qualified, no active campaign'").

    `reply_rates`: optional {campaign_id: reply_rate} from
    python/analytics/reports.py — "once data exists" per §4. Falls back to
    "most recently activated campaign wins" (assumes `active_campaigns` is
    already sorted newest-first by the caller, since dict ordering from a
    DB query isn't a decision this function should make on its own).
    """
    reply_rates = reply_rates or {}

    matches = [
        c
        for c in active_campaigns
        if c.get("status") == "ACTIVE"
        and c.get("industry", "").strip().lower() == company.get("industry", "").strip().lower()
        and c.get("target_location", "").strip().lower() == company.get("location", "").strip().lower()
    ]

    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    # Multiple matches: prefer higher historical reply rate if we have data
    # for ANY of the candidates; otherwise fall back to "most recent" order
    # as already provided by the caller.
    scored = [(c, reply_rates.get(c.get("id"))) for c in matches]
    if any(rate is not None for _, rate in scored):
        scored.sort(key=lambda pair: (pair[1] is None, -(pair[1] or 0)))
        return scored[0][0]

    return matches[0]  # caller-provided order = most-recently-activated first


# ---------------------------------------------------------------------------
# I/O wrapper (WF-07 entry point)
# ---------------------------------------------------------------------------
def wf07_assign(company_id: str) -> dict[str, Any]:
    from python.config import get_client

    client = get_client()
    company = client.table("companies").select("*").eq("id", company_id).single().execute().data
    campaigns = (
        client.table("campaigns")
        .select("*")
        .eq("status", "ACTIVE")
        .order("created_at", desc=True)  # most-recently-activated first, per §4 fallback rule
        .execute()
        .data
    )

    matched = match_campaign(company, campaigns)

    if matched is None:
        return {"matched": False, "reason": "No active campaign matches industry+location"}

    # No DB write here by design (docs/13-n8n-architecture.md WF-07: "no
    # write until WF-08 creates the outreach row") — the match is simply
    # returned for WF-08 to consume directly in the same n8n run.
    return {"matched": True, "campaign_id": matched["id"], "campaign_name": matched.get("name")}


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m python.campaign.matcher <company_id>")
        sys.exit(1)
    print(wf07_assign(sys.argv[1]))
