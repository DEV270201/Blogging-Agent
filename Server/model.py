from langchain_ollama import ChatOllama

from Server.config import LLM_MODEL, OLLAMA_REQUEST_TIMEOUT, OLLAMA_URL

if not OLLAMA_URL:
    raise RuntimeError("OLLAMA_URL is not set in the environment. Add it to .env.")

llm = ChatOllama(
    model=LLM_MODEL,
    base_url=OLLAMA_URL,
    temperature=0,
    request_timeout=OLLAMA_REQUEST_TIMEOUT,
)