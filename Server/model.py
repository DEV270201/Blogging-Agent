from langchain_ollama import ChatOllama

from Server.config import LLM_MODEL
# from Server.tools import tools

llm = ChatOllama(model=LLM_MODEL, temperature=0)
# llm_with_tools = llm.bind_tools(tools)