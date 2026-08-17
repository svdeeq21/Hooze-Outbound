"""
Shared configuration and Supabase client factory for the whole python/ layer.

Every module (enrichment, research, scoring, personalization, classification)
imports `get_client()` from here rather than constructing its own Supabase
client, so credential handling lives in exactly one place — per
docs/14-security-spec.md §1 ("no credential ever appears in a committed
n8n workflow JSON, Python file, or doc").

Environment variables (set these in n8n's credential store / environment,
or in a local .env for dev — see .env.example at the repo root):

  SUPABASE_URL              - your Supabase project URL
  SUPABASE_SERVICE_ROLE_KEY - service role key (server-side only, bypasses RLS)
  AI_PROVIDER                - "gemini" or "groq" (matches the existing
                                Hooze stack's Gemini-primary/Groq-fallback
                                pattern, docs/14-security-spec.md §4)
  GEMINI_API_KEY
  GROQ_API_KEY
  RESEARCH_MAX_FETCHES_PER_COMPANY - hard ceiling on page fetches per
                                company (docs/07-research-engine.md §7),
                                defaults to 6 if unset.
"""
from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv is a dev convenience only; production (n8n) sets real
    # environment variables directly, so its absence is not an error.
    pass


class ConfigError(RuntimeError):
    """Raised when a required environment variable is missing at call time.

    Deliberately NOT raised at import time — importing config.py should
    never crash a workflow; only the specific call that needs a missing
    credential should fail, so unrelated code paths (e.g. running the
    scoring engine's pure functions in a unit test with no Supabase creds
    set at all) keep working.
    """


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(
            f"Missing required environment variable: {name}. "
            f"See python/config.py module docstring for the full list."
        )
    return value


def get_client():
    """Returns a Supabase client authenticated with the SERVICE ROLE key.

    Per docs/14-security-spec.md §2, the service role key is what every
    n8n-triggered Python call uses; it bypasses Row Level Security by design
    because n8n itself is the trusted backend in V1 (single operator).
    """
    from supabase import create_client

    url = _require("SUPABASE_URL")
    key = _require("SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def research_fetch_cap() -> int:
    """Per-company page-fetch ceiling for the research engine (docs/07 §7)."""
    return int(os.environ.get("RESEARCH_MAX_FETCHES_PER_COMPANY", "6"))


def ai_provider() -> str:
    """Which AI provider to call first. 'gemini' (primary) or 'groq' (fallback),
    matching the existing Hooze stack pattern (docs/14-security-spec.md §4)."""
    return os.environ.get("AI_PROVIDER", "gemini").lower()
