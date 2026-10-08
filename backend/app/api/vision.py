import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.app.core import config
from backend.app.core.dependencies import get_current_user
from backend.app.db.database import add_message, create_conversation, get_conversation, get_messages
from backend.app.schemas.chat import ChatResponse
from backend.app.services.llm_service import LLMConfigError
from backend.app.services.vision_service import answer_image, detect_image_type

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vision", tags=["vision"])


@router.post("/ask", response_model=ChatResponse)
def ask_about_image(
    image: UploadFile = File(...),
    instruction: str = Form(""),
    conversation_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """Upload a screenshot/photo; the AI reads it and answers any question it contains."""
    user_id = current_user["id"]
    conversation = get_conversation(user_id, conversation_id) if conversation_id else None
    if conversation_id and conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation is None:
        conversation = create_conversation(user_id, "Image research")
    conversation_id = conversation["id"]

    data = image.file.read()
    if not data:
        raise HTTPException(status_code=422, detail="The image file is empty")
    if len(data) > config.MAX_IMAGE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail=f"Image is larger than {config.MAX_IMAGE_MB} MB"
        )

    mime_type = detect_image_type(data)
    if mime_type is None:
        raise HTTPException(
            status_code=422, detail="Unsupported image. Please upload a PNG, JPG, WEBP or GIF."
        )

    instruction = instruction.strip()[:1000]
    history = get_messages(user_id, limit=config.HISTORY_MESSAGES_IN_PROMPT, conversation_id=conversation_id)

    try:
        answer = answer_image(data, mime_type, instruction, history)
    except LLMConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("Image question failed")
        raise HTTPException(
            status_code=502,
            detail="The model could not process the image. Please try again.",
        )

    # The image itself is not stored - only a text note, plus the answer.
    label = "📷 [Image] " + (instruction or "Answer the question in the image")
    add_message(user_id, "user", label, conversation_id=conversation_id)
    add_message(user_id, "assistant", answer, [], conversation_id=conversation_id)

    return ChatResponse(answer=answer, sources=[], conversation_id=conversation_id)
