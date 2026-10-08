from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import (
    clear_messages,
    create_conversation,
    delete_conversation,
    get_conversation,
    get_conversations,
    get_messages,
    rename_conversation,
)
from backend.app.schemas.chat import (
    Conversation,
    ConversationCreate,
    ConversationRename,
    HistoryMessage,
)

router = APIRouter(tags=["history"])


@router.get("/history", response_model=List[HistoryMessage])
def read_history(
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    return get_messages(current_user["id"], limit=limit)


@router.delete("/history", status_code=204)
def delete_history(current_user: dict = Depends(get_current_user)):
    clear_messages(current_user["id"])
    return Response(status_code=204)


@router.get("/conversations", response_model=List[Conversation])
def read_conversations(current_user: dict = Depends(get_current_user)):
    return get_conversations(current_user["id"])


@router.post("/conversations", response_model=Conversation, status_code=201)
def new_conversation(payload: ConversationCreate, current_user: dict = Depends(get_current_user)):
    return create_conversation(current_user["id"], payload.title)


@router.get("/conversations/{conversation_id}/messages", response_model=List[HistoryMessage])
def read_conversation_messages(
    conversation_id: int,
    limit: int = Query(500, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
):
    if not get_conversation(current_user["id"], conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return get_messages(current_user["id"], limit=limit, conversation_id=conversation_id)


@router.patch("/conversations/{conversation_id}", response_model=Conversation)
def rename_chat(
    conversation_id: int,
    payload: ConversationRename,
    current_user: dict = Depends(get_current_user),
):
    if not rename_conversation(current_user["id"], conversation_id, payload.title):
        raise HTTPException(status_code=404, detail="Conversation not found")
    row = get_conversation(current_user["id"], conversation_id)
    row["message_count"] = len(get_messages(current_user["id"], 1000, conversation_id))
    return row


@router.delete("/conversations/{conversation_id}", status_code=204)
def remove_chat(conversation_id: int, current_user: dict = Depends(get_current_user)):
    if not delete_conversation(current_user["id"], conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return Response(status_code=204)
