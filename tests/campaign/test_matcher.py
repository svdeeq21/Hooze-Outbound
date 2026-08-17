import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python.campaign.matcher import match_campaign  # noqa: E402


def test_matches_on_industry_and_location():
    company = {"industry": "Real Estate", "location": "Abuja"}
    campaigns = [{"id": "c1", "industry": "Real Estate", "target_location": "Abuja", "status": "ACTIVE"}]
    result = match_campaign(company, campaigns)
    assert result["id"] == "c1"


def test_no_match_returns_none():
    company = {"industry": "Clinics", "location": "Abuja"}
    campaigns = [{"id": "c1", "industry": "Real Estate", "target_location": "Abuja", "status": "ACTIVE"}]
    assert match_campaign(company, campaigns) is None


def test_paused_campaign_never_matches():
    company = {"industry": "Real Estate", "location": "Abuja"}
    campaigns = [{"id": "c1", "industry": "Real Estate", "target_location": "Abuja", "status": "PAUSED"}]
    assert match_campaign(company, campaigns) is None


def test_multiple_matches_prefers_higher_reply_rate():
    company = {"industry": "Real Estate", "location": "Abuja"}
    campaigns = [
        {"id": "old", "industry": "Real Estate", "target_location": "Abuja", "status": "ACTIVE"},
        {"id": "new", "industry": "Real Estate", "target_location": "Abuja", "status": "ACTIVE"},
    ]
    result = match_campaign(company, campaigns, reply_rates={"old": 0.4, "new": 0.1})
    assert result["id"] == "old"


def test_multiple_matches_no_data_falls_back_to_caller_order():
    company = {"industry": "Real Estate", "location": "Abuja"}
    campaigns = [
        {"id": "newest", "industry": "Real Estate", "target_location": "Abuja", "status": "ACTIVE"},
        {"id": "older", "industry": "Real Estate", "target_location": "Abuja", "status": "ACTIVE"},
    ]
    result = match_campaign(company, campaigns)
    assert result["id"] == "newest"
