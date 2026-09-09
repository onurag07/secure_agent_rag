import json
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from config import settings

log = logging.getLogger(__name__)

GENERATOR_PROMPT = """You are a helpful AI assistant. Answer the user's question using ONLY the provided context. If the answer is not in the context, state clearly what is missing or state that you don't know based on the context.

CONTEXT:
{context}"""

CRITIC_PROMPT = """Rate how well these retrieved documents can answer the question.
Return ONLY JSON: {{"relevance": 0.0-1.0, "missing": "what info is missing, if any"}}

QUESTION: {query}

DOCUMENTS:
{docs}"""

REWRITER_PROMPT = """The first search for this question returned weak results.
Missing info: {missing}
Rewrite the question as 1-2 sharper, more specific search queries.
Return ONLY JSON: {{"sub_queries": ["query1", "query2"]}}

ORIGINAL QUESTION: {query}"""

def critic_agent(query: str, retrieved_docs: list[dict]) -> dict:
    if not retrieved_docs:
        return {"relevance": 0.0, "missing": "no documents retrieved"}
    llm = ChatGroq(model=settings.planner_model_name, temperature=0, api_key=settings.groq_api_key, max_tokens=150)
    docs_text = "\n\n".join(d.get("content", "") for d in retrieved_docs)
    try:
        resp = llm.invoke([
            SystemMessage(content="Rate how well the retrieved documents answer the question. Return ONLY JSON: {\"relevance\": 0.0-1.0, \"missing\": \"what info is missing, if any\"}"),
            HumanMessage(content=f"QUESTION: {query}\n\nDOCUMENTS:\n{docs_text}")
        ])
        data = json.loads(resp.content.replace("```json", "").replace("```", "").strip())
        return {"relevance": float(data.get("relevance", 1.0)), "missing": data.get("missing", "")}
    except Exception as e:
        log.warning("Critic agent JSON parse failed (%s) — failing open", e)
        return {"relevance": 1.0, "missing": ""}

def rewrite_query(query: str, missing: str) -> list[str]:
    llm = ChatGroq(model=settings.planner_model_name, temperature=0.3, api_key=settings.groq_api_key, max_tokens=150)
    try:
        resp = llm.invoke([
            SystemMessage(content="The search for this question returned weak results. Rewrite the question as 1-2 sharper, more specific search queries. Return ONLY JSON: {\"sub_queries\": [\"query1\", \"query2\"]}"),
            HumanMessage(content=f"ORIGINAL QUESTION: {query}\n\nMISSING INFO: {missing}")
        ])
        data = json.loads(resp.content.replace("```json", "").replace("```", "").strip())
        return data.get("sub_queries", [query])
    except Exception as e:
        log.warning("Rewriter agent failed (%s) — returning original query", e)
        return [query]

# Alias for backwards compatibility
rewriter_agent = rewrite_query

def generate_response(query: str, retrieved_docs: list[dict]) -> str:
    context_text = "\n\n".join(doc.get("content", "") for doc in retrieved_docs) if retrieved_docs else "No specific documents retrieved."
    llm = ChatGroq(
        model=settings.model_name,
        temperature=0.3,
        api_key=settings.groq_api_key,
        max_tokens=settings.max_tokens
    )
    try:
        resp = llm.invoke([
            SystemMessage(content=GENERATOR_PROMPT.format(context=context_text)),
            HumanMessage(content=query)
        ])
        return resp.content
    except Exception as e:
        log.error("Generator LLM invocation error: %s", e)
        if retrieved_docs:
            doc_summary = "\n\n".join(f"• {doc.get('content', '')}" for doc in retrieved_docs)
            return (
                f"**Retrieved Answer (LLM Generation Failed):**\n\n{doc_summary}\n\n"
                f"*Note: The LLM failed to generate a response. Error: {e}*"
            )
        return f"I encountered an issue generating a response. Error: {e}"