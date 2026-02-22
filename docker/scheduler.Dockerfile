FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dependency layer (cached unless requirements change)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code layer
COPY lib/ ./lib/
COPY src/ ./src/
COPY ml/ ./ml/

ENV PYTHONPATH=/app

CMD ["python", "-m", "src.main"]
