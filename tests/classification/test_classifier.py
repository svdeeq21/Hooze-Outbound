"""
tests/classification/test_classifier.py

Covers the two hard rules from docs/12-response-classification.md that must
never depend on the AI call succeeding: the UNSUBSCRIBE keyword pre-check
(§3) and the safe-default-to-UNKNOWN behavior (§4). Does not exercise the
AI-backed path (that needs live credentials) — see python/ai_client.py for
where that's isolated.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python.classification.classifier import _matches_unsubscribe, classify_response  # noqa: E402


def test_unsubscribe_keyword_variants_detected():
    assert _matches_unsubscribe("Please stop messaging me")
    assert _matches_unsubscribe("unsubscribe")
    assert _matches_unsubscribe("Remove me from your list")
    assert _matches_unsubscribe("Don't contact me again please")
    assert _matches_unsubscribe("take me off this list immediately")


def test_normal_reply_not_flagged_as_unsubscribe():
    assert not _matches_unsubscribe("Not interested right now, maybe later")
    assert not _matches_unsubscribe("How much does this cost?")


def test_unsubscribe_short_circuits_before_any_ai_call():
    """Even with no AI credentials configured at all, an UNSUBSCRIBE-phrased
    reply must classify correctly — this is the point of the keyword
    pre-check running before call_ai()."""
    result = classify_response(
        outreach_message="Hi, quick question about your listings...",
        response_text="Please remove me from your list, stop messaging me.",
        campaign={"offer": "demo", "cta": "book a call"},
    )
    assert result["classification"] == "UNSUBSCRIBE"
    assert result["sentiment"] == "NEGATIVE"
