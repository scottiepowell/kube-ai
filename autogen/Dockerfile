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

# Install bash, bash-completion, and set up history
RUN apt-get update && apt-get install -y bash bash-completion && \
    # Ensure interactive shell history works
    echo "export HISTFILE=/root/.bash_history" >> /etc/bash.bashrc && \
    echo "export HISTCONTROL=ignoredups:erasedups" >> /etc/bash.bashrc && \
    echo "shopt -s histappend" >> /etc/bash.bashrc && \
    # Enable bash completion
    echo "if [ -f /etc/bash_completion ]; then . /etc/bash_completion; fi" >> /etc/bash.bashrc

COPY src/ ./src
COPY tests/ ./tests
CMD ["uvicorn", "src.app_server:app","--reload","--app-dir", "/app","--host","0.0.0.0","--port","8000"]