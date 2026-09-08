import streamlit as st
import uuid
import requests
import json
from config import settings

st.set_page_config(page_title="SecureAgentRAG", page_icon="🛡️")
st.title("🛡️ SecureAgentRAG Chat")

# Initialize session state variables
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar for session management and pgvector stats
with st.sidebar:
    st.header("⚙️ Session Details")
    st.caption(f"**Session ID:** {st.session_state.session_id[:8]}...")
    st.caption(f"**Thread ID:** {st.session_state.thread_id[:8]}...")
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4()) # Start a new thread
        st.rerun()
        
    st.divider()
    st.header("🐘 pgvector backend")
    st.success("Vector Database Connected")
    st.info("Hybrid Search (HNSW) Active")

    st.divider()
    st.header("📎 Add to Knowledge Base")
    uploaded = st.file_uploader("Upload a .txt file to ingest into RAG", type=["txt"])
    if uploaded and st.button("Ingest File"):
        with st.spinner("Indexing..."):
            resp = requests.post(
                "http://localhost:8000/api/ingest",
                headers={"X-API-Key": settings.secret_key},
                files={"file": (uploaded.name, uploaded.getvalue())},
                timeout=30
            )
        if resp.status_code == 200:
            st.success(f"Indexed {resp.json()['chars']} chars from {uploaded.name}")
        else:
            st.error(f"Ingest failed: {resp.status_code}")

# Render existing messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat Input
if prompt := st.chat_input("Ask a secure question..."):
    # 1. Add user message to UI
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # 2. Call backend API (which uses LangGraph + pgvector)
    with st.chat_message("assistant"):
        with st.spinner("Thinking securely..."):
            try:
                # The backend API uses the thread_id to resume LangGraph state
                response = requests.post(
                    "http://localhost:8000/api/chat",
                    headers={"X-API-Key": settings.secret_key},
                    json={
                        "message": prompt,
                        "thread_id": st.session_state.thread_id,
                        "session_id": st.session_state.session_id
                    },
                    timeout=30
                )
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("generation", "I couldn't generate an answer.")
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    st.error(f"Backend error: {response.status_code}")
            except Exception as e:
                st.error("Failed to connect to the backend server. Is it running?")