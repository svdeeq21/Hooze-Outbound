import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python.personalization.validator import validate_message  # noqa: E402

EVIDENCE = [
    {"claim": "WhatsApp contact button visible on every listing page", "confidence": "HIGH"},
    {"claim": "40+ active property listings across the site", "confidence": "HIGH"},
    {"claim": "No visible automated qualification or booking flow", "confidence": "MEDIUM"},
]
CTA = "Offer a short (15-min) demonstration"


def test_valid_message_passes():
    message = (
        "Noticed Prime Estate has 40+ listings live with WhatsApp as the main way people reach you, "
        "but no automated flow to qualify or book inspections from there. Worth a quick 15-min demo "
        "of how we've automated that for another Abuja agency?"
    )
    result = validate_message(message, "WHATSAPP", EVIDENCE, CTA)
    assert result.passed, result.warnings


def test_message_too_long_for_whatsapp_fails():
    message = "word " * 100
    result = validate_message(message, "WHATSAPP", EVIDENCE, CTA)
    assert not result.passed
    assert any("exceeds" in w for w in result.warnings)


def test_email_without_subject_flagged():
    message = "Short valid email body mentioning 40+ listings and WhatsApp booking flow with a fifteen minute chat offer."
    result = validate_message(message, "EMAIL", EVIDENCE, CTA, subject=None)
    assert not result.passed
    assert any("subject" in w.lower() for w in result.warnings)


def test_unsupported_number_flagged():
    message = "Noticed you have 500 listings and a WhatsApp booking flow gap — worth a 15-min demo?"
    result = validate_message(message, "WHATSAPP", EVIDENCE, CTA)
    assert not result.passed
    assert any("500" in w for w in result.warnings)


def test_evidence_supported_number_passes_number_check():
    message = "Saw Prime Estate has 40+ listings live on WhatsApp with no booking flow — worth a 15-min demo?"
    result = validate_message(message, "WHATSAPP", EVIDENCE, CTA)
    # 40 should be recognized as present in evidence text ("40+ active...")
    assert not any("Numbers in message" in w for w in result.warnings)


def test_message_unrelated_to_evidence_flagged():
    message = "Hope this finds you well! We think your team would love our product for completely unrelated reasons."
    result = validate_message(message, "WHATSAPP", EVIDENCE, CTA)
    assert not result.passed
