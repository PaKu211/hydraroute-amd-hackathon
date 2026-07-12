# HydraRoute Agent - AMD Developer Hackathon ACT II
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

# System libraries for llama.cpp (libgomp for OpenMP)
RUN apt-get update -qq && apt-get install -y -qq libgomp1 2>/dev/null && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
RUN mkdir -p /input /output

# Optional: download local model for zero-token inference (non-blocking)
RUN pip install huggingface-hub -q 2>/dev/null && python src/download_model.py 2>&1 || echo "Local model not available — API fallback active"

RUN python -c "import src.config; import src.cache; import src.router; print('Health check: OK')"
CMD ["python", "-m", "src.main"]
