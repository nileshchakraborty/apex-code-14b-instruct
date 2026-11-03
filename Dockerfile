# Multi-Stage Dockerfile for ApexCode-36GB
# Combines pre-optimized llama-server with Python runtime for isolated execution

# Stage 1: Official optimized llama.cpp server binary
FROM ghcr.io/ggerganov/llama.cpp:server AS llama-bin

# Stage 2: Application & Runtime Environment
FROM python:3.11-slim

LABEL maintainer="Nilesh Chakraborty <nileshchakraborty@gmail.com>"
LABEL description="ApexCode-36GB Isolated Containerized Inference & Tooling"

# Install system dependencies and health check tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libgomp1 \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy llama-server and dependencies from Stage 1
COPY --from=llama-bin /llama-server /usr/local/bin/llama-server
COPY --from=llama-bin /lib /lib-extra
ENV LD_LIBRARY_PATH="/lib-extra:$LD_LIBRARY_PATH"

# Create application workspace & non-root user
WORKDIR /app
RUN useradd -m -u 1000 apexuser && chown -R apexuser:apexuser /app

# Install Python project dependencies
COPY --chown=apexuser:apexuser pyproject.toml /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir psutil httpx requests rich typer pydantic

# Copy scripts and configs
COPY --chown=apexuser:apexuser scripts /app/scripts
COPY --chown=apexuser:apexuser configs /app/configs
COPY --chown=apexuser:apexuser training /app/training
COPY --chown=apexuser:apexuser docs /app/docs

USER apexuser

# Model and dataset mount points
VOLUME ["/app/models", "/app/datasets"]

# Health check to ensure the OpenAI-compatible endpoint is responsive
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://127.0.0.1:8080/health || exit 1

EXPOSE 8080

# Default entrypoint starts the speculative inference server
ENTRYPOINT ["python3", "scripts/run_speculative_server.py"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
