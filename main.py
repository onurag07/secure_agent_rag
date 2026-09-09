from fastapi import FastAPI, Depends, HTTPException, Security, status, File, UploadFile, Form
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from pydantic import BaseModel
import os
import io
import shutil
from fastapi.responses import FileResponse
import logging

from graph import app as agent_graph
from config import settings
from cache import get_cached_response, set_cached_response
from auth import (
    create_user, authenticate_user, create_access_token,
    decode_access_token, create_thread, list_threads, get_thread
)
from db import init_db, save_message, get_conversation_history
from observability import bootstrap_langsmith
from agents.retriever import add_document_to_knowledge_base

log = logging.getLogger(__name__)

app = FastAPI(title="SecureAgentRAG", version="3.0")

@app.on_event("startup")
async def startup():
    try:
        bootstrap_langsmith()
    except Exception as e:
        log.warning("LangSmith bootstrap skipped: %s", e)
    try:
        init_db()
    except Exception as e:
        log.warning("DB init note: %s", e)

# ── Security Schemes ───────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/signin", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key and api_key != settings.secret_key:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

def get_current_user(token: str = Depends(oauth2_scheme)):
    """Decode JWT and return current user. Raises 401 if invalid."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please signin first.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = decode_access_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired or invalid. Please signin again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data

# ── Pydantic Models ────────────────────────────────────────────────
class SignupRequest(BaseModel):
    email: str
    password: str

class SigninRequest(BaseModel):
    email: str
    password: str

class ThreadCreateRequest(BaseModel):
    title: str = "New Conversation"

class QueryRequest(BaseModel):
    message: str
    thread_id: str

# ── Health ─────────────────────────────────────────────────────────
@app.get("/health")
@app.get("/api/v1/health")
def health():
    return {"status": "ok", "model": settings.model_name, "version": "3.0"}

# ── Auth Endpoints ─────────────────────────────────────────────────
@app.post("/api/auth/signup")
def signup(req: SignupRequest):
    """Register a new user account."""
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="Email and password required.")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    try:
        user = create_user(req.email, req.password)
        first_thread = create_thread(user["user_id"], "My First Conversation")
        token = create_access_token(user["user_id"], user["email"])
        return {
            "message": "Account created successfully.",
            "access_token": token,
            "token_type": "bearer",
            "user_id": user["user_id"],
            "email": user["email"],
            "first_thread_id": first_thread["thread_id"]
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.post("/api/auth/signin")
def signin(req: SigninRequest):
    """Sign in and receive JWT access token."""
    user = authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
    token = create_access_token(user["user_id"], user["email"])
    threads = list_threads(user["user_id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "email": user["email"],
        "threads": threads
    }

@app.get("/api/auth/me")
def get_me(current_user=Depends(get_current_user)):
    """Return current user info from JWT."""
    return {"user_id": current_user.user_id, "email": current_user.email}

# ── Thread & Conversation Endpoints ───────────────────────────────
@app.post("/api/threads")
def new_thread(req: ThreadCreateRequest, current_user=Depends(get_current_user)):
    """Create a new conversation thread for the current user."""
    thread = create_thread(current_user.user_id, req.title)
    return thread

@app.get("/api/threads")
def get_threads(current_user=Depends(get_current_user)):
    """List all threads for the current user."""
    return {"threads": list_threads(current_user.user_id)}

@app.get("/api/threads/{thread_id}/messages")
def get_thread_messages(thread_id: str, current_user=Depends(get_current_user)):
    """Retrieve message history for a specific thread."""
    thread = get_thread(current_user.user_id, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    history = get_conversation_history(current_user.user_id, thread_id)
    return {"messages": history}

# ── RAG Chat (JWT Protected) ───────────────────────────────────────
@app.post("/api/chat")
async def chat(req: QueryRequest, current_user=Depends(get_current_user)):
    """
    Main RAG chat endpoint.
    - Requires: Bearer JWT token (from signin)
    - Requires: thread_id (must belong to current user)
    """
    thread = get_thread(current_user.user_id, req.thread_id)
    if not thread:
        raise HTTPException(
            status_code=404,
            detail=f"Thread '{req.thread_id}' not found. Create one via POST /api/threads"
        )

    # Save incoming user query
    save_message(current_user.user_id, req.thread_id, "user", req.message)

    # Cache lookup
    cache_key = f"{current_user.user_id}:{req.thread_id}:{req.message}"
    cached = get_cached_response(cache_key)
    if cached:
        save_message(current_user.user_id, req.thread_id, "assistant", cached)
        return {"generation": cached, "safe": True, "cached": True, "thread_id": req.thread_id}

    state = {
        "query": req.message,
        "user_id": current_user.user_id,
        "session_id": current_user.user_id,
        "thread_id": req.thread_id,
        "security_events": [],
        "iteration_count": 0
    }
    config = {"configurable": {"thread_id": req.thread_id}}
    result = await agent_graph.ainvoke(state, config=config)

    final = result.get("final_response", "Request failed.")
    is_safe = result.get("is_safe", True) if "is_safe" in result else result.get("security_passed", True)

    if is_safe:
        set_cached_response(cache_key, final)

    # Save assistant response
    save_message(current_user.user_id, req.thread_id, "assistant", final)

    return {
        "generation": final,
        "safe": is_safe,
        "threat_type": result.get("threat_type", "none"),
        "thread_id": req.thread_id,
        "user_id": current_user.user_id,
        "cached": False
    }

# ── Document Management (PDF / TXT) ──────────────────────────────
@app.post("/api/ingest")
async def ingest_document(
    thread_id: str = Form(...),
    file: UploadFile = File(...), 
    current_user=Depends(get_current_user)
):
    """
    Ingests PDF or TXT file into Knowledge Base and saves it to user's folder.
    """
    # Verify thread ownership
    thread = get_thread(current_user.user_id, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    filename = file.filename or "uploaded_file"
    ext = filename.lower().split(".")[-1]
    if ext not in ["txt", "pdf"]:
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # --- NEW: Save file to user's personal upload folder ---
    user_upload_dir = os.path.join("uploads", str(current_user.user_id))
    os.makedirs(user_upload_dir, exist_ok=True)
    file_path = os.path.join(user_upload_dir, filename)
    with open(file_path, "wb") as f:
        f.write(content)
    # --------------------------------------------------------

    extracted_text = ""
    if ext == "pdf":
        try:
            from pypdf import PdfReader
            pdf_reader = PdfReader(io.BytesIO(content))
            extracted_text = "\n".join(page.extract_text() or "" for page in pdf_reader.pages)
        except Exception as e:
            log.error("PDF extraction error: %s", e)
            raise HTTPException(status_code=400, detail=f"Failed to read PDF file: {e}")
    else:
        try:
            extracted_text = content.decode("utf-8", errors="ignore")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read TXT file: {e}")

    if not extracted_text.strip():
        raise HTTPException(status_code=400, detail="No readable text extracted from document.")

    chunks_count = add_document_to_knowledge_base(extracted_text, filename=filename)
    
    # Associate this upload visually with the chat thread history
    save_message(
        current_user.user_id, 
        thread_id, 
        "user", 
        f"📄 **Uploaded Document:** `{filename}`\n_({chunks_count} chunks indexed)_"
    )

    return {
        "status": "ok",
        "filename": filename,
        "chunks_added": chunks_count,
        "message": f"Successfully ingested {chunks_count} chunks and saved '{filename}'!"
    }

@app.get("/api/files")
def list_files(current_user=Depends(get_current_user)):
    user_upload_dir = os.path.join("uploads", str(current_user.user_id))
    if not os.path.exists(user_upload_dir):
        return {"files": []}
    return {"files": os.listdir(user_upload_dir)}

@app.get("/api/files/{filename}")
def download_file(filename: str, current_user=Depends(get_current_user)):
    file_path = os.path.join("uploads", str(current_user.user_id), filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)

@app.delete("/api/files/{filename}")
def delete_file(filename: str, current_user=Depends(get_current_user)):
    file_path = os.path.join("uploads", str(current_user.user_id), filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    os.remove(file_path)
    return {"status": "ok", "message": f"Deleted {filename}"}

if __name__ == "__main__":
    import uvicorn
    if not os.getenv("GROQ_API_KEY"):
        print("WARNING: GROQ_API_KEY not found!")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)