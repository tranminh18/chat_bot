"""
Multi-LLM Factory – unified interface qua LangChain BaseChatModel.
Hỗ trợ: Gemini (Google), OpenAI (GPT), Anthropic (Claude).
"""

from functools import lru_cache
from typing import Dict

from langchain_core.language_models import BaseChatModel

from core.config import settings


def create_llm(provider: str | None = None, streaming: bool = False) -> BaseChatModel:
    provider = provider or settings.default_llm

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.chat_model,
            google_api_key=settings.gemini_api_key,
            streaming=streaming,
            temperature=0.7,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY chưa được cấu hình trong .env")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            streaming=streaming,
            temperature=0.7,
        )

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY chưa được cấu hình trong .env")
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model_name=settings.anthropic_model,
            anthropic_api_key=settings.anthropic_api_key,
            streaming=streaming,
            temperature=0.7,
        )

    raise ValueError(f"Provider không hỗ trợ: '{provider}'. Chọn: gemini | openai | anthropic")


def get_available_providers() -> Dict[str, bool]:
    """Trả về dict {provider: is_configured} để hiển thị trên UI."""
    return {
        "gemini": bool(settings.gemini_api_key),
        "openai": bool(settings.openai_api_key),
        "anthropic": bool(settings.anthropic_api_key),
    }
