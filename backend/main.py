import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.auth import router as auth_router
from backend.app.api.admin import router as admin_router
from backend.app.api.chat import router as chat_router
from backend.app.api.history import router as history_router
from backend.app.api.images import router as images_router
from backend.app.api.upload import router as upload_router
from backend.app.api.vision import router as vision_router
from backend.app.api.voice import router as voice_router
from backend.app.db.database import init_db

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # creates the SQLite tables on first run
    yield


app = FastAPI(
    title="AI Research Assistant API",
    description="Upload PDFs and chat with them using Retrieval-Augmented Generation.",
    version="5.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(upload_router)
app.include_router(chat_router)
app.include_router(history_router)
app.include_router(voice_router)
app.include_router(images_router)
app.include_router(vision_router)


@app.get("/")
def home():
    return {"message": "Welcome to AI Research Assistant API 🚀"}


@app.get("/health")
def health():
    return {"status": "ok"}
