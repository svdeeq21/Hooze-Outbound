# Scorer — Not an AI Prompt

Per docs/06-scoring-engine.md, scoring is a **deterministic rule engine**, not an AI call. This file exists as a placeholder/reference so the `prompts/` directory documents every stage of the pipeline, but `python/scoring/` should implement the rules in docs/06-scoring-engine.md directly in code (if/else or a rules table), not via an LLM call.

Rationale: scoring must be auditable and reproducible — `lead_scores.reason` must always be explainable by pointing at a specific rule, which a non-deterministic AI call cannot guarantee.

If a future version explores AI-assisted scoring (e.g. to catch pain signals not covered by explicit rules), it must:
- Run alongside, not replace, the deterministic engine
- Only ever adjust `personalization_score` or suggest new candidate pain/buying signals for human review — never alter `icp_score` or the DONT_CONTACT/disqualifier logic
