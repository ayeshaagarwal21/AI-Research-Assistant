"""Answer questions that appear inside an uploaded image (screenshot, photo of a page...).

Gemini is multimodal, so the same model used for chat reads the image directly -
no separate OCR step is needed.
"""
import base64
from typing import List, Optional

VISION_PROMPT = """
You are an AI assistant. The user attached an image - often a screenshot or photo
of a question, quiz, assignment or problem.

1. Read the image carefully.
2. If it contains one or more questions or problems, answer each one clearly.
   Number the answers to match the questions, and show the key steps for maths or logic.
3. If it contains no question, briefly describe what it shows and say that no
   question was found - unless the user's note below asks for something else.
4. If part of the image is unreadable, say so instead of guessing.

User's note: {instruction}

Earlier conversation:
{chat_history}
"""


def detect_image_type(data: bytes) -> Optional[str]:
    """Identify PNG/JPEG/WEBP/GIF from the file's first bytes (don't trust the filename)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def build_prompt(instruction: str, history: Optional[List[dict]] = None) -> str:
    history_text = (
        "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in history)
        if history
        else "(none)"
    )
    note = instruction.strip() or "(none - answer the question(s) in the image)"
    return VISION_PROMPT.format(instruction=note, chat_history=history_text)


def answer_image(
    image_bytes: bytes,
    mime_type: str,
    instruction: str = "",
    history: Optional[List[dict]] = None,
) -> str:
    # Imported here so the helpers above stay usable (and testable) without langchain installed.
    from langchain_core.messages import HumanMessage

    from backend.app.services.llm_service import get_llm
    from backend.app.services.rag_service import _as_text

    data_uri = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    message = HumanMessage(
        content=[
            {"type": "text", "text": build_prompt(instruction, history)},
            {"type": "image_url", "image_url": {"url": data_uri}},
        ]
    )
    return _as_text(get_llm().invoke([message]).content).strip()
