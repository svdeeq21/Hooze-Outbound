"""
python/research/interface.py — the research engine INTERFACE

Per docs/07-research-engine.md §2 and docs/01-system-prd.md design principle
#1 ("interfaces before implementations"): this file defines the *contract*
every research implementation must satisfy. `fetcher.py` is one reference
implementation (direct HTTP fetch of public pages); it can be swapped for a
permitted API or manual research entry without touching WF-05, WF-06, or
python/scoring/engine.py, as long as it returns a ResearchOutput.

INPUT:  company_id, website (optional), social handles (optional)
OUTPUT: ResearchOutput — see docs/07-research-engine.md §2 for the field-
        level spec this mirrors 1:1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Evidence:
    claim: str
    source_url: str
    confidence: str  # HIGH | MEDIUM | LOW

    def __post_init__(self):
        if self.confidence not in ("HIGH", "MEDIUM", "LOW"):
            raise ValueError(f"Evidence.confidence must be HIGH/MEDIUM/LOW, got {self.confidence!r}")
        if not self.claim or not self.claim.strip():
            raise ValueError("Evidence.claim is required (docs/07-research-engine.md §4)")
        if not self.source_url or not self.source_url.strip():
            raise ValueError("Evidence.source_url is required — no claim without a source (docs/07 §4)")


@dataclass
class ResearchOutput:
    website_summary: str | None
    services: list[str]
    target_market: str | None
    whatsapp_present: bool | None
    booking_process: str | None
    lead_capture_process: str | None
    proof: str | None
    observed_problem: str | None
    evidence: list[Evidence] = field(default_factory=list)
    pain_signals: list[str] = field(default_factory=list)
    buying_signals: list[str] = field(default_factory=list)

    def research_score(self) -> int:
        """docs/07-research-engine.md §6 — research completeness score.

        Approximated here by evidence volume/confidence, since 'categories'
        (website presence, listings, booking flow, etc. — docs/07 §3) map
        loosely to distinct claim topics rather than a formal field on
        Evidence; a HIGH/MEDIUM-evidence-row count is a reasonable, auditable
        proxy and keeps this function deterministic like the scoring engine.
        """
        usable = [e for e in self.evidence if e.confidence in ("HIGH", "MEDIUM")]
        n = len(usable)
        if n >= 5:
            return 90
        if n >= 3:
            return 65
        if n >= 1:
            return 35
        return 0

    def validate_provenance(self) -> None:
        """Enforces docs/07-research-engine.md §4/§5: every evidence row must
        have a source; observed_problem (a hypothesis) is allowed to exist
        with zero evidence rows, but if it exists it should be phrased as a
        hypothesis, not asserted — that phrasing check is a soft heuristic,
        not something this validator can prove, so we only assert the hard
        rule: no evidence row lacks a source_url (Evidence.__post_init__
        already guarantees this per-row; this function is the whole-object
        version of the same check, for defense in depth)."""
        for e in self.evidence:
            if not e.source_url:
                raise ValueError(f"Evidence for claim {e.claim!r} has no source_url — provenance rule violated")


class ResearchProvider(Protocol):
    """Any research implementation (HTTP fetch, API, manual entry) must
    expose this single method to be pluggable into WF-05."""

    def research(
        self,
        company_id: str,
        website: str | None,
        social_handles: dict[str, str] | None,
    ) -> ResearchOutput:
        ...
