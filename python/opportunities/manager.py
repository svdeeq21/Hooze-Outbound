"""
python/opportunities/manager.py — WF-13 Opportunity Management

Per docs/13-n8n-architecture.md WF-13: triggered manually from the
dashboard, OR automatically when python/classification/classifier.py
classifies a response as INTERESTED/MEETING/PRICE (docs/12 §1). The MEETING
auto-create path already lives in classifier.py (wf12_process_response) —
this module is the general-purpose create/update entry point both that
auto-path and manual dashboard actions call, so there is exactly one place
that enforces the valid stage transitions below.
"""
from __future__ import annotations

from typing import Any

VALID_STAGES = ["MEETING", "PROPOSAL", "WON", "LOST"]

_COMPANY_STATUS_FOR_STAGE = {
    "MEETING": "MEETING",
    "PROPOSAL": "PROPOSAL",
    "WON": "WON",
    "LOST": "LOST",
}


class OpportunityError(ValueError):
    pass


def create_or_advance(
    company_id: str,
    stage: str,
    estimated_value: float | None = None,
    notes: str | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    """Creates a new opportunities row, or advances the company's existing
    open opportunity to a later stage. Stages only move forward
    (MEETING -> PROPOSAL -> WON/LOST) — matching the general one-way status
    discipline used throughout this system (docs/05-lead-lifecycle.md §1).
    """
    from python.config import get_client

    if stage not in VALID_STAGES:
        raise OpportunityError(f"Invalid stage {stage!r}, must be one of {VALID_STAGES}")

    client = get_client()
    existing = (
        client.table("opportunities")
        .select("*")
        .eq("company_id", company_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )

    if existing:
        current = existing[0]
        current_idx = VALID_STAGES.index(current["stage"]) if current["stage"] in VALID_STAGES else -1
        new_idx = VALID_STAGES.index(stage)
        if new_idx < current_idx and current["stage"] not in ("WON", "LOST"):
            raise OpportunityError(
                f"Cannot move opportunity from {current['stage']} back to {stage} — stages only advance"
            )
        updates: dict[str, Any] = {"stage": stage}
        if estimated_value is not None:
            updates["estimated_value"] = estimated_value
        if notes is not None:
            updates["notes"] = notes
        if next_action is not None:
            updates["next_action"] = next_action
        client.table("opportunities").update(updates).eq("id", current["id"]).execute()
        opportunity_id = current["id"]
    else:
        row = (
            client.table("opportunities")
            .insert(
                {
                    "company_id": company_id,
                    "stage": stage,
                    "estimated_value": estimated_value,
                    "notes": notes,
                    "next_action": next_action,
                }
            )
            .execute()
            .data[0]
        )
        opportunity_id = row["id"]

    client.table("companies").update({"status": _COMPANY_STATUS_FOR_STAGE[stage]}).eq("id", company_id).execute()

    return {"opportunity_id": opportunity_id, "stage": stage, "company_status": _COMPANY_STATUS_FOR_STAGE[stage]}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m python.opportunities.manager <company_id> <stage> [notes]")
        sys.exit(1)
    notes = sys.argv[3] if len(sys.argv) > 3 else None
    print(create_or_advance(sys.argv[1], sys.argv[2], notes=notes))
