"""
python/review/actions.py — WF-09 (Human Approval) and WF-10 (Send
Confirmation), both "dashboard-backed" per docs/13-n8n-architecture.md:
these are called directly by dashboard/index.html actions (via a thin n8n
Webhook that just forwards to these functions), implementing docs/10-
outreach-sop.md §3-4 exactly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class ReviewActionError(ValueError):
    pass


def approve(outreach_id: str, edited_message: str | None = None) -> dict[str, Any]:
    """docs/10-outreach-sop.md §3 APPROVE / EDIT step.

    If `edited_message` is provided and differs from the current message,
    the ORIGINAL is preserved in draft_history (never silently overwritten
    in logs, per §3) and outreach.message becomes the edited text.
    """
    from python.config import get_client

    client = get_client()
    outreach = client.table("outreach").select("*").eq("id", outreach_id).single().execute().data

    if outreach["status"] != "PENDING_REVIEW":
        raise ReviewActionError(
            f"Cannot approve outreach {outreach_id}: status is {outreach['status']}, expected PENDING_REVIEW"
        )

    updates: dict[str, Any] = {
        "status": "APPROVED",
        "approved_by": "hooze",
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    if edited_message and edited_message != outreach["message"]:
        updates["draft_history"] = outreach["message"]  # preserve original AI draft
        updates["message"] = edited_message

    client.table("outreach").update(updates).eq("id", outreach_id).execute()
    return {"outreach_id": outreach_id, "status": "APPROVED", "edited": bool(updates.get("draft_history"))}


def reject(outreach_id: str, reason: str) -> dict[str, Any]:
    """docs/10-outreach-sop.md §3 REJECT step. Company reverts to QUALIFIED
    (not stuck at REVIEW) so it can be re-personalized later."""
    from python.config import get_client

    if not reason or not reason.strip():
        raise ReviewActionError("A rejection reason is required (docs/10-outreach-sop.md §3)")

    client = get_client()
    outreach = client.table("outreach").select("*").eq("id", outreach_id).single().execute().data

    client.table("outreach").update(
        {"status": "REJECTED", "rejection_reason": reason}
    ).eq("id", outreach_id).execute()
    client.table("companies").update({"status": "QUALIFIED"}).eq("id", outreach["company_id"]).execute()

    return {"outreach_id": outreach_id, "status": "REJECTED"}


def mark_sent(outreach_id: str) -> dict[str, Any]:
    """docs/10-outreach-sop.md §4 sending procedure.

    Guardrail (§4 point 4 / docs/05-lead-lifecycle.md §4): a company may not
    have two concurrently ACTIVE outreach cycles. Enforced here in code, not
    just "Hooze should visually confirm" — a hard block is safer than an
    honor system for something the doc itself calls out as a rule.
    """
    from python.config import get_client
    from python.followup.scheduler import next_follow_up_at

    client = get_client()
    outreach = client.table("outreach").select("*").eq("id", outreach_id).single().execute().data

    if outreach["status"] != "APPROVED":
        raise ReviewActionError(
            f"Cannot mark outreach {outreach_id} sent: status is {outreach['status']}, expected APPROVED"
        )

    other_active = (
        client.table("outreach")
        .select("id")
        .eq("company_id", outreach["company_id"])
        .neq("id", outreach_id)
        .in_("status", ["SENT", "ACTIVE"])
        .execute()
        .data
    )
    if other_active:
        raise ReviewActionError(
            f"Company {outreach['company_id']} already has an active outreach cycle "
            f"({other_active[0]['id']}) — cannot send a second concurrent message "
            f"(docs/05-lead-lifecycle.md §4 guardrail)"
        )

    now = datetime.now(timezone.utc)
    client.table("outreach").update(
        {
            "status": "ACTIVE",
            "sent_at": now.isoformat(),
            "next_follow_up_at": next_follow_up_at(outreach["follow_up_number"], now).isoformat(),
        }
    ).eq("id", outreach_id).execute()
    client.table("companies").update({"status": "CONTACTED"}).eq("id", outreach["company_id"]).execute()

    return {"outreach_id": outreach_id, "status": "ACTIVE"}


# ---------------------------------------------------------------------------
# Read-side helpers for the dashboard (dashboard/index.html).
#
# Per docs/14-security-spec.md §1/§2/§7: "Python scripts run with the same
# service-role credential as n8n, no separate exposed API surface in V1" —
# so the dashboard does NOT hold a Supabase key of its own (anon or
# otherwise) and does NOT read the database directly. Every dashboard read
# AND write goes through an n8n webhook that calls these service-role
# functions server-side. This keeps RLS's default-deny (migration 011)
# simple and correct: nothing except n8n ever touches Supabase directly.
# ---------------------------------------------------------------------------
def list_review_queue() -> list[dict[str, Any]]:
    """docs/10-outreach-sop.md §3 step 1: 'filter to REVIEW state, sorted by
    lead_scores.priority (A before B)'. Returns everything the dashboard
    needs to render one review card per outreach row: the message, the
    company, the score breakdown/reason, and the evidence list."""
    from python.config import get_client

    client = get_client()
    outreach_rows = client.table("outreach").select("*").eq("status", "PENDING_REVIEW").execute().data

    results = []
    priority_rank = {"A": 0, "B": 1, "C": 2, "DONT_CONTACT": 3}
    for row in outreach_rows:
        company = client.table("companies").select("*").eq("id", row["company_id"]).single().execute().data
        score_rows = (
            client.table("lead_scores")
            .select("*")
            .eq("company_id", row["company_id"])
            .order("scored_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        score = score_rows[0] if score_rows else None
        evidence = client.table("research_evidence").select("*").eq("company_id", row["company_id"]).execute().data
        results.append({"outreach": row, "company": company, "score": score, "evidence": evidence})

    results.sort(key=lambda r: priority_rank.get((r["score"] or {}).get("priority"), 9))
    return results


def list_send_queue() -> list[dict[str, Any]]:
    """docs/10-outreach-sop.md §4: APPROVED rows waiting for Hooze to send
    manually via WhatsApp/Gmail and confirm with mark_sent()."""
    from python.config import get_client

    client = get_client()
    outreach_rows = client.table("outreach").select("*").eq("status", "APPROVED").execute().data
    results = []
    for row in outreach_rows:
        company = client.table("companies").select("*").eq("id", row["company_id"]).single().execute().data
        contact = (
            client.table("contacts").select("*").eq("id", row["contact_id"]).single().execute().data
            if row.get("contact_id")
            else None
        )
        results.append({"outreach": row, "company": company, "contact": contact})
    return results


def list_replied_queue() -> list[dict[str, Any]]:
    """docs/10-outreach-sop.md §7 daily checklist: 'Check REPLIED leads —
    classify/confirm classification, act on INTERESTED/MEETING/PRICE
    immediately'."""
    from python.config import get_client

    client = get_client()
    companies = client.table("companies").select("*").eq("status", "REPLIED").execute().data
    results = []
    for company in companies:
        outreach_rows = (
            client.table("outreach")
            .select("*")
            .eq("company_id", company["id"])
            .order("sent_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        outreach_row = outreach_rows[0] if outreach_rows else None
        responses = (
            client.table("responses")
            .select("*")
            .eq("outreach_id", outreach_row["id"])
            .execute()
            .data
            if outreach_row
            else []
        )
        results.append({"company": company, "outreach": outreach_row, "responses": responses})
    return results
