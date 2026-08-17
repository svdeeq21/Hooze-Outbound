"""
tests/research/test_evidence_rules.py

Enforces docs/07-research-engine.md §4: "no fact enters `research` without
a corresponding row in `research_evidence` carrying a source URL." Tests the
code-level guardrails in python/research/interface.py and
python/research/ai_extractor.py, independent of any real AI call.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python.research.interface import Evidence, ResearchOutput  # noqa: E402
from python.research.ai_extractor import _parse_and_validate  # noqa: E402


def test_evidence_requires_source_url():
    with pytest.raises(ValueError):
        Evidence(claim="WhatsApp button visible", source_url="", confidence="HIGH")


def test_evidence_requires_claim():
    with pytest.raises(ValueError):
        Evidence(claim="", source_url="https://example.com", confidence="HIGH")


def test_evidence_rejects_bad_confidence():
    with pytest.raises(ValueError):
        Evidence(claim="x", source_url="https://example.com", confidence="SUPER_HIGH")


def test_research_output_research_score_tiers():
    def make(n, confidence="HIGH"):
        return ResearchOutput(
            website_summary=None,
            services=[],
            target_market=None,
            whatsapp_present=None,
            booking_process=None,
            lead_capture_process=None,
            proof=None,
            observed_problem=None,
            evidence=[Evidence(f"claim {i}", "https://example.com", confidence) for i in range(n)],
        )

    assert make(0).research_score() == 0
    assert make(2).research_score() == 35
    assert make(4).research_score() == 65
    assert make(6).research_score() == 90
    assert make(6, confidence="LOW").research_score() == 0  # LOW doesn't count as usable


def test_ai_extractor_drops_evidence_missing_source_instead_of_crashing():
    raw = {
        "website_summary": "A real estate site",
        "services": ["Sales"],
        "target_market": "Home buyers",
        "whatsapp_present": True,
        "booking_process": None,
        "lead_capture_process": None,
        "proof": None,
        "observed_problem": "May need help qualifying leads",
        "evidence": [
            {"claim": "WhatsApp button visible", "source_url": "https://example.com", "confidence": "HIGH"},
            {"claim": "No source claim", "source_url": "", "confidence": "HIGH"},  # invalid, must be dropped
            {"claim": "Bad confidence", "source_url": "https://example.com", "confidence": "VERY_SURE"},  # invalid
        ],
    }
    output = _parse_and_validate(raw)
    assert len(output.evidence) == 1
    assert output.evidence[0].claim == "WhatsApp button visible"


def test_ai_extractor_handles_zero_evidence():
    raw = {
        "website_summary": None,
        "services": [],
        "target_market": None,
        "whatsapp_present": None,
        "booking_process": None,
        "lead_capture_process": None,
        "proof": None,
        "observed_problem": None,
        "evidence": [],
    }
    output = _parse_and_validate(raw)
    assert output.evidence == []
    assert output.research_score() == 0
