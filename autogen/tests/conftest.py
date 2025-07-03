# tests/conftest.py
import json, time, requests, pytest
from pathlib import Path

# Re-use constants from the test file
try:
    from tests.test_latency import MODELS, OLLAMA
except ImportError:              # running inside the container
    from test_latency import MODELS, OLLAMA   # noqa: F401

@pytest.fixture(scope="session", autouse=True)
def warm_ollama_models():
    """
    One-time warm-up: hit /api/generate with a 1-token prompt so the
    weights & KV-cache are resident in RAM before the real tests run.
    """
    for model, _ in MODELS:
        print(f"[warm-up] loading {model} …", flush=True)
        t0 = time.time()
        requests.post(
            OLLAMA,
            headers={"Content-Type": "application/json"},
            data=json.dumps({"model": model,
                             "prompt": "ping",
                             "stream": False}),
            timeout=180,
        )
        print(f"[warm-up] {model} ready in {time.time() - t0:.2f}s",
              flush=True)
