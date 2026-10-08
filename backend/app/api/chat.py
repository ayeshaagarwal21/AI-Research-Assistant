import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.app.core import config
from backend.app.core.dependencies import get_current_user
from backend.app.db.database import add_message, create_conversation, get_conversation, get_messages
from backend.app.prompts.rag_prompt import NOT_FOUND_MESSAGE
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services.llm_service import LLMConfigError
from backend.app.services.pdf_question_service import (
    answer_pdf_questions,
    wants_pdf_questions,
)
from backend.app.services.rag_service import generate_answer, generate_general_answer
from utils.embeddings import load_embedding_model
from utils.retriever import retrieve_chunks
from utils.vector_store import get_index, load_pages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

NO_DOCUMENTS_MESSAGE = (
    "You haven't uploaded any documents yet. Upload a PDF and click "
    "**Process documents**, or switch to General knowledge mode."
)


def _build_sources(retrieved: list) -> list:
    """One entry per (file, page), best-scoring first."""
    seen, sources = set(), []
    for chunk in retrieved:
        key = (chunk["source"], chunk["page"])
        if key in seen:
            continue
        seen.add(key)
        snippet = chunk["text"].strip().replace("\n", " ")
        sources.append(
            {
                "source": chunk["source"],
                "page": chunk["page"],
                "score": round(chunk["score"], 3),
                "snippet": snippet[:300] + ("..." if len(snippet) > 300 else ""),
            }
        )
    return sources


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """Three modes:

    documents      - answer a question about the PDFs' content (with sources)
    pdf_questions  - find the questions written inside the PDFs and answer them
    general        - answer from the model's own knowledge (no PDFs needed)

    In "documents" mode, messages like "answer question 3" or "solve all the questions"
    are automatically routed to "pdf_questions".
    """
    user_id = current_user["id"]
    question = request.question.strip()

    conversation = get_conversation(user_id, request.conversation_id) if request.conversation_id else None
    if request.conversation_id and conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation is None:
        title = question[:70].strip() + ("…" if len(question) > 70 else "")
        conversation = create_conversation(user_id, title or "New research chat")
    conversation_id = conversation["id"]

    mode = request.mode
    if mode == "documents" and wants_pdf_questions(question):
        mode = "pdf_questions"

    # Read history *before* saving the new question so it isn't duplicated in the prompt.
    history = get_messages(user_id, limit=config.HISTORY_MESSAGES_IN_PROMPT, conversation_id=conversation_id)

    retrieved, pages = [], []
    if mode == "documents":
        index, chunks = get_index(user_id)
        if index is None:
            return ChatResponse(answer=NO_DOCUMENTS_MESSAGE, sources=[], conversation_id=conversation_id)
        retrieved = retrieve_chunks(
            question, load_embedding_model(), index, chunks, top_k=config.TOP_K
        )
    elif mode == "pdf_questions":
        pages = load_pages(user_id)
        if not pages:
            return ChatResponse(answer=NO_DOCUMENTS_MESSAGE, sources=[], conversation_id=conversation_id)

    try:
        if mode == "general":
            answer = generate_general_answer(question, history)
        elif mode == "pdf_questions":
            answer = answer_pdf_questions(question, pages, history)
        else:
            answer = generate_answer(question, retrieved, history)
    except LLMConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("LLM call failed")
        raise HTTPException(
            status_code=502,
            detail="The language model request failed. Please try again in a moment.",
        )

    # Only plain document Q&A shows source cards (the other modes cite pages in the text).
    show_sources = mode == "documents" and NOT_FOUND_MESSAGE not in answer
    sources = _build_sources(retrieved) if show_sources else []

    add_message(user_id, "user", question, conversation_id=conversation_id)
    add_message(user_id, "assistant", answer, sources, conversation_id=conversation_id)

    return ChatResponse(answer=answer, sources=sources, conversation_id=conversation_id)
