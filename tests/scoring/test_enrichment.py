"""
tests/scoring/test_enrichment.py

NOTE: filed under tests/scoring/ purely for path-convenience (shares the
sys.path bootstrap); it tests python/enrichment/, not python/scoring/.
Covers WF-02 (normalize) and WF-03 (dedup) pure logic.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402

from python.enrichment.normalize import (  # noqa: E402
    NormalizationError,
    normalize_company,
    normalize_email,
    normalize_name,
    normalize_phone,
)
from python.enrichment.dedup import DedupOutcome, find_matches  # noqa: E402
from python.enrichment.enrich import infer_domain_from_website  # noqa: E402


def test_normalize_name_strips_punctuation_and_case():
    assert normalize_name("Prime Estate, Ltd.") == "prime estate ltd"
    assert normalize_name("  Multiple   Spaces  ") == "multiple spaces"


def test_normalize_phone_local_nigerian_format():
    assert normalize_phone("08012345678") == "+2348012345678"


def test_normalize_phone_already_e164():
    assert normalize_phone("+2348012345678") == "+2348012345678"


def test_normalize_phone_empty():
    assert normalize_phone(None) is None
    assert normalize_phone("") is None


def test_normalize_email_valid():
    assert normalize_email("Sunday@Example.COM") == "sunday@example.com"


def test_normalize_email_invalid_returns_none():
    assert normalize_email("not-an-email") is None


def test_normalize_company_requires_name():
    with pytest.raises(NormalizationError):
        normalize_company({"name": ""})


def test_normalize_company_full_row():
    updates = normalize_company(
        {"name": "Prime Estate", "phone": "08012345678", "email": "Info@Prime.com"}
    )
    assert updates["normalized_name"] == "prime estate"
    assert updates["phone_normalized"] == "+2348012345678"
    assert updates["email_normalized"] == "info@prime.com"


def test_dedup_unique_when_no_matches():
    candidate = {"normalized_name": "new co", "location": "Abuja"}
    result = find_matches(candidate, [])
    assert result.outcome == DedupOutcome.UNIQUE


def test_dedup_exact_match_on_name_and_location():
    candidate = {"normalized_name": "prime estate", "location": "Abuja"}
    existing = [{"id": "abc", "normalized_name": "prime estate", "location": "Abuja"}]
    result = find_matches(candidate, existing)
    assert result.outcome == DedupOutcome.DUPLICATE_EXACT
    assert result.matched_company_id == "abc"


def test_dedup_exact_match_on_phone():
    candidate = {"phone_normalized": "+2348012345678"}
    existing = [{"id": "xyz", "phone_normalized": "+2348012345678"}]
    result = find_matches(candidate, existing)
    assert result.outcome == DedupOutcome.DUPLICATE_EXACT
    assert result.matched_company_id == "xyz"


def test_dedup_ambiguous_when_multiple_different_rows_match():
    candidate = {
        "normalized_name": "prime estate",
        "location": "Abuja",
        "phone_normalized": "+2348099999999",
    }
    existing = [
        {"id": "row1", "normalized_name": "prime estate", "location": "Abuja"},
        {"id": "row2", "phone_normalized": "+2348099999999"},
    ]
    result = find_matches(candidate, existing)
    assert result.outcome == DedupOutcome.AMBIGUOUS
    assert result.matched_company_id is None


def test_infer_domain_from_website():
    assert infer_domain_from_website("https://www.example.com/listings") == "example.com"
    assert infer_domain_from_website("example.com") == "example.com"
    assert infer_domain_from_website(None) is None
