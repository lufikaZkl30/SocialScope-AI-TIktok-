"""Central configuration, read from environment variables (see .env.example)."""
import os
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
    TIKTOK_API_ACCESS_TOKEN = os.getenv("TIKTOK_API_ACCESS_TOKEN", "")
    VERSION = "1.0.0"
