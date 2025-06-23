# ./autogen/Dockerfile
FROM python:3.11-slim

# system deps for llama-cpp & Ollama client if you later build wheels
RUN apt-get update && apt-get install -y git build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY configs/ ./configs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src
CMD ["python", "-m", "src.server"]      # FastAPI / Flask entrypoint

# Use uvicorn to serve the FastAPI app on 0.0.0.0:8000
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000"]