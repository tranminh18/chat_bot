from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str
    chunk_size: int = 800
    chunk_overlap: int = 150
    max_context_docs: int = 6
    embedding_model: str = "models/text-embedding-004"
    chat_model: str = "gemini-1.5-flash"

    class Config:
        env_file = ".env"


settings = Settings()
