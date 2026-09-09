from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from dotenv import load_dotenv

# Load .env into os.environ so LangSmith and others can find the keys
load_dotenv()
import os
os.environ.pop("LANGCHAIN_TRACING", None)

class Settings(BaseSettings):
    groq_api_key: str = ""
    langchain_api_key: str = ""
    langchain_tracing_v2: bool = False
    langchain_project: str = "secure-agent-rag"
    
    # Model Routing & Token Caps
    model_name: str = "groq/compound"
    primary_model: str = "groq/compound"    # Alias used by security & RAG agents
    planner_model_name: str = "groq/compound-mini"  # Token Strategy 1: Small LLM for Planning
    max_tokens: int = 512                              # Token Strategy 2: Max Output Cap
    max_input_tokens: int = 4096                       # Token Strategy 3: Max Input Guard Cap
    secret_key: str = "fallback-secret-key-123"
    debug: bool = False

    # Security Thresholds
    risk_score_threshold: float = 0.7                  # Prompt injection risk score cutoff (0–1)

    # JWT Auth
    jwt_secret_key: str = "change-me-in-production-minimum-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # Redis & PGVector Connection Strings
    redis_url: str = "redis://localhost:6379/0"
    pgvector_url: str = "postgresql+psycopg://rag_user:rag_pass@localhost:5432/rag_db"
    pgvector_async_url: str = "postgresql+asyncpg://rag_user:rag_pass@localhost:5432/rag_db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()


# Convenience instance used across all nodes
settings = get_settings()
# How to use in OTHER files:
# from config import get_settings
# settings = get_settings()  
# print(settings.model_name)  # llama-3.3-70b-versatile