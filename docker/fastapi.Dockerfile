FROM python:3.12-slim

WORKDIR /app

# Install minimal build tools for some Python deps
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dependency layer (cached unless requirements change)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code layer
COPY apps/backend/fastapi/ ./backend/
COPY lib/ ./lib/

EXPOSE 8000

# Run as non-root
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

CMD ["uvicorn", "server:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "8000"]
