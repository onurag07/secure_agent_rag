from config import settings
from langchain_groq import ChatGroq
from typing import Tuple
from langchain_core.messages import SystemMessage,HumanMessage
import JSON

SYSTEM_PROMPT = """
You are a query Palnner. Your job is to classify the User's intent and break down complex question into sub-queries for retrieval.
return ONLY VALID JSON in the format:
{"intent":"general_qa", sub_queries:["query1","query2"]}
Intents can be : general_qa, code_help, rag_hlp, summarization, malicious
"""

def plan(sanitized_query:str)->Tuple[str, list[str]]:  
    llm = ChatGroq(model=settings.model_name, temperature=0, api_key=settings.groq_api_key)
    
    try:
        resp: llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=sanitized_query)
        ])

        # clean Up markdown Json blocks if present
        content = resp.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)

        intent = data.get("intent","general_qa")
        sub_queries = data.get("sub_queries", [sanitized_query])
        
        return intent, sub_queries


    except Exception as e:
        # fallback if LLM Fails or Returns bad JSON
        return "general_qa", [sanitized_query]
