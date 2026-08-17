"""
python/enrichment/normalize.py — WF-02 Lead Cleaning

Computes the three derived/normalized fields docs/03-data-dictionary.md
requires for every `companies` row before it can be deduplicated (WF-03):

  normalized_name  - lowercased, punctuation-stripped name used for dedup
  phone_normalized - digits-only version (E.164-ish) for dedup
  email_normalized - lowercased email for dedup

Pure functions, no DB/network dependency — matches the "small, testable
workflows" principle (docs/01-system-prd.md §9.5). The DB-touching wrapper
(`clean_company`) is at the bottom, same pattern as python/scoring/engine.py.
"""
from __future__ import annotations

import re
from typing import Any

# Nigeria-first phone handling: Hooze's ICP (docs/02-icp-spec.md) is Abuja/
# Lagos real estate, so local numbers commonly show up as 080..., 070..., etc.
# We normalize to E.164 (+234...) when we can confidently infer the country
# code; otherwise we just strip to digits and leave country-code inference to
# a human/researcher rather than guessing wrong (a wrong country code breaks
# WhatsApp contact silently, which is worse than leaving it ambiguous).
_NG_LOCAL_PREFIX = re.compile(r"^0(\d{10})$")


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    docs/03-data-dictionary.md: 'Lowercased, punctuation-stripped name used
    for dedup'. This is intentionally lossy (e.g. 'Prime Estate Ltd.' and
    'Prime Estate' normalize to different strings still, since we do NOT
    strip legal-entity suffixes here — doing so risks merging two distinct
    businesses that happen to share a common name root. Suffix-stripping is
    a WF-03 fuzzy-match concern, not a WF-02 normalization concern.
    """
    if not name:
        return ""
    lowered = name.strip().lower()
    stripped = re.sub(r"[^\w\s]", "", lowered)
    collapsed = re.sub(r"\s+", " ", stripped).strip()
    return collapsed


def normalize_phone(phone: str | None) -> str | None:
    """Digits-only normalization with best-effort +234 (Nigeria) inference.

    Returns None if input is empty/unusable, so callers can distinguish
    "no phone provided" from "phone provided but garbage" (the latter should
    flag the row per docs/13-n8n-architecture.md WF-02 error path: 'Rows
    failing normalization... flagged, status stays DISCOVERED').
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None

    if digits.startswith("234") and len(digits) == 13:
        return "+" + digits
    m = _NG_LOCAL_PREFIX.match(digits)
    if m:
        return "+234" + m.group(1)
    if phone.strip().startswith("+"):
        # Already had an explicit country code the user provided — trust it,
        # just strip formatting characters.
        return "+" + digits
    # Ambiguous (not clearly Nigerian-local, no + prefix given): return
    # digits-only rather than guess a country code.
    return digits


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    candidate = email.strip().lower()
    if "@" not in candidate or "." not in candidate.split("@")[-1]:
        return None  # fails docs/03-data-dictionary.md 'valid email format' validation
    return candidate


def is_valid_domain(domain: str | None) -> bool:
    if not domain:
        return False
    return bool(re.match(r"^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)+$", domain.strip().lower()))


class NormalizationError(ValueError):
    """Raised when a row cannot be normalized enough to proceed.

    Per docs/13-n8n-architecture.md WF-02 error path: such rows should stay
    at status=DISCOVERED (not advance to CLEANED) and surface in WF-15.
    """


def normalize_company(company: dict[str, Any]) -> dict[str, Any]:
    """Returns the field updates WF-02 should apply to a `companies` row.

    Raises NormalizationError if the row lacks the bare minimum to proceed
    (docs/03-data-dictionary.md: name is the only unconditionally required
    field besides system-generated ones — but a company with no name AND no
    normalized_name is unusable downstream).
    """
    name = (company.get("name") or "").strip()
    if not name:
        raise NormalizationError("companies.name is required and empty/missing")

    updates: dict[str, Any] = {
        "normalized_name": normalize_name(name),
    }

    phone = company.get("phone")
    if phone:
        norm_phone = normalize_phone(phone)
        if norm_phone is None:
            raise NormalizationError(f"phone '{phone}' could not be normalized to digits")
        updates["phone_normalized"] = norm_phone

    email = company.get("email")
    if email:
        norm_email = normalize_email(email)
        if norm_email is None:
            raise NormalizationError(f"email '{email}' is not a valid email format")
        updates["email_normalized"] = norm_email

    domain = company.get("domain")
    if domain and not is_valid_domain(domain):
        raise NormalizationError(f"domain '{domain}' is not a valid domain format")

    return updates


# ---------------------------------------------------------------------------
# I/O wrapper (WF-02 entry point)
# ---------------------------------------------------------------------------
def clean_company(company_id: str) -> dict[str, Any]:
    from python.config import get_client

    client = get_client()
    company = client.table("companies").select("*").eq("id", company_id).single().execute().data

    try:
        updates = normalize_company(company)
    except NormalizationError as exc:
        client.table("error_log").insert(
            {
                "workflow": "WF-02-lead-cleaning",
                "company_id": company_id,
                "error_message": str(exc),
                "payload": {"company": company},
            }
        ).execute()
        # status intentionally left at DISCOVERED per docs/13 WF-02 error path
        return {"status": "error", "reason": str(exc)}

    updates["status"] = "CLEANED"
    client.table("companies").update(updates).eq("id", company_id).execute()
    return {"status": "CLEANED", **updates}


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m python.enrichment.normalize <company_id>")
        sys.exit(1)
    print(clean_company(sys.argv[1]))
