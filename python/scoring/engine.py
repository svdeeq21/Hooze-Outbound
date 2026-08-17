"""
python/scoring/engine.py — WF-06 ICP Scoring

Implements docs/06-scoring-engine.md EXACTLY. This is the one place in the
whole system that assigns a score, and it is deliberately NOT an AI call —
see prompts/scorer.md and docs/06-scoring-engine.md §1 for why: every point
awarded must trace to a rule in this file so `lead_scores.reason` can always
explain itself in plain language to Hooze.

Public entry point: score_company(company, contacts, research, evidence)
  -> ScoreResult

This module has NO Supabase/network dependency by design — it is pure
functions over plain dicts/lists, so it can be unit tested (see
tests/scoring/test_engine.py) without a database, and so WF-06 in n8n can
call it via a simple Code node or a thin CLI wrapper (score_from_db below)
that only handles I/O, not scoring logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Reference data — kept in code, not hardcoded magic strings scattered around,
# so a change to the ICP/pain/buying signal catalogue (docs/02-icp-spec.md)
# only has to happen in one place. Values are the canonical signal keys this
# engine expects to find in research.pain_signals / research.buying_signals
# (research is expected to have already matched raw observations to these
# keys — see docs/03-data-dictionary.md `research.pain_signals` derivation).
# ---------------------------------------------------------------------------

# docs/02-icp-spec.md §3 — five pain signals, worth up to 5 matches (25 pts)
KNOWN_PAIN_SIGNALS = {
    "whatsapp_primary_manual",       # WhatsApp primary but slow/manual responses
    "no_automated_qualification",    # inquiries go straight to a human, no structure
    "high_listing_volume_vs_team_size",
    "public_complaints_slow_response",
    "no_crm_evidence",
}

# docs/02-icp-spec.md §4 — four buying signals, worth up to 4 matches (20 pts)
KNOWN_BUYING_SIGNALS = {
    "hiring_customer_service",       # hiring ad for customer service/sales/whatsapp handler
    "increased_marketing_activity",
    "multiple_branches",
    "recent_redesign_or_relaunch",
}

CONFIDENCE_RANK = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}


@dataclass
class ScoreBreakdown:
    icp_score: int
    pain_score: int
    buying_signal_score: int
    contactability_score: int
    personalization_score: int
    disqualified: bool
    disqualify_reason: str | None
    pain_matches: list[str] = field(default_factory=list)
    buying_matches: list[str] = field(default_factory=list)

    @property
    def total_score(self) -> int:
        if self.disqualified:
            return 0
        return (
            self.icp_score
            + self.pain_score
            + self.buying_signal_score
            + self.contactability_score
            + self.personalization_score
        )


@dataclass
class ScoreResult:
    icp_score: int
    pain_score: int
    buying_signal_score: int
    contactability_score: int
    personalization_score: int
    total_score: int
    priority: str  # A / B / C / DONT_CONTACT
    reason: str
    scored_at: str


# ---------------------------------------------------------------------------
# §2.1 ICP Fit (0-25)
# ---------------------------------------------------------------------------
def _score_icp_fit(
    company: dict[str, Any],
    active_campaigns: Iterable[dict[str, Any]],
) -> tuple[int, bool, str | None, list[str]]:
    """Returns (icp_score, disqualified, disqualify_reason, notes).

    docs/06-scoring-engine.md §2.1: industry match (+10), location match (+5),
    online presence (+5), WhatsApp/contact channel (+5). A disqualifier
    (docs/02-icp-spec.md §2.2) forces score to 0 and priority DONT_CONTACT,
    skipping every other component.
    """
    notes: list[str] = []

    # --- Disqualifiers first (docs/02-icp-spec.md §2.2) ---
    if not any([company.get("whatsapp"), company.get("email"), company.get("phone")]):
        return 0, True, "No public contact channel of any kind (disqualifier #1)", notes
    if company.get("status") == "DEAD":
        return 0, True, "Company already marked DEAD (disqualifier: defunct/opted out/existing client)", notes

    score = 0
    active = list(active_campaigns)

    industry_match = any(
        c.get("industry", "").strip().lower() == company.get("industry", "").strip().lower()
        for c in active
    )
    if industry_match:
        score += 10
        notes.append("industry matches an active campaign vertical (+10)")

    location_match = any(
        c.get("target_location", "").strip().lower() == company.get("location", "").strip().lower()
        for c in active
    )
    if location_match:
        score += 5
        notes.append("location matches active campaign geography (+5)")

    has_online_presence = bool(company.get("website") or company.get("instagram") or company.get("linkedin"))
    if has_online_presence:
        score += 5
        notes.append("online presence requirement met (+5)")

    has_contact_channel = bool(company.get("whatsapp"))
    if has_contact_channel:
        score += 5
        notes.append("WhatsApp contact channel visible/inferable (+5)")

    return score, False, None, notes


# ---------------------------------------------------------------------------
# §2.2 Pain Signal (0-25) and §2.3 Buying Signal (0-20)
# ---------------------------------------------------------------------------
def _evidenced_signals(
    signals: Iterable[str],
    known_signals: set[str],
    evidence: list[dict[str, Any]],
) -> list[str]:
    """A matched signal only counts if there is >=1 research_evidence row
    for the company (docs/06-scoring-engine.md §2.2/§2.3: "an unsupported
    pain/buying signal does not count").

    We don't try to fuzzy-map which specific evidence row backs which
    specific signal key here (that mapping is the research engine's job —
    it writes research.pain_signals/buying_signals only when it has already
    grounded them in evidence, per docs/03-data-dictionary.md). This
    function's job is the second-line guardrail: if a company somehow has
    signal keys set but ZERO evidence rows at all, none of the signals count,
    full stop — that catches a broken/partial research write.
    """
    if not evidence:
        return []
    return [s for s in signals if s in known_signals]


def _score_pain(research: dict[str, Any], evidence: list[dict[str, Any]]) -> tuple[int, list[str]]:
    matches = _evidenced_signals(research.get("pain_signals") or [], KNOWN_PAIN_SIGNALS, evidence)
    matches = matches[:5]  # cap at 5 signals per docs/06 §2.2
    return len(matches) * 5, matches


def _score_buying(research: dict[str, Any], evidence: list[dict[str, Any]]) -> tuple[int, list[str]]:
    matches = _evidenced_signals(research.get("buying_signals") or [], KNOWN_BUYING_SIGNALS, evidence)
    matches = matches[:4]  # cap at 4 signals per docs/06 §2.3
    return len(matches) * 5, matches


# ---------------------------------------------------------------------------
# §2.4 Contactability (0-15)
# ---------------------------------------------------------------------------
def _score_contactability(contacts: list[dict[str, Any]]) -> int:
    if not contacts:
        return 0
    # If multiple contacts exist, score the best one (highest confidence).
    best = max(contacts, key=lambda c: CONFIDENCE_RANK.get(c.get("confidence"), -1))
    return {"HIGH": 15, "MEDIUM": 10, "LOW": 5}.get(best.get("confidence"), 0)


# ---------------------------------------------------------------------------
# §2.5 Personalization Potential (0-15)
# ---------------------------------------------------------------------------
def _score_personalization(evidence: list[dict[str, Any]]) -> int:
    usable = [e for e in evidence if e.get("confidence") in ("HIGH", "MEDIUM")]
    n = len(usable)
    if n >= 5:
        return 15
    if n >= 3:
        return 10
    if n >= 1:
        return 5
    return 0


# ---------------------------------------------------------------------------
# §3 Tiering
# ---------------------------------------------------------------------------
def _tier(total_score: int, disqualified: bool) -> str:
    if disqualified:
        return "DONT_CONTACT"
    if total_score >= 80:
        return "A"
    if total_score >= 65:
        return "B"
    if total_score >= 50:
        return "C"
    return "DONT_CONTACT"


def _build_reason(breakdown: ScoreBreakdown, priority: str) -> str:
    if breakdown.disqualified:
        return f"DISQUALIFIED: {breakdown.disqualify_reason}. Score forced to 0."
    parts = [
        f"ICP {breakdown.icp_score}/25",
        f"Pain {breakdown.pain_score}/25"
        + (f" ({', '.join(breakdown.pain_matches)})" if breakdown.pain_matches else " (no evidenced pain signals)"),
        f"Buying {breakdown.buying_signal_score}/20"
        + (f" ({', '.join(breakdown.buying_matches)})" if breakdown.buying_matches else " (no evidenced buying signals)"),
        f"Contactability {breakdown.contactability_score}/15",
        f"Personalization {breakdown.personalization_score}/15",
    ]
    return f"Total {breakdown.total_score}/100 -> Tier {priority}. " + "; ".join(parts) + "."


def score_company(
    company: dict[str, Any],
    contacts: list[dict[str, Any]],
    research: dict[str, Any] | None,
    evidence: list[dict[str, Any]],
    active_campaigns: list[dict[str, Any]],
) -> ScoreResult:
    """Score a single company per docs/06-scoring-engine.md.

    Args mirror the tables named in docs/13-n8n-architecture.md WF-06 input:
    `companies`, `research`, `research_evidence`, `contacts`, plus the list
    of currently ACTIVE `campaigns` rows (needed for the ICP industry/location
    match in §2.1 — a company can only match a campaign that is ACTIVE).

    Missing inputs never crash the workflow (docs/13 WF-06 error path:
    "Missing required inputs (e.g. no contacts row) -> contactability_score
    = 0, scoring proceeds with the rest, does not fail the whole workflow").
    """
    research = research or {}
    contacts = contacts or []
    evidence = evidence or []
    active_campaigns = [c for c in active_campaigns if c.get("status") == "ACTIVE"]

    icp_score, disqualified, dq_reason, _icp_notes = _score_icp_fit(company, active_campaigns)

    if disqualified:
        breakdown = ScoreBreakdown(
            icp_score=0,
            pain_score=0,
            buying_signal_score=0,
            contactability_score=0,
            personalization_score=0,
            disqualified=True,
            disqualify_reason=dq_reason,
        )
    else:
        pain_score, pain_matches = _score_pain(research, evidence)
        buying_score, buying_matches = _score_buying(research, evidence)
        contactability_score = _score_contactability(contacts)
        personalization_score = _score_personalization(evidence)

        breakdown = ScoreBreakdown(
            icp_score=icp_score,
            pain_score=pain_score,
            buying_signal_score=buying_score,
            contactability_score=contactability_score,
            personalization_score=personalization_score,
            disqualified=False,
            disqualify_reason=None,
            pain_matches=pain_matches,
            buying_matches=buying_matches,
        )

    priority = _tier(breakdown.total_score, breakdown.disqualified)
    reason = _build_reason(breakdown, priority)

    return ScoreResult(
        icp_score=breakdown.icp_score,
        pain_score=breakdown.pain_score,
        buying_signal_score=breakdown.buying_signal_score,
        contactability_score=breakdown.contactability_score,
        personalization_score=breakdown.personalization_score,
        total_score=breakdown.total_score,
        priority=priority,
        reason=reason,
        scored_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# I/O wrapper — the ONLY function in this file that touches the database.
# Called by n8n WF-06 (either via a Code node running Python, or an HTTP/CLI
# bridge — see n8n/WF-06-icp-scoring.json for the exact call pattern used).
# ---------------------------------------------------------------------------
def score_from_db(company_id: str) -> ScoreResult:
    from python.config import get_client  # local import: keeps db-free unit tests fast

    client = get_client()

    company = client.table("companies").select("*").eq("id", company_id).single().execute().data
    contacts = client.table("contacts").select("*").eq("company_id", company_id).execute().data
    research_rows = (
        client.table("research")
        .select("*")
        .eq("company_id", company_id)
        .order("researched_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    research = research_rows[0] if research_rows else {}
    evidence = client.table("research_evidence").select("*").eq("company_id", company_id).execute().data
    campaigns = client.table("campaigns").select("*").eq("status", "ACTIVE").execute().data

    # docs/03-data-dictionary.md: research.pain_signals / buying_signals have
    # Source = "scoring" — this step (not the research engine) derives them
    # from evidence and persists them back onto the research row, so the
    # dashboard/audit trail shows WHICH signals were credited, not just the
    # resulting score. See python/scoring/signal_matcher.py.
    if research:
        from python.scoring.signal_matcher import match_buying_signals, match_pain_signals

        matched_pain = match_pain_signals(evidence)
        matched_buying = match_buying_signals(evidence)
        research["pain_signals"] = matched_pain
        research["buying_signals"] = matched_buying
        client.table("research").update(
            {"pain_signals": matched_pain, "buying_signals": matched_buying}
        ).eq("id", research["id"]).execute()

    result = score_company(company, contacts, research, evidence, campaigns)

    client.table("lead_scores").insert(
        {
            "company_id": company_id,
            "icp_score": result.icp_score,
            "pain_score": result.pain_score,
            "buying_signal_score": result.buying_signal_score,
            "contactability_score": result.contactability_score,
            "personalization_score": result.personalization_score,
            "total_score": result.total_score,
            "priority": result.priority,
            "reason": result.reason,
            "scored_at": result.scored_at,
        }
    ).execute()

    # docs/06-scoring-engine.md §3 + docs/05-lead-lifecycle.md: QUALIFIED
    # requires total_score >= 65 (tier A or B). Below that, status stays
    # RESEARCHED (visible as tier C/DONT_CONTACT in the dashboard) —
    # WF-06 never regresses status, only advances it.
    if result.total_score >= 65:
        client.table("companies").update({"status": "QUALIFIED"}).eq("id", company_id).execute()

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m python.scoring.engine <company_id>")
        sys.exit(1)
    out = score_from_db(sys.argv[1])
    print(out)
