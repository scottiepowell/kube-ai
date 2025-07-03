import json, time, pathlib, requests, pytest

OLLAMA = "http://127.0.0.1:11434/api/generate"
PROMPTS = pathlib.Path(__file__).parent / "prompts"

MODELS = [
    ("qwen2.5:0.5b", 3.0),        # (model, max_seconds)
    ("tinyllama:1.1b", 5.0),
    ("smollm:1.7b",   8.0),
]

@pytest.mark.parametrize("model,max_s", MODELS)
@pytest.mark.parametrize("prompt_file", ["health.txt", "decision.txt"])
def test_latency(model, max_s, prompt_file):
    prompt = (PROMPTS / prompt_file).read_text()

    t0 = time.time()
    r = requests.post(
        OLLAMA,
        headers={"Content-Type": "application/json"},
        data=json.dumps({"model": model, "prompt": prompt, "stream": False}),
        timeout=max_s + 60,        # network safety
    )
    elapsed = time.time() - t0
    answer  = r.json().get("response", "")[:120]

    print(f"\n{prompt_file} | {model} | {elapsed:.2f}s | {answer!r}")
    assert elapsed <= max_s, f"{model} took {elapsed:.2f}s (> {max_s}s)"
