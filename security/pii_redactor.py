from presidio_analyser import AnalyzerEngine
from presidio_anonmizer import AnonymizerEngine

#  Initialize presidio globally so it load models once
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

def  redact(text:str)->str:
    """
    Sacan text for PII (Name, Phones,emails,SSN) and return anonymized text
    """
    # Analyse the text for PII Entities
    results = analyzer.analyze(
        text=text,
        entities=["EMAIL_ADDRESS","PHONE_NUMBER", "CREDIT_CARD","PERSON","LOCATION"],
        language="en",
    )

    # Anonymize the detected entities
    anonymized = anonymizer.anonymize(text=text, analyze_results=results)
    return anonymized.text

