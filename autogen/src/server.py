import os
from fastapi import FastAPI, Body
from autogen import AssistantAgent, UserProxyAgent
from autogen.oai.ollama import OllamaLLMConfigEntry   # entry-level class
from autogen.llm_config import LLMConfig              # top-level wrapper

# client_host now points at root, so requests end up at /api/chat
ollama_entry = OllamaLLMConfigEntry(
    model="mistral:7b-instruct-q4_0",
    api_key="ollama",
    client_host=os.getenv("OLLAMA_URL"),
)

# Wrap into the top-level config
llm_config = LLMConfig(
    config_list=[ollama_entry],
    temperature=0.2,
)

assistant = AssistantAgent(
    "ops-assistant",
    llm_config=llm_config,
    human_input_mode="NEVER",
)

user = UserProxyAgent(
    "user",
    human_input_mode="NEVER",   # ← add this
)

app       = FastAPI()

@app.post("/ask")
async def ask(question: str = Body(..., embed=True)):
    user.initiate_chat(assistant, message=question)
    return {"answer": assistant.last_message()["content"]}