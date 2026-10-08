from typing import List, Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    source: str
    page: int
    score: float
    snippet: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: Literal["documents", "pdf_questions", "general"] = "documents"
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[Source] = []
    conversation_id: int | None = None


class HistoryMessage(BaseModel):
    role: str
    content: str
    sources: List[Source] = []
    created_at: str


class Conversation(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationCreate(BaseModel):
    title: str = Field(default="New research chat", min_length=1, max_length=120)


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class DocumentInfo(BaseModel):
    filename: str
    chunks: int
