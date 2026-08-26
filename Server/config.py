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
# Seconds before an Ollama HTTP call is considered hung and raises a timeout error.
# Size this generously for large models — a 14B model cold-start can take 60-120s.
OLLAMA_REQUEST_TIMEOUT = int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "180"))

for _var, _val in (("LLM_MODEL", LLM_MODEL), ("DATABASE_URI", DATABASE_URI)):
    if not _val:
        raise RuntimeError(f"{_var} is not set in the environment. Add it to .env.")
POOL_MIN_SIZE = int(os.getenv("POOL_MIN_SIZE", "1"))
POOL_MAX_SIZE = int(os.getenv("POOL_MAX_SIZE", "10"))

# --- Human-in-the-loop research review ---
# When research coverage comes back weak (partial/insufficient) the graph pauses
# and asks the user whether to proceed or re-research. This caps how many
# user-triggered re-research rounds are allowed before the agent auto-proceeds
# with whatever evidence exists, so a job can never loop forever.
RESEARCH_RETRY_CAP = int(os.getenv("RESEARCH_RETRY_CAP", "2"))

# --- API server settings ---
# Number of blog-generation jobs that may run concurrently in the API process.
API_MAX_WORKERS = int(os.getenv("API_MAX_WORKERS", "4"))
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# --- Job lease / heartbeat settings ---
# A running worker refreshes its job's heartbeat on this cadence; if a job goes
# LEASE_TIMEOUT seconds without a heartbeat it is considered orphaned (its owner
# crashed) and is reclaimed. LEASE_TIMEOUT must be comfortably larger than the
# heartbeat interval (~8x) so a few missed beats never falsely expire a live job.
JOB_HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("JOB_HEARTBEAT_INTERVAL_SECONDS", "10"))
JOB_LEASE_TIMEOUT_SECONDS = int(os.getenv("JOB_LEASE_TIMEOUT_SECONDS", "120"))
# How often the background sweeper scans for orphaned (expired-lease) jobs.
JOB_SWEEP_INTERVAL_SECONDS = int(os.getenv("JOB_SWEEP_INTERVAL_SECONDS", "30"))
# Comma-separated list of origins allowed by CORS (the React client).
_cors_raw = os.getenv("CORS_ORIGINS")
if not _cors_raw:
    raise RuntimeError("CORS_ORIGINS is not set in the environment. Add it to .env.")
CORS_ORIGINS = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]
