"""
python/personalization/generator.py — WF-08 Message Generation

Builds the structured input object exactly matching docs/08-personalization-
spec.md §2, calls the AI with prompts/personalizer.md, and runs every draft
through python/personalization/validator.py before it reaches the review
queue — per docs/13-n8n-architecture.md WF-08: "Validation failures flagged
in the row (warning field) but still routed to review."

This module NEVER free-texts a prompt to the model (docs/08 §2: "never
given a free-text 'write a personalized message' prompt") — the only inputs
are the structured object below, built entirely from `evidence[]` rows that
already passed the provenance check in WF-05/python/research/interface.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from python.ai_client import AIError, call_ai
from python.personalization.validator import validate_message

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "personalizer.md"


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text()


def build_input_object(
    company: dict[str, Any],
    campaign: dict[str, Any],
    evidence: list[dict[str, Any]],
    observed_problem: str | None,
    contact: dict[str, Any] | None,
    variant_count: int = 1,
) -> dict[str, Any]:
    """Matches docs/08-personalization-spec.md §2 input contract exactly."""
    usable_evidence = [e for e in evidence if e.get("confidence") in ("HIGH", "MEDIUM")]
    return {
        "company": company.get("name"),
        "industry": company.get("industry"),
        "location": company.get("location"),
        "campaign": {
            "offer": campaign.get("offer"),
            "pain": campaign.get("pain"),
            "proof": campaign.get("proof"),
            "cta": campaign.get("cta"),
        },
        "evidence": [
            {"claim": e["claim"], "source_url": e["source_url"], "confidence": e["confidence"]}
            for e in usable_evidence
        ],
        "observed_problem": observed_problem,
        "contact": (
            {
                "name": contact.get("name"),
                "title": contact.get("job_title"),
                "confidence": contact.get("confidence"),
            }
            if contact
            else None
        ),
        "variant_count": variant_count,
    }


def generate_messages(input_object: dict[str, Any]) -> list[dict[str, Any]]:
    """Calls the AI, returns the raw `variants` list from prompts/
    personalizer.md's output schema. Raises AIError on total failure —
    caller (wf08_generate below) decides fallback behavior."""
    system_prompt = _load_system_prompt()
    raw = call_ai(system_prompt, input_object)
    variants = raw.get("variants")
    if not variants:
        raise AIError(f"AI response had no 'variants' array: {raw}")
    return variants


# ---------------------------------------------------------------------------
# I/O wrapper (WF-08 entry point)
# ---------------------------------------------------------------------------
def wf08_generate(company_id: str, campaign_id: str) -> dict[str, Any]:
    from python.config import get_client

    client = get_client()
    company = client.table("companies").select("*").eq("id", company_id).single().execute().data
    campaign = client.table("campaigns").select("*").eq("id", campaign_id).single().execute().data
    evidence = client.table("research_evidence").select("*").eq("company_id", company_id).execute().data
    research_rows = (
        client.table("research")
        .select("*")
        .eq("company_id", company_id)
        .order("researched_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    observed_problem = research_rows[0].get("observed_problem") if research_rows else None
    contacts = client.table("contacts").select("*").eq("company_id", company_id).execute().data
    contact = max(contacts, key=lambda c: {"HIGH": 2, "MEDIUM": 1, "LOW": 0}.get(c.get("confidence"), -1)) if contacts else None

    if not evidence:
        # docs/06-scoring-engine.md §2.5: personalization_score = 0 with zero
        # evidence, and per docs/05-lead-lifecycle.md the company "cannot
        # enter PERSONALIZED state... personalization engine has nothing to
        # ground a message in." We enforce that here, not just in scoring.
        client.table("error_log").insert(
            {
                "workflow": "WF-08-message-generation",
                "company_id": company_id,
                "error_message": "No research_evidence rows — cannot personalize without grounding evidence",
                "payload": {},
            }
        ).execute()
        return {"status": "skipped", "reason": "no evidence to ground message in"}

    input_object = build_input_object(
        company=company,
        campaign=campaign,
        evidence=evidence,
        observed_problem=observed_problem,
        contact=contact,
        variant_count=2,  # docs/08-personalization-spec.md §7: up to 2 variants
    )

    try:
        variants = generate_messages(input_object)
    except AIError as exc:
        client.table("error_log").insert(
            {
                "workflow": "WF-08-message-generation",
                "company_id": company_id,
                "error_message": f"AI generation failed: {exc}",
                "payload": {},
            }
        ).execute()
        return {"status": "error", "reason": str(exc)}

    created_rows = []
    for variant in variants:
        channel = variant.get("channel", "WHATSAPP")
        message = variant.get("message", "")
        subject = variant.get("subject")

        validation = validate_message(
            message=message,
            channel=channel,
            evidence=input_object["evidence"],
            campaign_cta=campaign.get("cta", ""),
            subject=subject,
        )

        full_message = f"Subject: {subject}\n\n{message}" if channel == "EMAIL" and subject else message

        row = (
            client.table("outreach")
            .insert(
                {
                    "company_id": company_id,
                    "contact_id": contact.get("id") if contact else None,
                    "campaign_id": campaign_id,
                    "channel": channel,
                    "message": full_message,
                    "status": "PENDING_REVIEW",
                    "follow_up_number": 0,
                }
            )
            .execute()
            .data[0]
        )
        created_rows.append({"outreach_id": row["id"], "channel": channel, "validation_passed": validation.passed, "warnings": validation.warnings})

        if not validation.passed:
            client.table("error_log").insert(
                {
                    "workflow": "WF-08-message-generation",
                    "company_id": company_id,
                    "error_message": "Message validation warnings (routed to review anyway per docs/08 §6)",
                    "payload": {"outreach_id": row["id"], "warnings": validation.warnings},
                }
            ).execute()

    client.table("companies").update({"status": "REVIEW"}).eq("id", company_id).execute()

    return {"status": "REVIEW", "variants_created": created_rows}


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python -m python.personalization.generator <company_id> <campaign_id>")
        sys.exit(1)
    print(wf08_generate(sys.argv[1], sys.argv[2]))
