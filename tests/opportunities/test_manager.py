import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python.opportunities.manager import VALID_STAGES, OpportunityError  # noqa: E402


def test_valid_stages_order():
    assert VALID_STAGES == ["MEETING", "PROPOSAL", "WON", "LOST"]


def test_invalid_stage_is_an_error_class():
    assert issubclass(OpportunityError, ValueError)
