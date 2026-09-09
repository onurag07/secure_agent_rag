import re
import json
import logging
from typing import Tuple, Optional, List
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from config import settings

log = logging.getLogger(__name__)

GROUNDEDNESS_PROMPT = """You are a groundedness judge. Determine if the RESPONSE is fully supported by the CONTEXT.
If the response contains facts not in the context, or contradicts the context, return is_grounded: false.
Return ONLY JSON: {{"is_grounded": true|false, "reason": "one sentence explanation"}}"""

def _regex_checks(response: str) -> Tuple[bool, str]:
    if "You are security classifier" in response or "You are an AI assistant" in response:
        return False, "System prompt leakage detected in output."
    if re.search(r"(\bpassword\b|\bsecret_key\b).{0,20}[:=]", response, re.IGNORECASE):
        return False, "Potential credentials leakage detected (jailbroken)."
    if "kill myself" in response or "suicide" in response:
        return False, "Sensitive content detected (self-harm/weapons)."
    return True, "ok"

def _groundedness_check(response: str, retrieved_docs: Optional[List[dict]]) -> Tuple[bool, str]:
    if not retrieved_docs:
        return True, "No context to ground against - skipping."
    context = "\n\n".join(d.get("content", "") for d in retrieved_docs if isinstance(d, dict))
    if not context.strip():
        return True, "Empty context - skipping groundedness check."

    try:
        llm = ChatGroq(model=settings.planner_model_name, temperature=0, api_key=settings.groq_api_key, max_tokens=150)
        resp = llm.invoke([
            SystemMessage(content=GROUNDEDNESS_PROMPT),
            HumanMessage(content=f"CONTEXT:\n{context}\n\nRESPONSE:\n{response}")
        ])
        data = json.loads(resp.content.replace("```json", "").replace("```", "").strip())
        if not data.get("is_grounded", True):
            return False, f"Hallucination detected: {data.get('reason', 'Ungrounded claim')}"
    except Exception as e:
        log.warning("Groundedness LLM check skipped: %s", e)
    return True, "ok"

def validate_output(response: str, retrieved_docs: Optional[List[dict]] = None) -> Tuple[bool, str]:
    """Layer 3 output security: regex leak/harm scan, then LLM groundedness judge."""
    is_safe, reason = _regex_checks(response)
    if not is_safe:
        return False, reason
    return _groundedness_check(response, retrieved_docs or [])