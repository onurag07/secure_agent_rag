import requests
import time

API_URL = "http://localhost:8000"

def test_api():
    print("Testing API...")
    # 1. Signup
    signup_data = {"email": "test@example.com", "password": "password123"}
    resp = requests.post(f"{API_URL}/api/auth/signup", json=signup_data)
    if resp.status_code == 409:
        print("User already exists, trying signin...")
        resp = requests.post(f"{API_URL}/api/auth/signin", json=signup_data)
    
    resp.raise_for_status()
    data = resp.json()
    token = data["access_token"]
    user_id = data["user_id"]
    
    print(f"Logged in! User ID: {user_id}")
    
    # 2. Get Thread
    headers = {"Authorization": f"Bearer {token}"}
    threads_resp = requests.get(f"{API_URL}/api/threads", headers=headers)
    threads_resp.raise_for_status()
    threads = threads_resp.json().get("threads", [])
    
    if not threads:
        new_thread = requests.post(f"{API_URL}/api/threads", json={"title": "Test Thread"}, headers=headers).json()
        thread_id = new_thread["thread_id"]
    else:
        thread_id = threads[0]["thread_id"]
        
    print(f"Using Thread ID: {thread_id}")
    
    # 3. Ingest vector data
    files = {"file": ("test_doc.txt", b"This is a test document about pgvector and securely storing vectors in Postgres.")}
    ingest_resp = requests.post(f"{API_URL}/api/ingest", headers=headers, files=files)
    ingest_resp.raise_for_status()
    print("Ingest response:", ingest_resp.json())
    
    # 4. Chat
    chat_payload = {"message": "What is pgvector?", "thread_id": thread_id}
    chat_resp = requests.post(f"{API_URL}/api/chat", json=chat_payload, headers=headers)
    chat_resp.raise_for_status()
    print("Chat response:", chat_resp.json())
    
    # 5. Get History
    history_resp = requests.get(f"{API_URL}/api/threads/{thread_id}/messages", headers=headers)
    history_resp.raise_for_status()
    print("History length:", len(history_resp.json()["messages"]))
    
if __name__ == "__main__":
    for _ in range(30):
        try:
            requests.get(f"{API_URL}/health").raise_for_status()
            break
        except:
            print("Waiting for API...")
            time.sleep(2)
    test_api()
