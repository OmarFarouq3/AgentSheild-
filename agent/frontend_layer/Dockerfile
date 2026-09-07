FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY agent_layer ./agent_layer
COPY frontend_layer ./frontend_layer

EXPOSE 8002

CMD ["chainlit", "run", "frontend_layer/app/chainlit_app.py", "--host", "0.0.0.0", "--port", "8002"]
