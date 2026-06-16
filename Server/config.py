import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# The nodes log progress with print(). On Windows the console defaults to cp1252,
# which raises UnicodeEncodeError on emoji/unicode in research snippets or sections —
# that would silently drop search results or crash a worker mid-job. Make the
# standard streams encode defensively so logging can never break generation.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SERVER_DIR = Path(__file__).resolve().parent
load_dotenv(SERVER_DIR.parent / ".env")
# load_dotenv(SERVER_DIR / ".env")

BLOGS_DIR = SERVER_DIR / "blogs"
BLOGS_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_URL = os.getenv("OLLAMA_URL")
LLM_MODEL = os.getenv("LLM_MODEL")
DATABASE_URI = os.getenv("DATABASE_URI")
POOL_MIN_SIZE = int(os.getenv("POOL_MIN_SIZE", "1"))
POOL_MAX_SIZE = int(os.getenv("POOL_MAX_SIZE", "10"))

# --- API server settings ---
# Number of blog-generation jobs that may run concurrently in the API process.
API_MAX_WORKERS = int(os.getenv("API_MAX_WORKERS", "4"))
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
# Comma-separated list of origins allowed by CORS (the React client).
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")
    if origin.strip()
]
