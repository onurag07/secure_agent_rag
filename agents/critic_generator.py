from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from config import settings

GENERATOR_PROMPT = """You are a helpful AI assistant. Answer the user's question 
using ONLY the provided context. If the answer is not in the context, say "I don't know based on the context."

CONTEXT:
{context}"""

def generate_respose(query:str, retrieved_docs:list[dict])->str:
    llm = ChatGroq(model=settings.model_name, temperature=0.7, api_key=settings.groq_api_key)
    
    # Format context from retrieved documents
    context_text = "\n\n".join([doc["content"] for doc in retrieved_docs])
    
    formatted_system = GENERATOR_PROMPT.replace("{context}", context_text)
    
    resp = llm.invoke([
        SystemMessage(content=formatted_system),
        HumanMessage(content=query)
    ])
    
    return resp.content
    
    