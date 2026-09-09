import streamlit as st
import requests
import uuid

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="SecureAgentRAG", page_icon="🛡️", layout="wide")

# ── Initialize Session State ───────────────────────────────────────
for key, default in {
    "jwt_token": None,
    "user_id": None,
    "user_email": None,
    "threads": [],
    "active_thread_id": None,
    "active_thread_title": "New Conversation",
    "messages": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Auth Helper ────────────────────────────────────────────────────
def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.jwt_token}"}

def ensure_active_thread():
    """Create a thread if none is active (e.g. after server restart wipes in-memory store)."""
    if st.session_state.active_thread_id:
        return True
    resp = requests.post(
        f"{API_BASE}/api/threads",
        headers=auth_headers(),
        json={"title": "New Conversation"},
        timeout=10
    )
    if resp.status_code == 200:
        new_t = resp.json()
        st.session_state.threads.insert(0, new_t)
        st.session_state.active_thread_id = new_t["thread_id"]
        st.session_state.active_thread_title = new_t["title"]
        return True
    return False

# ── NOT LOGGED IN: Show Login / Signup ─────────────────────────────
if not st.session_state.jwt_token:
    st.title("🛡️ SecureAgentRAG")
    st.subheader("Sign in to your account")

    tab_signin, tab_signup = st.tabs(["🔑 Sign In", "📝 Sign Up"])

    with tab_signin:
        with st.form("signin_form"):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)
        if submitted:
            if not email or not password:
                st.error("Email and password are required.")
            else:
                with st.spinner("Signing in..."):
                    resp = requests.post(
                        f"{API_BASE}/api/auth/signin",
                        json={"email": email, "password": password},
                        timeout=10
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.jwt_token = data["access_token"]
                    st.session_state.user_id = data["user_id"]
                    st.session_state.user_email = data["email"]
                    st.session_state.threads = data.get("threads", [])
                    if st.session_state.threads:
                        st.session_state.active_thread_id = st.session_state.threads[0]["thread_id"]
                        st.session_state.active_thread_title = st.session_state.threads[0]["title"]
                    st.success("Signed in!")
                    st.rerun()
                else:
                    st.error(f"Sign in failed: {resp.json().get('detail', 'Unknown error')}")

    with tab_signup:
        with st.form("signup_form"):
            new_email = st.text_input("Email", placeholder="you@example.com", key="su_email")
            new_pass = st.text_input("Password (min 8 chars)", type="password", key="su_pass")
            submitted2 = st.form_submit_button("Create Account", use_container_width=True)
        if submitted2:
            if not new_email or len(new_pass) < 8:
                st.error("Valid email and password (min 8 chars) required.")
            else:
                with st.spinner("Creating account..."):
                    resp = requests.post(
                        f"{API_BASE}/api/auth/signup",
                        json={"email": new_email, "password": new_pass},
                        timeout=10
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.jwt_token = data["access_token"]
                    st.session_state.user_id = data["user_id"]
                    st.session_state.user_email = data["email"]
                    # Auto-create first thread is done by signup endpoint
                    first_tid = data.get("first_thread_id", str(uuid.uuid4()))
                    st.session_state.threads = [{"thread_id": first_tid, "title": "My First Conversation"}]
                    st.session_state.active_thread_id = first_tid
                    st.session_state.active_thread_title = "My First Conversation"
                    st.success("Account created! Welcome aboard 🎉")
                    st.rerun()
                else:
                    st.error(f"Signup failed: {resp.json().get('detail', 'Unknown error')}")

# ── LOGGED IN: Main Chat Interface ─────────────────────────────────
else:
    # ── Sidebar ────────────────────────────────────────────────────
    with st.sidebar:
        st.header("🛡️ SecureAgentRAG")
        st.caption(f"👤 **{st.session_state.user_email}**")
        st.caption(f"🆔 `{st.session_state.user_id[:8]}...`")

        st.divider()

        # Thread Management
        st.subheader("💬 Conversations")

        # New thread button
        with st.form("new_thread_form", clear_on_submit=True):
            thread_title = st.text_input("Thread title", placeholder="Ask about RAG...")
            if st.form_submit_button("➕ New Thread"):
                title = thread_title.strip() or "New Conversation"
                resp = requests.post(
                    f"{API_BASE}/api/threads",
                    headers=auth_headers(),
                    json={"title": title},
                    timeout=10
                )
                if resp.status_code == 200:
                    new_t = resp.json()
                    st.session_state.threads.insert(0, new_t)
                    st.session_state.active_thread_id = new_t["thread_id"]
                    st.session_state.active_thread_title = new_t["title"]
                    st.session_state.messages = []  # fresh messages for new thread
                    st.rerun()
                else:
                    st.error("Failed to create thread.")

        # Thread selector
        if st.session_state.threads:
            thread_titles = [t["title"] for t in st.session_state.threads]
            thread_ids    = [t["thread_id"] for t in st.session_state.threads]
            current_idx = 0
            if st.session_state.active_thread_id in thread_ids:
                current_idx = thread_ids.index(st.session_state.active_thread_id)
            selected = st.selectbox(
                "Select thread", thread_titles,
                index=current_idx, label_visibility="collapsed"
            )
            selected_id = thread_ids[thread_titles.index(selected)]
            if selected_id != st.session_state.active_thread_id:
                st.session_state.active_thread_id = selected_id
                st.session_state.active_thread_title = selected
                st.session_state.messages = []  # clear messages on thread switch
                st.rerun()

        st.divider()

        # File upload / ingest
        st.subheader("📎 Knowledge Base")
        uploaded = st.file_uploader("Upload document (.pdf or .txt)", type=["txt", "pdf"])
        if uploaded and st.button("Ingest File", use_container_width=True):
            with st.spinner("Parsing & Indexing into Knowledge Base..."):
                resp = requests.post(
                    f"{API_BASE}/api/ingest",
                    headers=auth_headers(),
                    files={"file": (uploaded.name, uploaded.getvalue())},
                    timeout=30
                )
            if resp.status_code == 200:
                data = resp.json()
                st.success(data.get("message", f"Successfully indexed {data.get('chunks_added', 0)} chunks!"))
            else:
                st.error(f"Ingest failed ({resp.status_code}): {resp.text}")

        st.divider()

        # Sign Out
        if st.button("🚪 Sign Out", use_container_width=True):
            for k in ["jwt_token", "user_id", "user_email", "threads",
                      "active_thread_id", "active_thread_title", "messages"]:
                st.session_state[k] = None if k == "jwt_token" else ([] if k in ["threads", "messages"] else None)
            st.rerun()

    # ── Main Chat Area ─────────────────────────────────────────────
    st.title(f"💬 {st.session_state.active_thread_title}")
    st.caption(f"Thread: `{st.session_state.active_thread_id}`")

    # Render messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask a secure question..."):
        if not st.session_state.active_thread_id:
            st.warning("Please create or select a conversation thread first.")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking securely..."):
                    try:
                        def _send_chat(thread_id):
                            return requests.post(
                                f"{API_BASE}/api/chat",
                                headers=auth_headers(),
                                json={"message": prompt, "thread_id": thread_id},
                                timeout=60
                            )

                        response = _send_chat(st.session_state.active_thread_id)

                        # Auto-recover: thread was lost (server restart wiped in-memory store)
                        if response.status_code == 404:
                            st.toast("⚠️ Thread expired after server restart — creating a new one...", icon="🔄")
                            new_resp = requests.post(
                                f"{API_BASE}/api/threads",
                                headers=auth_headers(),
                                json={"title": "Recovered Conversation"},
                                timeout=10
                            )
                            if new_resp.status_code == 200:
                                new_t = new_resp.json()
                                st.session_state.threads.insert(0, new_t)
                                st.session_state.active_thread_id = new_t["thread_id"]
                                st.session_state.active_thread_title = new_t["title"]
                                st.session_state.messages = [{"role": "user", "content": prompt}]
                                response = _send_chat(new_t["thread_id"])  # retry with new thread
                            else:
                                st.error("Could not create a new thread. Please sign out and back in.")
                                st.stop()

                        if response.status_code == 200:
                            data = response.json()
                            answer = data.get("generation", "No response.")
                            cached_badge = " ⚡ *[cached]*" if data.get("cached") else ""
                            st.markdown(answer + cached_badge)
                            st.session_state.messages.append(
                                {"role": "assistant", "content": answer}
                            )
                        elif response.status_code == 401:
                            st.error("Session expired. Please sign in again.")
                            st.session_state.jwt_token = None
                            st.rerun()
                        else:
                            try:
                                detail = response.json().get("detail", "Unknown error")
                            except Exception:
                                detail = response.text[:200] or f"HTTP {response.status_code}"
                            st.error(f"Error {response.status_code}: {detail}")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ Cannot reach backend. Is `uvicorn main:app --port 8000` running?")
                    except Exception as e:
                        st.error(f"Connection error: {e}. Is the backend running?")