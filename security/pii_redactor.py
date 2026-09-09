import re
import logging

log = logging.getLogger(__name__)

# Try initializing Presidio globally
try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    _analyzer = AnalyzerEngine()
    _anonymizer = AnonymizerEngine()
    PRESIDIO_AVAILABLE = True
except Exception as e:
    log.warning("Presidio PII analyzer not available (%s) — using regex fallback redactor", e)
    _analyzer = None
    _anonymizer = None
    PRESIDIO_AVAILABLE = False

def redact(text: str) -> str:
    """
    Scans text for PII (Email, Phone, SSN, Credit Card) and returns anonymized text.
    """
    if not text:
        return text

    if PRESIDIO_AVAILABLE and _analyzer and _anonymizer:
        try:
            results = _analyzer.analyze(
                text=text,
                entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "PERSON", "LOCATION"],
                language="en",
            )
            anonymized = _anonymizer.anonymize(text=text, analyzer_results=results)
            return anonymized.text
        except Exception as e:
            log.warning("Presidio anonymization failed (%s), falling back to regex", e)

    # Regex Fallback
    redacted = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL_REDACTED]', text)
    redacted = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE_REDACTED]', redacted)
    redacted = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]', redacted)
    redacted = re.sub(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b', '[CREDIT_CARD_REDACTED]', redacted)
    return redacted
