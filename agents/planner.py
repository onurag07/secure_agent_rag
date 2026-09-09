import json
import logging
from typing import Tuple, List, Dict, Any
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a query Planner. Your job is to classify the User's intent and break down complex questions into sub-queries for retrieval.
Return ONLY VALID JSON in the format:
{"intent": "general_qa|code_help|rag_help|summarization|malicious", "sub_queries": ["query1", "query2"]}"""

def plan(sanitized_query: str) -> Tuple[str, List[str]]:
    llm = ChatGroq(model=settings.planner_model_name, temperature=0, api_key=settings.groq_api_key, max_tokens=150)
    try:
        resp = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=sanitized_query)
        ])
        content = resp.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        intent = data.get("intent", "general_qa")
        sub_queries = data.get("sub_queries", [sanitized_query])
        return intent, sub_queries
    except Exception as e:
        log.warning("Planner LLM fallback (%s) — returning single query", e)
        return "general_qa", [sanitized_query]

def plan_node(state_or_query: Any) -> Dict[str, Any]:
    if isinstance(state_or_query, dict):
        q = state_or_query.get("sanitized_query") or state_or_query.get("query", "")
        intent, subs = plan(q)
        return {"intent": intent, "sub_queries": subs}
    intent, subs = plan(str(state_or_query))
    return {"intent": intent, "sub_queries": subs}
