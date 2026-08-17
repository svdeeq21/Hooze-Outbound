"""
tests/scoring/test_engine.py

Unit tests for python/scoring/engine.py against docs/06-scoring-engine.md.
No database required — pure function tests, matching the "small, testable"
principle in docs/01-system-prd.md §9.5.

Run: pytest tests/scoring/test_engine.py -v
(from the repo root, with the repo root on PYTHONPATH — see tests/README or
run `python -m pytest` from repo root)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python.scoring.engine import score_company  # noqa: E402

ACTIVE_CAMPAIGNS = [
    {
        "name": "CAMPAIGN 001 — Abuja Real Estate WhatsApp Automation",
        "industry": "Real Estate",
        "target_location": "Abuja",
        "status": "ACTIVE",
    }
]


def make_prime_estate():
    company = {
        "id": "company-a",
        "name": "Prime Estate",
        "industry": "Real Estate",
        "location": "Abuja",
        "whatsapp": "+2348000000000",
        "website": "https://example-prime-estate.com",
        "status": "RESEARCHED",
    }
    contacts = [
        {"company_id": "company-a", "confidence": "HIGH"},
    ]
    research = {
        "pain_signals": [
            "whatsapp_primary_manual",
            "no_automated_qualification",
            "high_listing_volume_vs_team_size",
        ],
        "buying_signals": ["hiring_customer_service", "multiple_branches"],
    }
    evidence = [
        {"claim": "WhatsApp button visible", "confidence": "HIGH"},
        {"claim": "40+ listings", "confidence": "HIGH"},
        {"claim": "No automated qualification observed", "confidence": "MEDIUM"},
        {"claim": "Two branches listed", "confidence": "HIGH"},
        {"claim": "Hiring ad for WhatsApp inquiries officer", "confidence": "HIGH"},
        {"claim": "Named MD found", "confidence": "HIGH"},
    ]
    return company, contacts, research, evidence


def test_high_scoring_lead_reaches_tier_a():
    company, contacts, research, evidence = make_prime_estate()
    result = score_company(company, contacts, research, evidence, ACTIVE_CAMPAIGNS)

    assert result.icp_score == 25  # industry+location+presence+whatsapp all match
    assert result.pain_score == 15  # 3 evidenced pain signals x 5
    assert result.buying_signal_score == 10  # 2 evidenced buying signals x 5
    assert result.contactability_score == 15  # HIGH confidence contact
    assert result.personalization_score == 15  # 6 usable evidence rows (>=5)
    assert result.total_score == 80
    assert result.priority == "A"
    assert "Tier A" in result.reason


def test_low_scoring_lead_is_dont_contact():
    company = {
        "id": "company-b",
        "name": "Random Realty Page",
        "industry": "Real Estate",
        "location": "Abuja",
        "whatsapp": "+2348011111111",
        "status": "RESEARCHED",
    }
    contacts = [{"company_id": "company-b", "confidence": "LOW"}]
    research = {"pain_signals": ["no_crm_evidence"], "buying_signals": []}
    evidence = [{"claim": "No booking tool visible", "confidence": "LOW"}]

    result = score_company(company, contacts, research, evidence, ACTIVE_CAMPAIGNS)

    # ICP: industry+location match (+15), no website/linkedin/instagram (+0
    # presence), whatsapp present (+5) => 20
    assert result.icp_score == 20
    assert result.pain_score == 5  # 1 evidenced pain signal
    assert result.buying_signal_score == 0
    assert result.contactability_score == 5  # LOW confidence
    assert result.personalization_score == 0  # only LOW-confidence evidence, none usable
    assert result.total_score == 30
    assert result.priority == "DONT_CONTACT"


def test_disqualifier_forces_zero_and_dont_contact():
    company = {
        "id": "company-c",
        "name": "No Contact Channel Inc",
        "industry": "Real Estate",
        "location": "Abuja",
        "status": "RESEARCHED",
        # no whatsapp, no email, no phone at all
    }
    result = score_company(company, [], {}, [], ACTIVE_CAMPAIGNS)

    assert result.total_score == 0
    assert result.priority == "DONT_CONTACT"
    assert "DISQUALIFIED" in result.reason


def test_unevidenced_pain_signal_does_not_count():
    """docs/06-scoring-engine.md §2.2: 'an unsupported pain signal does not
    count'. If research.pain_signals is populated but there is zero
    research_evidence at all, no pain points should be awarded."""
    company = {
        "id": "company-d",
        "industry": "Real Estate",
        "location": "Abuja",
        "whatsapp": "+234800",
        "status": "RESEARCHED",
    }
    research = {"pain_signals": ["whatsapp_primary_manual", "no_crm_evidence"], "buying_signals": []}
    result = score_company(company, [], research, [], ACTIVE_CAMPAIGNS)

    assert result.pain_score == 0


def test_personalization_score_tiers():
    from python.scoring.engine import _score_personalization

    assert _score_personalization([]) == 0
    assert _score_personalization([{"confidence": "HIGH"}]) == 5
    assert _score_personalization([{"confidence": "HIGH"}] * 3) == 10
    assert _score_personalization([{"confidence": "MEDIUM"}] * 5) == 15
    # LOW-confidence rows never count toward personalization potential
    assert _score_personalization([{"confidence": "LOW"}] * 10) == 0


def test_contactability_uses_best_available_contact():
    from python.scoring.engine import _score_contactability

    contacts = [{"confidence": "LOW"}, {"confidence": "HIGH"}, {"confidence": "MEDIUM"}]
    assert _score_contactability(contacts) == 15
    assert _score_contactability([]) == 0


def test_pain_and_buying_signals_are_capped():
    """docs/06-scoring-engine.md §2.2/§2.3: pain capped at 5 matches (25pts),
    buying capped at 4 matches (20pts) even if more signal keys are present."""
    company = {
        "id": "company-e",
        "industry": "Real Estate",
        "location": "Abuja",
        "whatsapp": "+234800",
        "status": "RESEARCHED",
    }
    research = {
        "pain_signals": list(__import__("python.scoring.engine", fromlist=["KNOWN_PAIN_SIGNALS"]).KNOWN_PAIN_SIGNALS),
        "buying_signals": list(__import__("python.scoring.engine", fromlist=["KNOWN_BUYING_SIGNALS"]).KNOWN_BUYING_SIGNALS),
    }
    evidence = [{"confidence": "HIGH"}]
    result = score_company(company, [], research, evidence, ACTIVE_CAMPAIGNS)
    assert result.pain_score == 25  # 5 known pain signals, all counted, capped at 25
    assert result.buying_signal_score == 20  # 4 known buying signals, capped at 20
