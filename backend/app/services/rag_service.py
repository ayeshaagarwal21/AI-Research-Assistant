from typing import List, Optional

from backend.app.prompts.rag_prompt import GENERAL_PROMPT, NOT_FOUND_MESSAGE, RAG_PROMPT
from backend.app.services.llm_service import get_llm


def _format_context(chunks: List[dict]) -> str:
    return "\n\n".join(
        f"[{c['source']}, page {c['page']}]\n{c['text']}" for c in chunks
    )


def _format_history(history: Optional[List[dict]]) -> str:
    if not history:
        return "(none)"
    return "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in history)


def _as_text(content) -> str:
    """Gemini sometimes returns a list of content parts instead of a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part if isinstance(part, str) else part.get("text", "") for part in content
        )
    return str(content)


def generate_answer(
    question: str,
    retrieved_chunks: List[dict],
    chat_history: Optional[List[dict]] = None,
) -> str:
    """Answer `question` using only the retrieved chunks (plus history for follow-ups)."""
    if not retrieved_chunks:
        return NOT_FOUND_MESSAGE

    prompt = RAG_PROMPT.format_messages(
        context=_format_context(retrieved_chunks),
        question=question,
        chat_history=_format_history(chat_history),
    )
    response = get_llm().invoke(prompt)
    return _as_text(response.content).strip()


def generate_general_answer(question: str, chat_history: Optional[List[dict]] = None) -> str:
    """Answer from the model's own knowledge (no documents involved)."""
    prompt = GENERAL_PROMPT.format_messages(
        question=question, chat_history=_format_history(chat_history)
    )
    return _as_text(get_llm().invoke(prompt).content).strip()
