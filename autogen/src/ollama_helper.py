import os
import time
import requests


DEFAULT_URL = "http://127.0.0.1:11434"


def wait_for_server(url: str | None = None, timeout: float = 30.0) -> str:
    """Return the Ollama URL after verifying the server responds.

    Parameters
    ----------
    url : str, optional
        Base URL to probe. Defaults to the ``OLLAMA_URL`` env variable or
        ``DEFAULT_URL`` if unset.
    timeout : float
        Seconds to wait before giving up.

    Raises
    ------
    RuntimeError
        If the server is unreachable within ``timeout`` seconds.
    """
    url = url or os.getenv("OLLAMA_URL", DEFAULT_URL)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{url}/api/tags", timeout=3)
            if r.ok:
                return url
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(f"Ollama server not reachable at {url}")


if __name__ == "__main__":
    print("Ollama URL:", wait_for_server())
