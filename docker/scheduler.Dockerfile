FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY lib/ ./lib/
COPY src/ ./src/
COPY ml/ ./ml/

ENV PYTHONPATH=/app

CMD ["python", "-m", "src.main"]
