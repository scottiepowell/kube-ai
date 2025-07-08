FROM python:3.11-slim AS builder
WORKDIR /wheels
COPY requirements.txt .
RUN pip wheel --extra-index-url https://download.pytorch.org/whl/cpu \
    --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH="/app:${PYTHONPATH}"
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
COPY src/ ./src
COPY tests/ ./tests
CMD ["uvicorn", "src.app_server:app","--reload","--host","0.0.0.0","--port","8000"]