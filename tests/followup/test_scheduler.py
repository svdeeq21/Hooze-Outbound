import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python.followup.scheduler import decide, next_follow_up_at  # noqa: E402


def test_skip_when_response_exists():
    decision = decide({"follow_up_number": 0}, has_response=True)
    assert decision.action == "SKIP_HAS_RESPONSE"


def test_mark_dead_at_max_attempts():
    decision = decide({"follow_up_number": 3}, has_response=False)
    assert decision.action == "MARK_DEAD"


def test_generate_followup_below_max():
    decision = decide({"follow_up_number": 1}, has_response=False)
    assert decision.action == "GENERATE_FOLLOWUP"


def test_cadence_matches_doc_3_7_14():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # follow_up_number=0 -> first follow-up scheduled 3 days out
    assert next_follow_up_at(0, now).day == 4  # Jan 1 + 3 = Jan 4
    # follow_up_number=1 -> second follow-up scheduled 4 more days out (day 7 total)
    assert (next_follow_up_at(1, now) - now).days == 4
    # follow_up_number=2 -> third follow-up scheduled 7 more days out (day 14 total)
    assert (next_follow_up_at(2, now) - now).days == 7
