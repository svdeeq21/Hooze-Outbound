"""
python/discovery/ — intentionally near-empty in V1.

docs/13-n8n-architecture.md WF-01 (Lead Import) reads raw rows from a
Google Sheets staging tab and maps them to the companies schema shape
directly in n8n (see n8n/WF-01-lead-import.json) — there's no Python
processing step in the discovery stage itself, since "map these columns to
those columns" doesn't need more than n8n's own Google Sheets + Supabase
nodes.

This package exists as a placeholder for when discovery becomes more
automated (e.g. a Google Maps/LinkedIn scraping module producing structured
candidate rows programmatically instead of a human populating a staging
sheet) — at that point it would gain the same shape as every other stage
here: a pure-function interface module plus a thin DB-touching wrapper,
matching python/research/interface.py's pattern. Not built in V1 because
docs/01-system-prd.md scopes V1 discovery as manual (staging sheet), and
building speculative interfaces ahead of an actual second implementation
violates the same "interfaces before implementations, not before there's
a second thing to abstract" principle the rest of this codebase follows.
"""
