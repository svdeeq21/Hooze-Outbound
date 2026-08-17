"""
python/research/ai_extractor.py — WF-05 Website/Evidence Research

Turns raw fetched page content (python/research/fetcher.py) into a
provenance-checked ResearchOutput (python/research/interface.py) by calling
the AI model with the exact prompt in prompts/researcher.md.

This module enforces the evidence rule (docs/07-research-engine.md §4) in
CODE, not just in the prompt text — the prompt tells the model what to do,
this module verifies it actually did it before anything reaches the
database. An AI response that fails validation is not written; the company
is left at whatever evidence WAS already validated (possibly zero), which
per docs/13-n8n-architecture.md WF-05 error path is the correct behavior:
"Zero evidence found -> status stays RESEARCHED but flagged low-quality."
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from python.ai_client import AIError, call_ai
from python.research.interface import Evidence, ResearchOutput

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "researcher.md"


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text()


def extract_research(company_name: str, pages: list[dict[str, str]]) -> ResearchOutput:
    """pages: list of {"url": ..., "content": ...} — matches
    prompts/researcher.md's input schema exactly.

    Raises AIError if the AI call fails outright (caller decides what to do —
    see wf05_research below, which logs to error_log and leaves the company
    with zero evidence rather than crashing the workflow).
    """
    system_prompt = _load_system_prompt()
    user_input = {"company_name": company_name, "pages": pages}

    raw = call_ai(system_prompt, user_input)
    return _parse_and_validate(raw)


def _parse_and_validate(raw: dict[str, Any]) -> ResearchOutput:
    evidence_raw = raw.get("evidence") or []
    evidence: list[Evidence] = []
    dropped = 0
    for item in evidence_raw:
        try:
            evidence.append(
                Evidence(
                    claim=item.get("claim", ""),
                    source_url=item.get("source_url", ""),
                    confidence=item.get("confidence", ""),
                )
            )
        except ValueError:
            # A claim with no source, or a bad confidence value, is DROPPED,
            # not passed through — this is the code-level enforcement of
            # docs/07-research-engine.md §4 the module docstring describes.
            dropped += 1
            continue

    output = ResearchOutput(
        website_summary=raw.get("website_summary"),
        services=raw.get("services") or [],
        target_market=raw.get("target_market"),
        whatsapp_present=raw.get("whatsapp_present"),
        booking_process=raw.get("booking_process"),
        lead_capture_process=raw.get("lead_capture_process"),
        proof=raw.get("proof"),
        observed_problem=raw.get("observed_problem"),
        evidence=evidence,
    )
    output.validate_provenance()  # raises if any evidence somehow still lacks a source
    output._dropped_evidence_count = dropped  # informational, for logging only
    return output


# ---------------------------------------------------------------------------
# I/O wrapper (WF-05 entry point)
# ---------------------------------------------------------------------------
def wf05_research(company_id: str) -> dict[str, Any]:
    from python.config import get_client, research_fetch_cap
    from python.research.fetcher import fetch_pages

    client = get_client()
    company = client.table("companies").select("*").eq("id", company_id).single().execute().data

    website = company.get("website")
    fetched = fetch_pages(website, research_fetch_cap()) if website else []
    pages = [{"url": p.url, "content": p.content} for p in fetched]

    if not pages:
        client.table("error_log").insert(
            {
                "workflow": "WF-05-research",
                "company_id": company_id,
                "error_message": "No pages could be fetched (no website on record, or all fetches failed)",
                "payload": {"website": website},
            }
        ).execute()
        # Still advance to RESEARCHED per docs/13 WF-05 error path — zero
        # evidence is a valid (if low-quality) research outcome, not a
        # workflow failure. Downstream scoring will naturally score
        # personalization_score = 0 for this company (docs/06 §2.5).
        client.table("companies").update({"status": "RESEARCHED"}).eq("id", company_id).execute()
        return {"status": "RESEARCHED", "evidence_count": 0, "reason": "no pages fetched"}

    try:
        output = extract_research(company.get("name", ""), pages)
    except AIError as exc:
        client.table("error_log").insert(
            {
                "workflow": "WF-05-research",
                "company_id": company_id,
                "error_message": f"AI extraction failed: {exc}",
                "payload": {"pages_fetched": len(pages)},
            }
        ).execute()
        client.table("companies").update({"status": "RESEARCHED"}).eq("id", company_id).execute()
        return {"status": "RESEARCHED", "evidence_count": 0, "reason": "AI extraction failed"}

    research_row = (
        client.table("research")
        .insert(
            {
                "company_id": company_id,
                "website_summary": output.website_summary,
                "services": output.services,
                "target_market": output.target_market,
                "whatsapp_present": output.whatsapp_present,
                "booking_process": output.booking_process,
                "lead_capture_process": output.lead_capture_process,
                "observed_problem": output.observed_problem,
                "research_score": output.research_score(),
            }
        )
        .execute()
        .data[0]
    )

    if output.evidence:
        client.table("research_evidence").insert(
            [
                {
                    "company_id": company_id,
                    "claim": e.claim,
                    "source_url": e.source_url,
                    "confidence": e.confidence,
                }
                for e in output.evidence
            ]
        ).execute()

    # docs/07-research-engine.md §3: promote a research-confirmed WhatsApp
    # number onto companies.whatsapp only now that WF-05 has actually seen a
    # WhatsApp button/link on the site (see enrichment/enrich.py's
    # `_whatsapp_candidate` note for why this wasn't done at WF-04).
    if output.whatsapp_present and not company.get("whatsapp") and company.get("phone_normalized"):
        client.table("companies").update({"whatsapp": company["phone_normalized"]}).eq("id", company_id).execute()

    client.table("companies").update({"status": "RESEARCHED"}).eq("id", company_id).execute()

    return {
        "status": "RESEARCHED",
        "evidence_count": len(output.evidence),
        "research_score": output.research_score(),
        "research_id": research_row["id"],
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m python.research.ai_extractor <company_id>")
        sys.exit(1)
    print(wf05_research(sys.argv[1]))
