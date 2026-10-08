import logging

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from backend.app.core.dependencies import get_current_user
from backend.app.services.voice_service import speech_to_text, text_to_mp3

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


@router.post("/speak")
def speak(request: SpeakRequest, current_user: dict = Depends(get_current_user)):
    """Text -> MP3 audio."""
    try:
        audio = text_to_mp3(request.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Text-to-speech failed")
        raise HTTPException(
            status_code=502,
            detail="Text-to-speech failed. Check your internet connection and that gTTS is installed.",
        )
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/transcribe")
def transcribe(
    audio: UploadFile = File(...), current_user: dict = Depends(get_current_user)
):
    """WAV audio -> text."""
    data = audio.file.read()
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio is too large (max 10 MB)")
    try:
        text = speech_to_text(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Speech recognition failed")
        raise HTTPException(
            status_code=502,
            detail="Speech recognition failed. Check your internet connection and that SpeechRecognition is installed.",
        )
    return {"text": text}
