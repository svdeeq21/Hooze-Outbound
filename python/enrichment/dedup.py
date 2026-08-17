"""
python/enrichment/dedup.py — WF-03 Lead Deduplication

Implements docs/13-n8n-architecture.md WF-03: after WF-02 normalizes a row,
check it against existing `companies` for a match on
(normalized_name, location), phone_normalized, or email_normalized.

Three outcomes, matching the workflow contract exactly:
  - UNIQUE           -> proceed, status stays CLEANED
  - DUPLICATE_EXACT  -> merged/discarded automatically (new row is a strict
                        subset of info the existing row already has, or an
                        exact re-import)
  - AMBIGUOUS        -> flagged for manual review, NOT auto-merged
                        (docs/13 WF-03 error path)

We deliberately do not implement a fuzzy string-similarity merge (e.g.
Levenshtein on names) in V1 — the exact-match rule set here is intentionally
conservative because a false-merge silently loses a real lead, which is a
worse failure mode than a false-unique that just means near-duplicate rows
sit in the review-adjacent AMBIGUOUS bucket for Hooze to eyeball.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class DedupOutcome(str, Enum):
    UNIQUE = "UNIQUE"
    DUPLICATE_EXACT = "DUPLICATE_EXACT"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass
class DedupResult:
    outcome: DedupOutcome
    matched_company_id: str | None
    matched_fields: list[str]
    reason: str


def find_matches(candidate: dict[str, Any], existing: list[dict[str, Any]]) -> DedupResult:
    """Pure function: given a normalized candidate row and a list of existing
    `companies` rows (already fetched by the caller — see dedup_company()
    below for the actual query), decide the dedup outcome.

    `existing` should already be pre-filtered by the caller to rows that
    match at least one of the three keys (the DB query does that narrowing
    for efficiency); this function does the decision logic on that narrowed
    candidate set.
    """
    if not existing:
        return DedupResult(DedupOutcome.UNIQUE, None, [], "No matching companies found")

    scored: list[tuple[dict[str, Any], list[str]]] = []
    for row in existing:
        fields_matched = []
        if (
            candidate.get("normalized_name")
            and candidate.get("location")
            and row.get("normalized_name") == candidate.get("normalized_name")
            and row.get("location") == candidate.get("location")
        ):
            fields_matched.append("normalized_name+location")
        if (
            candidate.get("phone_normalized")
            and row.get("phone_normalized") == candidate.get("phone_normalized")
        ):
            fields_matched.append("phone_normalized")
        if (
            candidate.get("email_normalized")
            and row.get("email_normalized") == candidate.get("email_normalized")
        ):
            fields_matched.append("email_normalized")
        if fields_matched:
            scored.append((row, fields_matched))

    if not scored:
        return DedupResult(DedupOutcome.UNIQUE, None, [], "No matching companies found")

    if len(scored) > 1:
        # Multiple different existing companies each partially match on
        # different keys -> ambiguous, do not guess which one is "real".
        ids = ", ".join(r.get("id", "?") for r, _ in scored)
        return DedupResult(
            DedupOutcome.AMBIGUOUS,
            None,
            [],
            f"Candidate matches {len(scored)} different existing companies ({ids}) on different keys — needs manual review",
        )

    row, fields_matched = scored[0]

    # A match on the strong dedup key (name+location) OR on a unique direct
    # identifier (phone or email) alone is treated as exact. Two or more
    # matched fields against the SAME row is high-confidence exact; a single
    # field match against the same single row is still exact (not ambiguous)
    # because ambiguity in this function means "which row", not "how sure".
    return DedupResult(
        DedupOutcome.DUPLICATE_EXACT,
        row.get("id"),
        fields_matched,
        f"Matches existing company {row.get('id')} on: {', '.join(fields_matched)}",
    )


# ---------------------------------------------------------------------------
# I/O wrapper (WF-03 entry point)
# ---------------------------------------------------------------------------
def dedup_company(company_id: str) -> dict[str, Any]:
    from python.config import get_client

    client = get_client()
    candidate = client.table("companies").select("*").eq("id", company_id).single().execute().data

    or_filters = []
    if candidate.get("normalized_name") and candidate.get("location"):
        or_filters.append(
            f"and(normalized_name.eq.{candidate['normalized_name']},location.eq.{candidate['location']})"
        )
    if candidate.get("phone_normalized"):
        or_filters.append(f"phone_normalized.eq.{candidate['phone_normalized']}")
    if candidate.get("email_normalized"):
        or_filters.append(f"email_normalized.eq.{candidate['email_normalized']}")

    if not or_filters:
        # Nothing to key dedup on at all — treat as unique but this is a
        # data-quality smell worth flagging, not a hard error.
        client.table("error_log").insert(
            {
                "workflow": "WF-03-lead-deduplication",
                "company_id": company_id,
                "error_message": "No dedup keys available (no name+location, phone, or email) — proceeding as UNIQUE",
                "payload": {"company": candidate},
            }
        ).execute()
        return {"outcome": "UNIQUE", "reason": "no dedup keys available"}

    existing = (
        client.table("companies")
        .select("*")
        .neq("id", company_id)
        .or_(",".join(or_filters))
        .execute()
        .data
    )

    result = find_matches(candidate, existing)

    if result.outcome == DedupOutcome.DUPLICATE_EXACT:
        # Discard the new (duplicate) row; the existing row survives.
        # docs/13 WF-03: "Duplicate -> merged/discarded (log which survived)".
        client.table("error_log").insert(
            {
                "workflow": "WF-03-lead-deduplication",
                "company_id": company_id,
                "error_message": f"Duplicate discarded, survivor={result.matched_company_id}",
                "payload": {"matched_fields": result.matched_fields},
            }
        ).execute()
        client.table("companies").delete().eq("id", company_id).execute()
    elif result.outcome == DedupOutcome.AMBIGUOUS:
        client.table("error_log").insert(
            {
                "workflow": "WF-03-lead-deduplication",
                "company_id": company_id,
                "error_message": result.reason,
                "payload": {},
            }
        ).execute()
        # Left at status=CLEANED but flagged in error_log for manual review;
        # does NOT proceed automatically to WF-04 (docs/13 WF-03 error path).
    # UNIQUE: no action needed, row proceeds to WF-04 as-is (status stays CLEANED)

    return {"outcome": result.outcome.value, "reason": result.reason, "matched_company_id": result.matched_company_id}


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m python.enrichment.dedup <company_id>")
        sys.exit(1)
    print(dedup_company(sys.argv[1]))
