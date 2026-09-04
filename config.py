from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    groq_api_key: str
    groq__model : str = "llama-3.3-70b-versatile"
    langchain_api_key: str
    model_name : str = "llama-3.3-70b-versatile"
    max_token: int = 4096
    secret_key: str
    debug: bool
    langchain_tracking_v2: bool = True
    langchain_project: str = "secure-agent-rag"
    class Config:
        env_file = ".env"
        case_sensitive = False
    
@lru_cache
def get_settings() -> Settings:
    return Settings()


# How to use in OTHER files:
# from config import get_settings
# settings = get_settings()  
# print(settings.model_name)  # llama-3.3-70b-versatile