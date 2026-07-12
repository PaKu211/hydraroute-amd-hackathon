# HydraRoute Agent - AMD Developer Hackathon ACT II
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/
RUN mkdir -p /input /output /app/models /app/bin

# Try to install optional local model (zero tokens). Failure → no local model, API fallback
RUN pip install huggingface-hub -q 2>/dev/null
RUN python scripts/download_local_model.py 2>&1 || echo "Local model download skipped"

RUN python -c "import src.config; import src.cache; import src.router; print('Health check: OK')"
CMD ["python", "-m", "src.main"]
