import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()

SERVER_DIR = Path(__file__).resolve().parent
BLOGS_DIR = SERVER_DIR / "blogs"
BLOGS_DIR.mkdir(parents=True, exist_ok=True)
OLLAMA_URL = os.getenv("OLLAMA_URL")
LLM_MODEL = os.getenv("LLM_MODEL")
# DATABASE_URI = os.getenv("DATABASE_URI")
# TOKENIZER_NAME = os.getenv("TOKENIZER_NAME")

#Configurations for implementing SHORT TERM MEMORY 

#WINDOW = 2048                          # depends on the model and the hardware running it
#BUDGET = int(WINDOW * 0.75)             # history allowance (the 75% you chose)
#TRIM_THRESHOLD = int(BUDGET * 0.90)     # trim once history crosses 90% of budget
#KEEP_TARGET = int(BUDGET * 0.25)        # keep ~25% of budget as recent verbatim
# tool definitions also live in the window every turn. If your tool
# schemas are large, shave the 0.75 down a little so they fit in the other 25%
# alongside the system prompt, the model's output, and the next user message