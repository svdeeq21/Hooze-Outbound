import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python.scoring.signal_matcher import match_buying_signals, match_pain_signals  # noqa: E402


def test_match_pain_signals_from_seed_style_evidence():
    evidence = [
        {"claim": "WhatsApp contact button visible on every listing page"},
        {"claim": "40+ active property listings across the site"},
        {"claim": "No visible automated qualification or booking flow — inquiries go to a phone number"},
    ]
    matched = match_pain_signals(evidence)
    assert "whatsapp_primary_manual" in matched
    assert "no_automated_qualification" in matched
    assert "high_listing_volume_vs_team_size" in matched


def test_match_buying_signals_from_seed_style_evidence():
    evidence = [
        {"claim": "Two branch locations listed (Wuse II, Gwarinpa)"},
        {"claim": 'LinkedIn job post for "Customer Service / WhatsApp Inquiries Officer" posted within last 30 days'},
    ]
    matched = match_buying_signals(evidence)
    assert "multiple_branches" in matched
    assert "hiring_customer_service" in matched


def test_no_false_positives_on_irrelevant_evidence():
    evidence = [{"claim": "Site uses a blue color scheme"}]
    assert match_pain_signals(evidence) == []
    assert match_buying_signals(evidence) == []
