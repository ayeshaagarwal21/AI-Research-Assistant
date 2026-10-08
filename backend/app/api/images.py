import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from backend.app.core import config
from backend.app.core.dependencies import get_current_user
from backend.app.services.image_service import ImageGenerationError, generate_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["images"])

_recent = defaultdict(list)  # user_id -> request timestamps (in memory; resets on restart)


def _check_rate_limit(user_id: int) -> None:
    now = time.time()
    _recent[user_id] = [t for t in _recent[user_id] if now - t < 3600]
    if len(_recent[user_id]) >= config.IMAGE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429, detail="Image limit reached. Try again later.")
    _recent[user_id].append(now)


class ImageRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=500)


@router.post("/generate")
def generate(request: ImageRequest, current_user: dict = Depends(get_current_user)):
    _check_rate_limit(current_user["id"])
    try:
        image, mime = generate_image(request.prompt.strip())
    except ImageGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Image generation failed")
        raise HTTPException(
            status_code=502,
            detail="Image generation failed. Your API key may not have image access.",
        )
    return Response(content=image, media_type=mime)
