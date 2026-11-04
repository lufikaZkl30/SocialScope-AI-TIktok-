"""Central configuration, read from environment variables (see .env.example)."""
import os
import secrets
from dotenv import load_dotenv

load_dotenv()


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name, default):
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or secrets.token_urlsafe(32)
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    PORT = _int("PORT", 5000)
    CORS_ORIGINS = [o.strip() for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
    MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 5)
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    # Similarity is O(n^2) in the worst case; the cap keeps analysis safe on a laptop.
    MAX_ROWS = _int("MAX_ROWS", 5000)
    SIMILARITY_THRESHOLD = _float("SIMILARITY_THRESHOLD", 0.80)
    PROMO_KEYWORDS_PATH = os.getenv("PROMO_KEYWORDS_PATH", "")
    TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
    TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
    TIKTOK_REDIRECT_URI = os.getenv(
        "TIKTOK_REDIRECT_URI", "http://localhost:5173/api/tiktok/callback"
    ).strip()
    TIKTOK_FRONTEND_URL = os.getenv("TIKTOK_FRONTEND_URL", "http://localhost:5173").strip()
    VERSION = "1.0.0"
