from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini (required)
    gemini_api_key: str
    # OpenAI (optional)
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    # Anthropic / Claude (optional)
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-haiku-20240307"

    # Default provider
    default_llm: str = "gemini"
    chat_model: str = "gemini-1.5-flash"
    embedding_model: str = "models/text-embedding-004"

    # RAG settings
    chunk_size: int = 800
    chunk_overlap: int = 150
    max_context_docs: int = 6

    # Memory
    memory_max_turns: int = 8

    class Config:
        env_file = ".env"


settings = Settings()
