"""Central configuration.

Every setting is read from an environment variable (a `.env` file in the
project root is loaded automatically), so no secrets live in the source code.
"""
import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# backend/app/core/config.py -> project root is three levels up
BASE_DIR = Path(__file__).resolve().parents[3]
load_dotenv(BASE_DIR / ".env")

# ---- Auth -------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Fine for local development, but every restart logs everyone out.
    SECRET_KEY = secrets.token_urlsafe(48)
    logger.warning(
        "SECRET_KEY is not set in .env - using a temporary random key. "
        "Logins will be invalidated whenever the server restarts."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
# ---- Separate admin portal ---------------------------------------------
# These credentials are only for the standalone admin portal. They are never
# rendered in the normal user application.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", SECRET_KEY)
ADMIN_TOKEN_EXPIRE_MINUTES = int(os.getenv("ADMIN_TOKEN_EXPIRE_MINUTES", "120"))

# ---- Storage ----------------------------------------------------------
DB_PATH = Path(os.getenv("DATABASE_PATH", BASE_DIR / "data" / "app.db"))

# ---- LLM / retrieval --------------------------------------------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TOP_K = int(os.getenv("TOP_K", "4"))
HISTORY_MESSAGES_IN_PROMPT = int(os.getenv("HISTORY_MESSAGES_IN_PROMPT", "6"))

# ---- Uploads ----------------------------------------------------------
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))

# ---- Image generation -------------------------------------------------
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gemini-2.5-flash-image")
IMAGE_LIMIT_PER_HOUR = int(os.getenv("IMAGE_LIMIT_PER_HOUR", "10"))

# ---- Image questions (screenshots) -------------------------------------
MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB", "8"))
