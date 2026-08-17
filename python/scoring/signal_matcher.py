"""
python/scoring/signal_matcher.py

Per docs/03-data-dictionary.md, `research.pain_signals` and
`research.buying_signals` have Source = "scoring" (not "research engine") —
i.e. the research engine (WF-05) gathers raw evidence, and the SCORING step
(WF-06) is what matches that evidence against the known pain/buying signal
catalogue (docs/02-icp-spec.md §3/§4) to produce the signal-key arrays that
python/scoring/engine.py then counts.

This module is that matcher. It is deliberately simple keyword matching, not
an AI call — matches the "deterministic, auditable" principle of the whole
scoring engine (docs/06-scoring-engine.md §1). It is intentionally
conservative (few keywords, precise) because a false-positive signal match
inflates a score the way an unevidenced claim would, which docs/06 §2.2/§2.3
explicitly guards against.

Called by python/scoring/engine.py's score_from_db() before score_company(),
so by the time score_company() runs, research['pain_signals'] and
research['buying_signals'] are already populated from evidence — exactly as
docs/03-data-dictionary.md describes the derivation.
"""
from __future__ import annotations

from typing import Any

# Keyword -> signal key. Matching is case-insensitive substring matching
# against each research_evidence row's `claim` text. One evidence row can
# match more than one signal if its text is genuinely broad, but in practice
# each row should be specific enough to match at most one (docs/07-research-
# engine.md §4: "one specific, falsifiable observation").
_PAIN_KEYWORDS: dict[str, str] = {
    "whatsapp_primary_manual": "whatsapp",
    "no_automated_qualification": "no visible automated qualification",
    "no_booking_flow": "no booking",
    "high_listing_volume_vs_team_size": "listings",
    "public_complaints_slow_response": "complaint",
    "no_crm_evidence": "no booking/crm",
}

_BUYING_KEYWORDS: dict[str, str] = {
    "hiring_customer_service": "job post",
    "increased_marketing_activity": "boosted post",
    "multiple_branches": "branch",
    "recent_redesign_or_relaunch": "redesign",
}


def _match_signals(evidence: list[dict[str, Any]], keyword_map: dict[str, str], known: set[str]) -> list[str]:
    matched: set[str] = set()
    for row in evidence:
        claim = (row.get("claim") or "").lower()
        for signal_key, keyword in keyword_map.items():
            if signal_key not in known:
                continue
            if keyword in claim:
                matched.add(signal_key)
    return sorted(matched)


def match_pain_signals(evidence: list[dict[str, Any]]) -> list[str]:
    from python.scoring.engine import KNOWN_PAIN_SIGNALS

    return _match_signals(evidence, _PAIN_KEYWORDS, KNOWN_PAIN_SIGNALS)


def match_buying_signals(evidence: list[dict[str, Any]]) -> list[str]:
    from python.scoring.engine import KNOWN_BUYING_SIGNALS

    return _match_signals(evidence, _BUYING_KEYWORDS, KNOWN_BUYING_SIGNALS)
