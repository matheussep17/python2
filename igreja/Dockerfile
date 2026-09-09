FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Instala dependencias primeiro para aproveitar o cache de layers do Docker
# quando apenas o codigo da aplicacao mudar.
COPY licensing_server/requirements.txt /app/licensing_server/requirements.txt
RUN pip install --no-cache-dir -r /app/licensing_server/requirements.txt

COPY . /app

# Executa como usuario nao-root por seguranca.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/licensing_server/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os,sys; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=3).read()" || exit 1

CMD ["sh", "-c", "uvicorn licensing_server.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
