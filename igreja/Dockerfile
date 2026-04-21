FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY licensing_server/requirements.txt /app/licensing_server/requirements.txt
RUN pip install --no-cache-dir -r /app/licensing_server/requirements.txt

COPY . /app

CMD ["sh", "-c", "uvicorn licensing_server.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
