import csv
import os
from pathlib import Path

from autogen import AssistantAgent, UserProxyAgent
from autogen.llm_config import LLMConfig
from autogen.oai.ollama import OllamaLLMConfigEntry
from .ollama_helper import wait_for_server

TEMPLATE_PATH = Path(__file__).parent / "templates" / "MDMP_ghost_website.csv"


def load_steps(path: Path):
    """Return a list of (step, agent_task, outputs) tuples."""
    steps = []
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            step = row["MDMP Step"].strip() or "Supporting"
            task = row["AI Agent & Core Task"].strip()
            outputs = row["Key Outputs / Checks"].strip()
            steps.append((step, task, outputs))
    return steps


def build_agents():
    url = wait_for_server()
    model = os.getenv("SMALL_MODEL", "tinyllama:1.1b")
    entry = OllamaLLMConfigEntry(
        model=model,
        api_key="ollama",
        client_host=url,
    )
    llm_cfg = LLMConfig(config_list=[entry], temperature=0.2)
    assistant = AssistantAgent("ops-assistant", llm_config=llm_cfg, human_input_mode="NEVER")
    user = UserProxyAgent("user", human_input_mode="NEVER")
    return assistant, user


def run_workflow():
    assistant, user = build_agents()
    for step, task, outputs in load_steps(TEMPLATE_PATH):
        prompt = (
            f"Step: {step}\n"
            f"Role: {task}\n"
            f"Goal: {outputs}\n"
            "Provide your recommended actions or manifests."
        )
        user.initiate_chat(assistant, message=prompt)
        print(f"\n=== {step} ===")
        print(assistant.last_message()["content"])  # raw LLM response
        print()


if __name__ == "__main__":
    run_workflow()
