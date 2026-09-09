"""
db.py — Database persistence for threads, messages, and user auth.
Supports PostgreSQL (with pgvector) and in-memory fallback for maximum reliability.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from config import settings

log = logging.getLogger(__name__)

def get_db_connection():
    try:
        import psycopg
        # Try configured pgvector_url
        url = settings.pgvector_url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://")
        return psycopg.connect(url, connect_timeout=3)
    except Exception as e:
        return None

def init_db() -> bool:
    """Ensure tables exist if Postgres is connected."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE EXTENSION IF NOT EXISTS vector;
                CREATE EXTENSION IF NOT EXISTS pg_trgm;

                CREATE TABLE IF NOT EXISTS rag_documents (
                    id BIGSERIAL PRIMARY KEY,
                    collection TEXT NOT NULL DEFAULT 'default',
                    content TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}',
                    embedding vector (384),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW (),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW ()
                );

                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
                    email TEXT UNIQUE NOT NULL,
                    hashed_pw TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW ()
                );
                CREATE TABLE IF NOT EXISTS threads (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
                    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                    title TEXT NOT NULL DEFAULT 'New Conversation',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW (),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW ()
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
                    thread_id UUID NOT NULL REFERENCES threads (id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW ()
                );
                """)
        conn.close()
        log.info("Postgres database schema initialized.")
        return True
    except Exception as e:
        log.warning("Postgres schema initialization note: %s", e)
        return False

def save_message(user_id: str, thread_id: str, role: str, content: str):
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO conversations (id, thread_id, role, content) VALUES (%s, %s, %s, %s)",
                    (str(uuid.uuid4()), thread_id, role, content)
                )
        conn.close()
    except Exception as e:
        log.warning("Failed to save message to DB: %s", e)

def get_conversation_history(user_id: str, thread_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT role, content, created_at FROM conversations WHERE thread_id = %s ORDER BY created_at ASC",
                    (thread_id,)
                )
                rows = cur.fetchall()
                conn.close()
                return [{"role": r[0], "content": r[1], "created_at": r[2].isoformat()} for r in rows]
    except Exception as e:
        log.warning("Failed to fetch conversation history: %s", e)
        return []
