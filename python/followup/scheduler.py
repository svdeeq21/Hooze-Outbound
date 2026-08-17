"""
python/followup/scheduler.py — WF-11 Follow-up Scheduler

Implements docs/11-follow-up.md §2 exactly: runs daily (n8n Schedule
Trigger), finds `outreach` rows due for a follow-up, and either escalates
to DEAD (max attempts reached) or drafts the next follow-up via the
personalization engine — landing in PENDING_REVIEW just like an initial
message (docs/11 §4: "follow-ups are approved too, not auto-sent").

The cadence (Day 3 / Day 7 / Day 14, docs/11 §1) is intentionally the only
hardcoded schedule in the system — a campaign row COULD override it later
(docs/11 §1 "may override... in its campaigns row config") but Campaign 001
uses the default, so no per-campaign override lookup is implemented yet;
`CADENCE_DAYS` is the single place to change if/when that's needed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

MAX_FOLLOW_UPS = 3
# index 0 = interval from initial send to follow-up 1, etc. (docs/11 §1)
CADENCE_DAYS = [3, 4, 7]  # Day3, Day7 (3+4), Day14 (7+7) -> cumulative 3,7,14


@dataclass
class FollowUpDecision:
    action: str  # "SKIP_HAS_RESPONSE" | "MARK_DEAD" | "GENERATE_FOLLOWUP"
    reason: str


def decide(outreach: dict[str, Any], has_response: bool) -> FollowUpDecision:
    """Pure decision logic per docs/11-follow-up.md §2 — no DB/AI calls, so
    this is directly unit-testable (see tests/followup/test_scheduler.py)."""
    if has_response:
        return FollowUpDecision("SKIP_HAS_RESPONSE", "A responses row already exists for this outreach_id")

    if outreach.get("follow_up_number", 0) >= MAX_FOLLOW_UPS:
        return FollowUpDecision("MARK_DEAD", f"Max follow-up attempts ({MAX_FOLLOW_UPS}) reached with no response")

    return FollowUpDecision("GENERATE_FOLLOWUP", "Due for next follow-up in cadence")


def next_follow_up_at(follow_up_number: int, now: datetime | None = None) -> datetime:
    """follow_up_number is the number AFTER incrementing (i.e. the follow-up
    about to be sent). Returns when the ONE AFTER THAT should go out."""
    now = now or datetime.now(timezone.utc)
    if follow_up_number >= len(CADENCE_DAYS):
        # Past the schedule — shouldn't be reached because MAX_FOLLOW_UPS
        # stops generation first, but fail safe rather than crash.
        return now + timedelta(days=CADENCE_DAYS[-1])
    return now + timedelta(days=CADENCE_DAYS[follow_up_number])


# ---------------------------------------------------------------------------
# I/O wrapper (WF-11 entry point) — processes ALL due rows in one run.
# ---------------------------------------------------------------------------
def wf11_run_daily() -> dict[str, Any]:
    from python.config import get_client
    from python.personalization.generator import build_input_object, generate_messages
    from python.personalization.validator import validate_message
    from python.ai_client import AIError

    client = get_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    due = (
        client.table("outreach")
        .select("*")
        .eq("status", "ACTIVE")
        .lte("next_follow_up_at", now_iso)
        .execute()
        .data
    )

    results = []
    for outreach in due:
        response_exists = bool(
            client.table("responses").select("id").eq("outreach_id", outreach["id"]).execute().data
        )
        decision = decide(outreach, response_exists)

        if decision.action == "SKIP_HAS_RESPONSE":
            results.append({"outreach_id": outreach["id"], "action": decision.action})
            continue

        if decision.action == "MARK_DEAD":
            client.table("outreach").update({"status": "DEAD", "next_follow_up_at": None}).eq("id", outreach["id"]).execute()

            # "companies.status = DEAD (only if no other active
            # campaign/opportunity exists for this company)" — docs/11 §2
            other_active = (
                client.table("outreach")
                .select("id")
                .eq("company_id", outreach["company_id"])
                .neq("id", outreach["id"])
                .in_("status", ["SENT", "ACTIVE", "PENDING_REVIEW", "APPROVED"])
                .execute()
                .data
            )
            other_opportunities = (
                client.table("opportunities")
                .select("id")
                .eq("company_id", outreach["company_id"])
                .execute()
                .data
            )
            if not other_active and not other_opportunities:
                client.table("companies").update({"status": "DEAD"}).eq("id", outreach["company_id"]).execute()

            results.append({"outreach_id": outreach["id"], "action": decision.action})
            continue

        # GENERATE_FOLLOWUP
        company = client.table("companies").select("*").eq("id", outreach["company_id"]).single().execute().data
        campaign = client.table("campaigns").select("*").eq("id", outreach["campaign_id"]).single().execute().data
        evidence = client.table("research_evidence").select("*").eq("company_id", outreach["company_id"]).execute().data
        research_rows = (
            client.table("research")
            .select("*")
            .eq("company_id", outreach["company_id"])
            .order("researched_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        observed_problem = research_rows[0].get("observed_problem") if research_rows else None
        contact = (
            client.table("contacts").select("*").eq("id", outreach["contact_id"]).single().execute().data
            if outreach.get("contact_id")
            else None
        )

        input_object = build_input_object(company, campaign, evidence, observed_problem, contact, variant_count=1)
        input_object["is_follow_up"] = True
        input_object["follow_up_number"] = outreach["follow_up_number"] + 1
        input_object["previous_message"] = outreach.get("message")

        try:
            variants = generate_messages(input_object)
        except AIError as exc:
            client.table("error_log").insert(
                {
                    "workflow": "WF-11-follow-up-scheduler",
                    "company_id": outreach["company_id"],
                    "error_message": f"Follow-up generation failed: {exc}",
                    "payload": {"outreach_id": outreach["id"]},
                }
            ).execute()
            results.append({"outreach_id": outreach["id"], "action": "GENERATE_FOLLOWUP_FAILED"})
            continue

        variant = variants[0]
        new_follow_up_number = outreach["follow_up_number"] + 1
        validation = validate_message(
            message=variant.get("message", ""),
            channel=outreach["channel"],
            evidence=input_object["evidence"],
            campaign_cta=campaign.get("cta", ""),
            subject=variant.get("subject"),
        )

        new_row = (
            client.table("outreach")
            .insert(
                {
                    "company_id": outreach["company_id"],
                    "contact_id": outreach.get("contact_id"),
                    "campaign_id": outreach["campaign_id"],
                    "channel": outreach["channel"],
                    "message": variant.get("message", ""),
                    "status": "PENDING_REVIEW",
                    "follow_up_number": new_follow_up_number,
                }
            )
            .execute()
            .data[0]
        )

        # Original row's own next_follow_up_at is cleared — the NEW row
        # carries the schedule for its own eventual next step once approved
        # and sent (that transition is WF-10's job, not this scheduler's).
        client.table("outreach").update({"next_follow_up_at": None}).eq("id", outreach["id"]).execute()

        results.append(
            {
                "outreach_id": outreach["id"],
                "action": decision.action,
                "new_outreach_id": new_row["id"],
                "validation_passed": validation.passed,
                "warnings": validation.warnings,
            }
        )

    return {"processed": len(results), "results": results}


if __name__ == "__main__":
    print(wf11_run_daily())
