# ApexCode-36GB Containerized Sandbox & Tooling
# Python 3.11 lightweight runtime for isolated benchmarks, dataset preparation, and evaluation

FROM python:3.11-slim

LABEL maintainer="Nilesh Chakraborty <nileshchakraborty@gmail.com>"
LABEL description="ApexCode-36GB Isolated Tooling & Sandbox Environment"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create application workspace & non-root user
WORKDIR /app
RUN useradd -m -u 1000 apexuser && chown -R apexuser:apexuser /app

# Install Python dependencies
COPY --chown=apexuser:apexuser pyproject.toml /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir psutil httpx requests rich typer pydantic

# Copy codebase
COPY --chown=apexuser:apexuser scripts /app/scripts
COPY --chown=apexuser:apexuser configs /app/configs
COPY --chown=apexuser:apexuser training /app/training
COPY --chown=apexuser:apexuser docs /app/docs

USER apexuser

VOLUME ["/app/models", "/app/datasets", "/app/logs"]

ENTRYPOINT ["python3", "scripts/benchmark_throughput.py"]
CMD ["--url", "http://host.docker.internal:11434", "--model", "apex-coder-14b"]
