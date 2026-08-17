import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python.analytics.reports import compute_funnel_metrics, compute_positive_rate, slice_by  # noqa: E402


def make_companies():
    return [
        {"id": "1", "status": "CLEANED", "source": "google_maps"},
        {"id": "2", "status": "QUALIFIED", "source": "google_maps"},
        {"id": "3", "status": "CONTACTED", "source": "linkedin"},
        {"id": "4", "status": "REPLIED", "source": "linkedin"},
        {"id": "5", "status": "WON", "source": "linkedin"},
        {"id": "6", "status": "DEAD", "source": "manual"},  # excluded from funnel reach counts
    ]


def test_funnel_reached_counts_are_cumulative():
    metrics = compute_funnel_metrics(make_companies(), outreach=[])
    counts = metrics["funnel_counts"]
    # CLEANED: everyone at CLEANED or later (excluding DEAD/off-funnel) = 5
    assert counts["CLEANED"] == 5
    # WON: only the one company currently at WON
    assert counts["WON"] == 1
    # QUALIFIED: companies 2,3,4,5 (QUALIFIED or later) = 4
    assert counts["QUALIFIED"] == 4


def test_qualification_rate():
    metrics = compute_funnel_metrics(make_companies(), outreach=[])
    # qualified=4, cleaned=5 -> 0.8
    assert metrics["qualification_rate"] == 0.8


def test_safe_div_handles_zero_denominator():
    metrics = compute_funnel_metrics([], outreach=[])
    assert metrics["qualification_rate"] is None
    assert metrics["reply_rate"] is None


def test_positive_rate():
    responses = [
        {"classification": "INTERESTED"},
        {"classification": "NOT_INTERESTED"},
        {"classification": "MEETING"},
        {"classification": "QUESTION"},
    ]
    assert compute_positive_rate(responses) == 0.5


def test_positive_rate_empty():
    assert compute_positive_rate([]) is None


def test_slice_by_source():
    groups = slice_by(make_companies(), "source")
    assert len(groups["google_maps"]) == 2
    assert len(groups["linkedin"]) == 3
