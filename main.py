from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from graph import app as agent_graph
from config import settings
import os

api = FastAPI(title="SecureAgentRAG", version="2.0")

# --- AUTHENTICATION ---
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != settings.secret_key:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

class QueryRequest(BaseModel):
    message: str
    user_id: str = "anonymous"
    session_id: str = "default_session"
    thread_id: str = "default_thread"

@api.get("/health")
def health():
    return {"status": "ok", "model": settings.model_name}

@api.post("/api/chat")
async def chat(req: QueryRequest, api_key: str = Depends(verify_api_key)):
    # Setup initial state
    state = {
        "query": req.message, 
        "user_id": req.user_id, 
        "session_id": req.session_id,
        "thread_id": req.thread_id,
        "security_events": [],
        "iteration_count": 0
    }  
    
    # Execute LangGraph pipeline with session and thread memory
    config = {"configurable": {"thread_id": req.thread_id, "session_id": req.session_id}}
    result = await agent_graph.ainvoke(state, config=config)
    
    return {
        "generation": result.get('final_response', 'Request failed.'),
        "safe": result.get('is_safe', False),
        "threat_type": result.get('threat_type')
    }

if __name__ == "__main__":
    import uvicorn
    # Make sure GROQ_API_KEY is available in environment
    if not os.getenv("GROQ_API_KEY"):
        print("WARNING: GROQ_API_KEY not found in environment!")
    uvicorn.run("main:api", host="0.0.0.0", port=8000, reload=True)