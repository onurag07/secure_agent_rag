"""
auth.py — User signup, signin, JWT token management, and Thread storage.
Supports PostgreSQL persistence with seamless in-memory fallback.
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from config import settings
from db import get_db_connection

log = logging.getLogger(__name__)

# ── Password Hashing ───────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# ── JWT Token ──────────────────────────────────────────────────────
class TokenData(BaseModel):
    user_id: str
    email: str

def create_access_token(user_id: str, email: str) -> str:
    """Create JWT access token with user_id and email embedded."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> Optional[TokenData]:
    """Decode and validate JWT token. Returns None if invalid/expired."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        if not user_id:
            return None
        return TokenData(user_id=user_id, email=email)
    except JWTError:
        return None

# ── In-Memory Fallback Stores ──────────────────────────────────────
_USERS_STORE: dict[str, dict] = {}  # email -> {user_id, email, hashed_pw}
_THREADS_STORE: dict[str, list] = {}  # user_id -> [{thread_id, title, created_at}]

# ── User Store (DB + Fallback) ─────────────────────────────────────
def create_user(email: str, password: str) -> dict:
    """Register new user."""
    email = email.lower().strip()
    hashed = hash_password(password)
    user_id = str(uuid.uuid4())

    conn = get_db_connection()
    if conn:
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                    if cur.fetchone():
                        conn.close()
                        raise ValueError("Email already registered.")
                    cur.execute(
                        "INSERT INTO users (id, email, hashed_pw) VALUES (%s, %s, %s)",
                        (user_id, email, hashed)
                    )
            conn.close()
            # Keep in fallback store as well
            _USERS_STORE[email] = {"user_id": user_id, "email": email, "hashed_pw": hashed}
            return {"user_id": user_id, "email": email}
        except ValueError:
            raise
        except Exception as e:
            log.warning("DB user create failed (%s) — using fallback store", e)

    # Fallback in-memory
    if email in _USERS_STORE:
        raise ValueError("Email already registered.")
    _USERS_STORE[email] = {
        "user_id": user_id,
        "email": email,
        "hashed_pw": hashed
    }
    return {"user_id": user_id, "email": email}

def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Check credentials. Returns user dict on success, None on failure."""
    email = email.lower().strip()

    conn = get_db_connection()
    if conn:
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, email, hashed_pw FROM users WHERE email = %s", (email,))
                    row = cur.fetchone()
                    conn.close()
                    if row:
                        u_id, u_email, u_hash = str(row[0]), row[1], row[2]
                        if verify_password(password, u_hash):
                            return {"user_id": u_id, "email": u_email}
                        return None
        except Exception as e:
            log.warning("DB auth query failed (%s) — using fallback store", e)

    # Fallback in-memory
    user = _USERS_STORE.get(email)
    if not user:
        return None
    if not verify_password(password, user["hashed_pw"]):
        return None
    return {"user_id": user["user_id"], "email": user["email"]}

# ── Thread Store (DB + Fallback) ──────────────────────────────────
def create_thread(user_id: str, title: str = "New Conversation") -> dict:
    """Create a new conversation thread for a user."""
    thread_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    conn = get_db_connection()
    if conn:
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO threads (id, user_id, title) VALUES (%s, %s, %s)",
                        (thread_id, user_id, title)
                    )
            conn.close()
        except Exception as e:
            log.warning("DB thread create failed (%s)", e)

    thread = {
        "thread_id": thread_id,
        "user_id": user_id,
        "title": title,
        "created_at": now_iso
    }
    _THREADS_STORE.setdefault(user_id, []).append(thread)
    return thread

def list_threads(user_id: str) -> list:
    """Return all threads for a user, newest first."""
    conn = get_db_connection()
    if conn:
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, title, created_at FROM threads WHERE user_id = %s ORDER BY updated_at DESC",
                        (user_id,)
                    )
                    rows = cur.fetchall()
                    conn.close()
                    if rows:
                        return [{
                            "thread_id": str(r[0]),
                            "user_id": user_id,
                            "title": r[1],
                            "created_at": r[2].isoformat()
                        } for r in rows]
        except Exception as e:
            log.warning("DB list threads failed (%s)", e)

    return sorted(
        _THREADS_STORE.get(user_id, []),
        key=lambda t: t["created_at"],
        reverse=True
    )

def get_thread(user_id: str, thread_id: str) -> Optional[dict]:
    """Get a specific thread, verify it belongs to this user."""
    conn = get_db_connection()
    if conn:
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, title, created_at FROM threads WHERE id = %s AND user_id = %s",
                        (thread_id, user_id)
                    )
                    row = cur.fetchone()
                    conn.close()
                    if row:
                        return {
                            "thread_id": str(row[0]),
                            "user_id": user_id,
                            "title": row[1],
                            "created_at": row[2].isoformat()
                        }
        except Exception as e:
            log.warning("DB get thread failed (%s)", e)

    for t in _THREADS_STORE.get(user_id, []):
        if t["thread_id"] == thread_id:
            return t
    return None