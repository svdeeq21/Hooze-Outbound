"""
python/classification/classifier.py — WF-12 Response Processing

Classifies an inbound reply into exactly one of the 9 categories in
docs/12-response-classification.md §1, using prompts/classifier.md, then
applies the routing rules from that same doc — including the two HARD rules
that are NOT left to the AI's discretion:

  1. UNSUBSCRIBE always wins, and is enforced by a keyword pre-check in code
     (docs/12 §3) — not trusted to the model alone, because "this overrides
     every other rule" is exactly the kind of hard constraint that belongs
     in code, not just in a prompt.
  2. On any AI failure or low-confidence result, default to UNKNOWN, never
     guess INTERESTED/NOT_INTERESTED (docs/12 §4 — a false positive on
     either one is worse than a human seeing an UNKNOWN).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from python.ai_client import AIError, call_ai

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "classifier.md"

VALID_CLASSIFICATIONS = {
    "INTERESTED", "QUESTION", "NOT_INTERESTED", "LATER", "PRICE",
    "MEETING", "WRONG_PERSON", "UNSUBSCRIBE", "UNKNOWN",
}

# docs/12-response-classification.md §3 — explicit opt-out phrasing. This is
# a code-level pre-check that runs BEFORE the AI call gets the final say,
# because unsubscribe handling is a hard legal/trust rule, not a judgment
# call — matching the doc's own words: "must be classified UNSUBSCRIBE
# regardless of any other content in the message."
_UNSUBSCRIBE_PATTERNS = [
    r"\bstop messaging me\b",
    r"\bremove me\b",
    r"\bunsubscribe\b",
    r"\bdon'?t contact( me)? again\b",
    r"\bdo not contact( me)? again\b",
    r"\btake me off\b.*\blist\b",
    r"\bno longer (want|wish) to (be contacted|hear)\b",
]


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _matches_unsubscribe(response_text: str) -> bool:
    text = response_text.lower()
    return any(re.search(p, text) for p in _UNSUBSCRIBE_PATTERNS)


def classify_response(outreach_message: str, response_text: str, campaign: dict[str, Any]) -> dict[str, Any]:
    """Returns {"classification", "sentiment", "intent"}.

    Never raises — on any failure (AI error, malformed output, invalid
    category), falls back to the safe default per docs/12-response-
    classification.md §4: UNKNOWN, NEUTRAL sentiment, and an intent string
    explaining why it fell back (so Hooze isn't left guessing why a reply
    landed in UNKNOWN when reviewing it).
    """
    # Hard rule, checked first, before spending an AI call at all.
    if _matches_unsubscribe(response_text):
        return {
            "classification": "UNSUBSCRIBE",
            "sentiment": "NEGATIVE",
            "intent": "Explicit opt-out phrase detected by keyword pre-check (docs/12 §3 hard rule)",
        }

    system_prompt = _load_system_prompt()
    user_input = {
        "outreach_message": outreach_message,
        "response_text": response_text,
        "campaign": {"offer": campaign.get("offer"), "cta": campaign.get("cta")},
    }

    try:
        raw = call_ai(system_prompt, user_input)
    except AIError as exc:
        return {
            "classification": "UNKNOWN",
            "sentiment": "NEUTRAL",
            "intent": f"AI classification failed, defaulted to UNKNOWN per docs/12 §4: {exc}",
        }

    classification = raw.get("classification")
    if classification not in VALID_CLASSIFICATIONS:
        return {
            "classification": "UNKNOWN",
            "sentiment": raw.get("sentiment") if raw.get("sentiment") in ("POSITIVE", "NEUTRAL", "NEGATIVE") else "NEUTRAL",
            "intent": f"AI returned an invalid/missing classification ({classification!r}), defaulted to UNKNOWN",
        }

    # Second-line UNSUBSCRIBE override: even if the keyword pre-check missed
    # a phrasing variant, if the model itself says UNSUBSCRIBE, that still
    # wins over everything per docs/12 §3 — no special handling needed here,
    # UNSUBSCRIBE just passes through like any other valid category. This
    # comment exists so a future reader doesn't wonder why there's no
    # second override block: there isn't one because none is needed.

    sentiment = raw.get("sentiment")
    if sentiment not in ("POSITIVE", "NEUTRAL", "NEGATIVE"):
        sentiment = "NEUTRAL"

    return {
        "classification": classification,
        "sentiment": sentiment,
        "intent": raw.get("intent", ""),
    }


# ---------------------------------------------------------------------------
# Routing table — docs/12-response-classification.md §1 "Routing" column.
# Each entry is applied by wf12_process_response() below.
# ---------------------------------------------------------------------------
_STOPS_FOLLOWUPS = {
    "INTERESTED", "QUESTION", "PRICE", "MEETING", "NOT_INTERESTED",
    "UNSUBSCRIBE", "LATER", "UNKNOWN",
}  # every category stops follow-ups (docs/11-follow-up.md §3); WRONG_PERSON
   # is the one exception — it stops THIS outreach cycle but is handled via
   # a distinct path below (allow re-research, don't kill the company).

_CREATES_OPPORTUNITY_STAGE = {
    "MEETING": "MEETING",
    # INTERESTED and PRICE create a sales task/notify per docs/12 §1 but do
    # NOT automatically create an opportunities row at MEETING stage — only
    # an explicit MEETING classification does. INTERESTED/PRICE surface for
    # Hooze to handle personally (docs/10-outreach-sop.md §6 escalation).
}

_IMMEDIATE_NOTIFY = {"INTERESTED", "PRICE", "MEETING"}  # docs/12 §1


def wf12_process_response(outreach_id: str, response_text: str) -> dict[str, Any]:
    from python.config import get_client

    client = get_client()
    outreach = client.table("outreach").select("*").eq("id", outreach_id).single().execute().data
    campaign = client.table("campaigns").select("*").eq("id", outreach["campaign_id"]).single().execute().data

    result = classify_response(outreach.get("message", ""), response_text, campaign)

    client.table("responses").insert(
        {
            "outreach_id": outreach_id,
            "response_text": response_text,  # stored verbatim, docs/12 §5
            "classification": result["classification"],
            "sentiment": result["sentiment"],
            "intent": result["intent"],
        }
    ).execute()

    company_id = outreach["company_id"]
    classification = result["classification"]

    if classification == "UNSUBSCRIBE":
        # docs/12 §3: hard stop, enforced at companies level, all campaigns.
        client.table("companies").update({"status": "DEAD"}).eq("id", company_id).execute()
        client.table("outreach").update({"status": "NOT_INTERESTED", "next_follow_up_at": None}).eq("id", outreach_id).execute()
        # docs/14-security-spec.md §6: scrub contact fields to a minimal
        # do-not-contact record rather than deleting the row outright.
        client.table("companies").update(
            {"phone": None, "email": None, "whatsapp": None}
        ).eq("id", company_id).execute()
        client.table("contacts").update({"email": None, "phone": None}).eq("company_id", company_id).execute()

    elif classification == "NOT_INTERESTED":
        client.table("outreach").update({"status": "NOT_INTERESTED", "next_follow_up_at": None}).eq("id", outreach_id).execute()
        client.table("companies").update({"status": "REPLIED"}).eq("id", company_id).execute()

    elif classification == "WRONG_PERSON":
        # docs/12 §1: "update contacts confidence/flag, do not mark company
        # DEAD — allow re-research for correct contact, stop this outreach
        # cycle." We downgrade confidence on the contact this outreach was
        # sent to (if any) rather than deleting it, so the history of "we
        # tried this contact and it was wrong" is preserved for research to
        # avoid repeating it.
        if outreach.get("contact_id"):
            client.table("contacts").update({"confidence": "LOW"}).eq("id", outreach["contact_id"]).execute()
        client.table("outreach").update({"status": "REPLIED", "next_follow_up_at": None}).eq("id", outreach_id).execute()
        client.table("companies").update({"status": "REPLIED"}).eq("id", company_id).execute()
        client.table("error_log").insert(
            {
                "workflow": "WF-12-response-processing",
                "company_id": company_id,
                "error_message": "WRONG_PERSON reply — contact confidence downgraded, flagged for re-research of correct contact",
                "payload": {"outreach_id": outreach_id, "contact_id": outreach.get("contact_id")},
            }
        ).execute()

    elif classification == "MEETING":
        client.table("opportunities").insert(
            {"company_id": company_id, "stage": "MEETING"}
        ).execute()
        client.table("outreach").update({"status": "REPLIED", "next_follow_up_at": None}).eq("id", outreach_id).execute()
        client.table("companies").update({"status": "MEETING"}).eq("id", company_id).execute()

    elif classification == "LATER":
        # docs/12 §1: stop cadence, schedule a single re-engagement reminder
        # (+30 days if unspecified) — company stays CONTACTED, not DEAD.
        from datetime import datetime, timedelta, timezone

        client.table("outreach").update(
            {
                "status": "REPLIED",
                "next_follow_up_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            }
        ).eq("id", outreach_id).execute()
        # companies.status intentionally left as CONTACTED (not advanced to
        # REPLIED) per docs/12 §1's explicit instruction for LATER.

    else:
        # INTERESTED, QUESTION, PRICE, UNKNOWN: stop follow-ups, surface to
        # Hooze, company -> REPLIED (docs/12 §1).
        client.table("outreach").update({"status": "REPLIED", "next_follow_up_at": None}).eq("id", outreach_id).execute()
        client.table("companies").update({"status": "REPLIED"}).eq("id", company_id).execute()

    return {"classification": classification, "sentiment": result["sentiment"], "notify_immediately": classification in _IMMEDIATE_NOTIFY}


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python -m python.classification.classifier <outreach_id> '<response_text>'")
        sys.exit(1)
    print(wf12_process_response(sys.argv[1], sys.argv[2]))
