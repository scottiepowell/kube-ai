import csv
import os
import sys
import re
import json
import textwrap
from pathlib import Path
import tiktoken

from autogen import AssistantAgent, UserProxyAgent
from autogen.llm_config import LLMConfig
from autogen.oai.ollama import OllamaLLMConfigEntry
from .ollama_helper import wait_for_server

sys.path.insert(0, str(Path(__file__).parent))

TEMPLATE_PATH = Path(__file__).parent / "templates" / "MDMP_ghost_website.csv"

# ---------------------------------------------------------------------
# Tokenizer trim settings for Ollama
# ---------------------------------------------------------------------
TOKEN_CEILING = 350
enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

def last_n_tokens(txt: str, limit: int = TOKEN_CEILING) -> str:
    ids = enc.encode(txt)
    trimmed = ids[-limit:]
    return enc.decode(trimmed)

# ---------------------------------------------------------------------
# Format validators
# ---------------------------------------------------------------------
JSON_RE = re.compile(r'^\s*\{.*\}\s*$', re.S)
YAML_END_RE = re.compile(r'---END---\s*$')

def _looks_valid(reply: str, expect_json: bool) -> bool:
    if expect_json:
        return JSON_RE.match(reply) is not None
    return YAML_END_RE.search(reply) is not None

# ---------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------
def load_steps(path: Path):
    steps = []
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        for row in reader:
            steps.append((
                row.get("MDMP Step", "Supporting").strip(),
                row["Agent"].strip(),
                row["Prompt Template"].strip(),
            ))
    return steps

# ---------------------------------------------------------------------
# Agent builder
# ---------------------------------------------------------------------
def build_agents():
    url = wait_for_server()
    model = os.getenv("SMALL_MODEL", "tinyllama:1.1b")
    entry = OllamaLLMConfigEntry(
        model=model,
        api_key="ollama",
        client_host=url,
        max_tokens=350,
        temperature=0.1,
    )
    cfg = LLMConfig(config_list=[entry])
    assistant = AssistantAgent("ops-assistant", llm_config=cfg, human_input_mode="NEVER")
    user = UserProxyAgent("user", human_input_mode="NEVER")
    return assistant, user

# ---------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------
def run_workflow():
    assistant, user = build_agents()
    prev = ""

    for step, agent, template in load_steps(TEMPLATE_PATH):
        expect_json = step.startswith("1")

        # Truncate & tag prior result
        prev_block = textwrap.dedent(f"""\
        ## Previous-Step-Output
        {last_n_tokens(prev)}
        ## End-Prev
        """)
        full_prompt = template.replace("<PREV>", prev_block)

        user.initiate_chat(
            assistant,
            message=full_prompt,
            max_turns=2,
            stop_when_reply=True
        )
        reply = assistant.last_message()["content"]

        # Retry on bad format
        if not _looks_valid(reply, expect_json):
            assistant.update_system_message(
                "ONLY output the requested artefact – nothing else!"
            )
            user.initiate_chat(
                assistant,
                message=full_prompt,
                max_turns=2,
                stop_when_reply=True
            )
            reply = assistant.last_message()["content"]

        print(f"\n### {step}\n{reply}\n")
        prev = reply

# ---------------------------------------------------------------------
# Optional: validator callback (not used in CLI run)
# ---------------------------------------------------------------------
def yaml_only_checker(recipient, _msgs, sender, _config):
    if sender != recipient:
        return False, None

    reply = _msgs[-1]["content"].strip()
    ok_format = reply.endswith("---END---") and not reply.startswith("```")
    if ok_format:
        return False, None

    hint = (
        "FORMAT ERROR – Reply with **one** YAML/JSON block only, "
        "no markdown fences, end with ---END---."
    )
    return True, hint

# ---------------------------------------------------------------------
if __name__ == "__main__":
    run_workflow()