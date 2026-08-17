"""
Reject/approve/mark_sent in python/review/actions.py are thin DB-touching
wrappers with real logic guarded by status-precondition checks. Without a
live Supabase instance we can only test the parts that don't need the
network: the exception types and the reason-required guard on reject().
Full behavioral coverage of these three functions happens via the
database/seed.sql fixtures in a real/staging Supabase project — see
README.md "Testing without live Supabase".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402

from python.review.actions import ReviewActionError, reject  # noqa: E402


def test_reject_requires_non_empty_reason():
    with pytest.raises(ReviewActionError):
        reject("some-outreach-id", "")
    with pytest.raises(ReviewActionError):
        reject("some-outreach-id", "   ")
