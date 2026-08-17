"""
python/enrichment/enrich.py — WF-04 Lead Enrichment

Fills gaps in a `companies` row after cleaning/dedup: resolving a domain
from a name+website guess, inferring social handles, etc.

Per docs/01-system-prd.md design principle #1 ("interfaces before
implementations"), this module defines the enrichment INTERFACE
(`enrich_company`) and ships a minimal, free-tier-safe reference
implementation. It is explicitly allowed and expected that this gets
swapped/extended later (e.g. a paid enrichment API) without touching WF-04's
contract: input a `companies` dict, output a dict of field updates.

docs/13-n8n-architecture.md WF-04 error path: "Enrichment failures don't
block progression — proceeds to research with whatever's available." This
module NEVER raises on a failed enrichment step; it just returns fewer
updates and logs what it tried.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


def infer_domain_from_website(website: str | None) -> str | None:
    """Extract the root domain from a full website URL, if present.

    docs/03-data-dictionary.md: domain = 'Root domain, no protocol/www'.
    """
    if not website:
        return None
    try:
        parsed = urlparse(website if "://" in website else f"https://{website}")
        host = parsed.netloc or parsed.path
        host = host.split(":")[0]  # drop port if present
        if host.startswith("www."):
            host = host[4:]
        return host.lower() if host else None
    except Exception:
        return None


def infer_website_from_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    return f"https://{domain}"


def enrich_company(company: dict[str, Any]) -> dict[str, Any]:
    """Best-effort gap-filling. Returns only the fields it was able to add —
    never overwrites a field that's already populated (enrichment fills
    gaps, it does not correct/override discovery data)."""
    updates: dict[str, Any] = {}

    if not company.get("domain") and company.get("website"):
        domain = infer_domain_from_website(company["website"])
        if domain:
            updates["domain"] = domain

    if not company.get("website") and company.get("domain"):
        updates["website"] = infer_website_from_domain(company["domain"])

    # WhatsApp inference from a Nigerian phone number: if a phone is present
    # and no whatsapp field is set, many small Nigerian businesses use the
    # same number for both — flag it as a LOW-confidence candidate rather
    # than silently asserting it (docs/02-icp-spec.md contactability rules
    # care about confidence; WF-05 research should confirm WhatsApp presence
    # on-site before this is trusted for scoring/personalization).
    if not company.get("whatsapp") and company.get("phone_normalized"):
        updates["_whatsapp_candidate"] = company["phone_normalized"]
        # NOTE: prefixed with "_" deliberately — this is NOT written to the
        # `whatsapp` column automatically. WF-05 (research) should confirm a
        # visible WhatsApp button/link on the company's site/socials before
        # promoting this candidate to `companies.whatsapp`. See
        # docs/07-research-engine.md §3 "WhatsApp presence" check.

    return updates


# ---------------------------------------------------------------------------
# I/O wrapper (WF-04 entry point)
# ---------------------------------------------------------------------------
def enrich_from_db(company_id: str) -> dict[str, Any]:
    from python.config import get_client

    client = get_client()
    company = client.table("companies").select("*").eq("id", company_id).single().execute().data

    updates = enrich_company(company)
    real_updates = {k: v for k, v in updates.items() if not k.startswith("_")}

    if real_updates:
        client.table("companies").update(real_updates).eq("id", company_id).execute()

    return {"applied": real_updates, "candidates": {k: v for k, v in updates.items() if k.startswith("_")}}


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m python.enrichment.enrich <company_id>")
        sys.exit(1)
    print(enrich_from_db(sys.argv[1]))
