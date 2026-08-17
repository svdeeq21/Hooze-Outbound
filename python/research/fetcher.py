"""
python/research/fetcher.py — reference implementation of ResearchProvider

Satisfies python/research/interface.py using a direct HTTP fetch of public
pages (website + any social URLs on record), per docs/07-research-engine.md
§2 ("Any implementation... satisfying this interface is acceptable and
swappable"). This is the free-tier-compliant default: no paid scraping APIs
(docs/01-system-prd.md §7).

This module ONLY fetches and lightly parses raw page content — it does NOT
decide what's evidence-worthy. That judgment call is python/research/
ai_extractor.py's job (via prompts/researcher.md), because deciding "is this
a falsifiable claim" is exactly the kind of task an LLM does better than
regex, and docs/07-research-engine.md §4 requires that judgment to happen
somewhere auditable, not buried in scraping heuristics.

Rate/quota discipline (docs/07-research-engine.md §7): capped at
config.research_fetch_cap() page fetches per company (default 6), and each
request sets a descriptive User-Agent and respects robots.txt.
"""
from __future__ import annotations

import urllib.robotparser as robotparser
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "HoozeOutboundResearchBot/1.0 (+https://hooze.example; contact: research@hooze.example)"

# The handful of extra pages worth checking beyond the homepage, in priority
# order — matches docs/07-research-engine.md §3 categories (services/listings,
# contact/WhatsApp, about/team, reviews). Stops once the fetch cap is hit.
CANDIDATE_PATHS = ["/", "/about", "/contact", "/listings", "/properties", "/team", "/services"]


@dataclass
class FetchedPage:
    url: str
    content: str  # cleaned, visible text only — no markup, no scripts/styles


def _robots_allows(base_url: str, path: str) -> bool:
    try:
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(USER_AGENT, urljoin(base_url, path))
    except Exception:
        # If robots.txt is unreachable/unparseable, default to allow for a
        # single public page fetch (fail-open on THIS check only — the
        # fetch itself still has its own timeout/error handling below).
        return True


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return " ".join(text.split())[:8000]  # cap page text size fed to the AI extractor


def fetch_pages(website: str, max_fetches: int) -> list[FetchedPage]:
    """Fetches up to `max_fetches` public pages from `website`, respecting
    robots.txt. Never raises on an individual page failure — a dead link on
    a small business site is expected, not exceptional; it just means fewer
    evidence candidates, which docs/13-n8n-architecture.md WF-05 error path
    already handles ('Zero evidence found -> status stays RESEARCHED but
    flagged low-quality')."""
    if not website:
        return []

    base = website if website.startswith("http") else f"https://{website}"
    pages: list[FetchedPage] = []

    with httpx.Client(timeout=10.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for path in CANDIDATE_PATHS:
            if len(pages) >= max_fetches:
                break
            if not _robots_allows(base, path):
                continue
            url = urljoin(base, path)
            try:
                resp = client.get(url)
                if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                    pages.append(FetchedPage(url=str(resp.url), content=_clean_text(resp.text)))
            except (httpx.HTTPError, httpx.TimeoutException):
                continue  # skip unreachable page, try the next candidate path

    return pages
