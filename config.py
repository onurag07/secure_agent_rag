from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from dotenv import load_dotenv

# Load .env into os.environ so LangSmith and others can find the keys
load_dotenv()

class Settings(BaseSettings):
    groq_api_key: str = ""
    langchain_api_key: str = ""
    langchain_tracing_v2: bool = True
    langchain_project: str = "secure-agent-rag"
    model_name: str = "llama-3.3-70b-versatile"
    max_tokens: int = 4096
    secret_key: str = "fallback-secret-key-123"
    debug: bool = False

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