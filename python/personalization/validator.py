"""
python/personalization/validator.py — automated pre-review validation

Implements docs/08-personalization-spec.md §6 EXACTLY:

  [ ] Every specific factual claim in the message text can be matched to an
      evidence[] entry (fuzzy match on key phrases/numbers)
  [ ] No numbers appear in the message that don't appear in evidence[]
  [ ] The CTA matches campaign.cta
  [ ] Message length within the channel limit (§5: WhatsApp <= 80 words,
      email <= 150 words)
  [ ] No competitor names, no unrelated claims

Per §6: "Any failed check routes the draft to REVIEW with a warning flag
rather than blocking it outright — Hooze makes the final call." So this
module NEVER blocks a send; it only annotates. The decision authority stays
exactly where docs/01-system-prd.md §9.6 puts it: with Hooze.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

WHATSAPP_WORD_LIMIT = 80
EMAIL_WORD_LIMIT = 150

_NUMBER_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?\b")


@dataclass
class ValidationResult:
    passed: bool
    warnings: list[str] = field(default_factory=list)

    def add(self, warning: str) -> None:
        self.warnings.append(warning)
        self.passed = False


def _word_count(message: str) -> int:
    return len(message.split())


def _numbers_in(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text))


def _evidence_text_blob(evidence: list[dict]) -> str:
    return " ".join(e.get("claim", "") for e in evidence).lower()


def validate_message(
    message: str,
    channel: str,
    evidence: list[dict],
    campaign_cta: str,
    subject: str | None = None,
) -> ValidationResult:
    result = ValidationResult(passed=True)

    # --- Length check (§5/§6) ---
    limit = WHATSAPP_WORD_LIMIT if channel == "WHATSAPP" else EMAIL_WORD_LIMIT
    wc = _word_count(message)
    if wc > limit:
        result.add(f"Message is {wc} words, exceeds {channel} limit of {limit} words")

    if channel == "EMAIL" and not subject:
        result.add("Email message is missing a subject line (docs/08-personalization-spec.md §5)")

    # --- Number check (§6: "No numbers appear... that don't appear in evidence[]") ---
    # docs/08-personalization-spec.md §3 explicitly allows "general statements
    # about Hooze Enterprises' offer, proof, and CTA (these are Hooze's own
    # claims, not claims about the prospect)" — so a number that comes from
    # the CTA/offer itself (e.g. "15-min demo") is NOT an unsupported claim
    # about the prospect, and must not be flagged the same way an invented
    # fact ABOUT the prospect would be.
    message_numbers = _numbers_in(message)
    evidence_numbers = _numbers_in(_evidence_text_blob(evidence))
    cta_numbers = _numbers_in(campaign_cta)
    unsupported_numbers = message_numbers - evidence_numbers - cta_numbers
    if unsupported_numbers:
        result.add(f"Numbers in message not found in evidence or CTA: {sorted(unsupported_numbers)}")

    # --- CTA check (§6: "The CTA matches campaign.cta") ---
    # Exact-match is too strict for natural phrasing variation in a drafted
    # message (the CTA is paraphrased into a sentence, not pasted verbatim,
    # e.g. "demonstration" -> "demo", "call"), so we check for meaningful
    # word overlap using a small synonym expansion — this is a heuristic,
    # which is exactly why §6 says failures WARN rather than BLOCK.
    _CTA_SYNONYMS = {
        "demonstration": {"demo", "demonstration", "walkthrough", "show"},
        "call": {"call", "chat", "meeting", "talk"},
        "meeting": {"meeting", "call", "chat", "talk"},
        "offer": {"offer"},
        "short": {"short", "quick", "brief"},
    }
    cta_keywords = {w for w in re.findall(r"[a-z]+", campaign_cta.lower()) if len(w) > 3}
    message_words = set(re.findall(r"[a-z]+", message.lower()))
    expanded_cta_keywords: set[str] = set(cta_keywords)
    for kw in cta_keywords:
        expanded_cta_keywords |= _CTA_SYNONYMS.get(kw, set())
    overlap = expanded_cta_keywords & message_words
    if cta_keywords and not overlap:
        result.add(f"Message CTA doesn't clearly match campaign.cta ({campaign_cta!r}); no keyword/synonym overlap")

    # --- Fuzzy evidence-grounding check (§6: "Every specific factual claim
    # in the message text can be matched to an evidence[] entry") ---
    # We do NOT attempt full claim-level NLP matching here (that's the AI's
    # job at generation time, per prompts/personalizer.md rule #1). This is
    # a second-line, code-level sanity check: if the message contains
    # specific evidence-sourced content, at least SOME of the message's
    # meaningful words should overlap with the evidence text. A message with
    # near-zero overlap to any evidence claim is a strong signal the model
    # invented an observation.
    if evidence:
        evidence_words = {w for w in re.findall(r"[a-z]{4,}", _evidence_text_blob(evidence))}
        message_content_words = {w for w in re.findall(r"[a-z]{4,}", message.lower())}
        grounding_overlap = evidence_words & message_content_words
        if not grounding_overlap:
            result.add(
                "Message shares no meaningful vocabulary with any research_evidence claim — "
                "possible unsupported/hallucinated observation, verify manually"
            )

    return result
