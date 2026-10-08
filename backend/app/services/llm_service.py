from functools import lru_cache

from backend.app.core import config


class LLMConfigError(RuntimeError):
    """The language model is not configured (e.g. missing API key)."""


@lru_cache(maxsize=1)
def get_llm():
    """Create the Gemini client on first use, so the server can start without a key."""
    if not config.GOOGLE_API_KEY:
        raise LLMConfigError(
            "GOOGLE_API_KEY is not set. Add it to the .env file and restart the backend."
        )

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL,
        google_api_key=config.GOOGLE_API_KEY,
        temperature=0.3,
    )
