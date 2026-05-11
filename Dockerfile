# Zeiterfassung — Flask + SQLite
# Persistenz: Host-Verzeichnis nach /app/instance mounten.
# Konfiguration: SECRET_KEY MUSS per Environment gesetzt werden.
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Service-User früh anlegen (für --chown bei COPY).
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

# Erst Requirements, damit pip-Layer beim Code-Update gecached bleibt.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App-Quellen (gefiltert durch .dockerignore).
COPY --chown=appuser:appuser . .

# Instance-Verzeichnis vorbereiten und Entrypoint ausführbar machen.
RUN mkdir -p /app/instance \
 && chown -R appuser:appuser /app/instance \
 && chmod 0755 /app/docker-entrypoint.sh

USER appuser

EXPOSE 8000

# Healthcheck: Index-Route ist anonym erreichbar und antwortet immer mit 200.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3).status==200 else 1)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# SQLite: nur ein Worker-Prozess; Threads sind unkritisch für Locks.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "app:app"]
