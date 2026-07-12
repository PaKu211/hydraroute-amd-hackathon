# HydraRoute Agent - AMD Developer Hackathon ACT II
# Build: docker build --platform linux/amd64 -t hydraroute:latest .
# Run:   docker run --platform linux/amd64 \
#          -e FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
#          -e ALLOWED_MODELS=$ALLOWED_MODELS \
#          -v $(pwd)/input:/input -v $(pwd)/output:/output \
#          hydraroute:latest

FROM python:3.11-slim

# Set non-interactive mode
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install Python deps (no llama-cpp-python — use subprocess with pre-compiled llama.cpp binary)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Create output dir (will be overridden by volume mount)
RUN mkdir -p /input /output /app/models /app/llama.cpp

# Download pre-compiled llama.cpp binary (15MB, no compilation needed)
RUN apt-get update -qq && apt-get install -y -qq curl 2>/dev/null && rm -rf /var/lib/apt/lists/* && \
    curl -sL "https://github.com/ggml-org/llama.cpp/releases/download/b9969/llama-b9969-bin-ubuntu-x64.tar.gz" -o /tmp/llama.tar.gz && \
    tar -xzf /tmp/llama.tar.gz -C /app/llama.cpp && \
    chmod +x /app/llama.cpp/llama-cli && \
    rm /tmp/llama.tar.gz

# Download local GGUF model for zero-token inference (Qwen2.5 1.5B Q4_K_M ~1GB)
RUN pip install huggingface-hub -q && \
    python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Qwen/Qwen2.5-1.5B-Instruct-GGUF', filename='qwen2.5-1.5b-instruct-q4_k_m.gguf', local_dir='/app/models')"

# Health check - ensure python can import main (model not loaded yet)
RUN python -c "import src.config; import src.cache; import src.router; print('HydraRoute health check: OK')"

# Run the agent
CMD ["python", "-m", "src.main"]
