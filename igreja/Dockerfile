FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY . /app

RUN pip install --no-cache-dir -r /app/licensing_server/requirements.txt

CMD ["sh", "-c", "uvicorn licensing_server.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
