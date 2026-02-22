FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dependency layer (cached unless worker requirements change)
COPY apps/worker/requirements.txt ./requirements.txt
RUN uv pip install --system --no-cache -r requirements.txt

# App code layer
RUN mkdir -p ./worker/
COPY apps/worker/ ./worker/
COPY src/ ./src/
COPY lib/ ./lib/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import redis; r=redis.from_url('redis://redis:6379'); r.ping()" || exit 1


# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app
CMD ["celery", "-A", "worker.worker:app", "worker", "--loglevel=info"]
