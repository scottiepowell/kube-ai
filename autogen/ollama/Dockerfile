# ── Stage 1: pull the model ─────────────────────────
FROM ollama/ollama:latest AS builder

RUN bash -lc "\
    ollama serve --cors '*' & \
    PID=\$! && \
    sleep 10 && \
    ollama pull mistral:7b-instruct && \
    kill \"\$PID\" \
"

# ── Stage 2: final image ────────────────────────────
FROM ollama/ollama:latest

# Copy only the model data from the builder
COPY --from=builder /root/.ollama /root/.ollama

EXPOSE 11434

CMD ["ollama", "serve", "--cors", "*"]