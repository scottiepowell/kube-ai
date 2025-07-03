import os
import time
import asyncio
import json
import logging
from contextlib import asynccontextmanager

import psutil
import httpx                                   # <-- only for first-token timer
from fastapi import FastAPI, Body, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from autogen import AssistantAgent, UserProxyAgent
from autogen.llm_config import LLMConfig
from autogen.oai.ollama import OllamaLLMConfigEntry

# --------------------------------------------------------------------------- #
# ENV
# --------------------------------------------------------------------------- #
BIG_MODEL  = os.getenv("BIG_MODEL",  "mistral:7b-instruct-q4_K_M")
SMALL_MODEL = os.getenv("SMALL_MODEL", "tinyllama:1.1b")
BIG_MODEL_RAM_GIB   = float(os.getenv("BIG_MODEL_RAM_GIB",   "2.5"))
SMALL_MODEL_RAM_GIB = float(os.getenv("SMALL_MODEL_RAM_GIB", "1.0"))

TIMEOUT_SECONDS            = float(os.getenv("LLM_TIMEOUT",            "60"))
FALLBACK_THRESHOLD_SECONDS = float(os.getenv("LLM_FALLBACK_THRESHOLD", "20"))

OLLAMA_HOST = os.getenv("OLLAMA_URL", "http://ollama:11434")

ENABLE_CODE_EXEC = os.getenv("ENABLE_CODE_EXEC", "true").lower() == "true"
LOG_LEVEL        = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format="%(message)s")

# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
REQ_LAT = Histogram("llm_request_latency_seconds", "Time spent in /ask")
REQ_CNT = Counter("llm_requests_total",           "Number of /ask calls", ["success"])
MODEL_SWITCHES = Counter("llm_model_switch_total","LLM model switches")

# --------------------------------------------------------------------------- #
def free_ram_gib() -> float:
    return psutil.virtual_memory().available / 1024**3


# --------------------------------------------------------------------------- #
class AppServer:
    def __init__(self):
        self._current_model = self._select_model()
        self._assistant, self._user = self._build_agents(self._current_model)

        self.app = FastAPI(lifespan=self._lifespan)
        self._wire_routes()

    # ------------------------------------------------------------------ #
    # Agent factory
    # ------------------------------------------------------------------ #
    def _build_agents(self, model: str):
        entry = OllamaLLMConfigEntry(model=model, api_key="ollama", client_host=OLLAMA_HOST)
        cfg = LLMConfig(config_list=[entry], temperature=0.2)

        code_cfg = {} if ENABLE_CODE_EXEC else False
        assistant = AssistantAgent(
            "ops-assistant",
            llm_config=cfg,
            human_input_mode="NEVER",
            code_execution_config=code_cfg,
        )
        user = UserProxyAgent("user", human_input_mode="NEVER")
        return assistant, user

    # ------------------------------------------------------------------ #
    # RAM-based chooser
    # ------------------------------------------------------------------ #
    def _select_model(self) -> str:
        ram = free_ram_gib()
        if ram >= BIG_MODEL_RAM_GIB:
            return BIG_MODEL
        if ram >= SMALL_MODEL_RAM_GIB:
            return SMALL_MODEL
        raise RuntimeError(
            f"Insufficient RAM ({ram:.2f} GiB) — need ≥{SMALL_MODEL_RAM_GIB} GiB."
        )

    # ------------------------------------------------------------------ #
    @asynccontextmanager
    async def _lifespan(self, _: FastAPI):
        yield

    # ------------------------------------------------------------------ #
    # Routes
    # ------------------------------------------------------------------ #
    def _wire_routes(self):
        @self.app.post("/ask")
        async def ask(request: Request, question: str = Body(..., embed=True)):
            phases = {
                "start": time.time(),
                "model": self._current_model,
                "ram_before": free_ram_gib(),
            }

            try:
                answer = await self._run_chat(question, phases)
                latency = time.time() - phases["start"]
                phases["ram_after"] = free_ram_gib()

                REQ_LAT.observe(latency)
                REQ_CNT.labels(success="true").inc()
                logging.debug(json.dumps({**phases, "status": "ok"}))

                resp = {"answer": answer, "latency": latency, "model": self._current_model}
                if request.query_params.get("debug") == "true":
                    resp["phases"] = phases
                return resp

            except asyncio.TimeoutError:
                REQ_CNT.labels(success="false").inc()
                phases["status"] = "timeout"
                logging.error(json.dumps(phases))
                raise HTTPException(504, detail="LLM request timed out", headers={"X-Phases": json.dumps(phases)})

            except MemoryError as e:
                REQ_CNT.labels(success="false").inc()
                phases["status"] = "ram_error"
                logging.error(json.dumps({**phases, "error": str(e)}))
                raise HTTPException(503, detail=str(e))

        @self.app.get("/healthz")
        async def health():
            return {"status": "ok", "model": self._current_model, "free_ram_gib": free_ram_gib()}

        @self.app.get("/metrics")
        async def metrics():
            return JSONResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # ------------------------------------------------------------------ #
    async def _run_chat(self, question: str, phases: dict):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._sync_chat, question, phases),
                timeout=TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            phases["timeout"] = time.time()

            if self._current_model == BIG_MODEL:
                self._switch_to_small(phases)          # ↓ defined below
                MODEL_SWITCHES.inc()

                return await asyncio.wait_for(
                    asyncio.to_thread(self._sync_chat, question, phases),
                    timeout=TIMEOUT_SECONDS,
                )
            raise
    
    def _switch_to_small(self, phases: dict) -> None:
        """Down-size to SMALL_MODEL unconditionally and log it."""
        self._current_model = SMALL_MODEL
        self._assistant, self._user = self._build_agents(SMALL_MODEL)
        phases["model_switched"] = SMALL_MODEL
        logging.info(json.dumps({**phases, "event": "forced big→small on timeout"}))

    """
    # This is an alternative to the _switch_to_small() method above.
    # It checks RAM before switching models, but it is not used in the current implementation.
    def _maybe_switch_model(self, phases: dict) -> bool:
        ram = free_ram_gib()
        phases["ram_check"] = ram
        if self._current_model == BIG_MODEL and ram < BIG_MODEL_RAM_GIB:
            self._current_model = SMALL_MODEL
            self._assistant, self._user = self._build_agents(self._current_model)
            phases["model_switched"] = self._current_model
            logging.info(json.dumps({**phases, "event": "big→small"}))
            return True
        return False"""

    # ------------------------------------------------------------------ #
    def _sync_chat(self, question: str, phases: dict) -> str:
        phases["chat_start"] = time.time()

        # --- first-token timer via low-level HTTP call --------------
        first_token_at = None
        def _capture_first_chunk(resp: httpx.Response):
            nonlocal first_token_at
            first_token_at = time.time()

        # inject event-hook into httpx used by ollama
        import autogen.oai.ollama as oai_ollama
        oai_ollama._client_event_hooks = {"response": [_capture_first_chunk]}  # type: ignore

        self._user.initiate_chat(self._assistant, message=question)

        phases["first_token"] = first_token_at or phases["chat_start"]
        phases["chat_end"]   = time.time()
        return self._assistant.last_message()["content"]


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
app = FastAPI()
try:
    app = AppServer().app
except RuntimeError as e:
    error_message = str(e)
    app = FastAPI()

    @app.get("/healthz")
    def healthz():
        return {"error": error_message}
else:
    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}
