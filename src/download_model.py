#!/usr/bin/env python3
"""Download optional local model (llama.cpp binary + GGUF) for zero-token inference."""

import os
import sys
import urllib.request
import tarfile
import shutil

BIN_DIR = "/app/bin"
MODEL_DIR = "/app/models"

os.makedirs(BIN_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

ok = True

# 1. llama.cpp pre-compiled binary
try:
    print("Downloading llama.cpp binary...")
    url = "https://github.com/ggml-org/llama.cpp/releases/download/b9969/llama-b9969-bin-ubuntu-x64.tar.gz"
    urllib.request.urlretrieve(url, "/tmp/llama.tar.gz")
    with tarfile.open("/tmp/llama.tar.gz") as tf:
        import re

        members = [m for m in tf.getmembers() if not m.isdir()]
        for m in members:
            tf.extract(m, BIN_DIR)
        # Find and rename the binary to llama-cli
        for root_dir, dirs, files in os.walk(BIN_DIR):
            for f in files:
                if f in ("main", "llama-cli", "llama_inference"):
                    src = os.path.join(root_dir, f)
                    dst = os.path.join(BIN_DIR, "llama-cli")
                    if src != dst:
                        import shutil

                        shutil.copy2(src, dst)
                    os.chmod(dst, 0o755)
                    print(f"llama-cli ready (from {f})")
                    break
    os.remove("/tmp/llama.tar.gz")
except Exception as e:
    print(f"llama-cli download failed: {e}", file=sys.stderr)
    ok = False

# 2. GGUF model (~1GB)
try:
    print("Downloading Qwen2.5-1.5B GGUF model (~1GB, may take a few minutes)...")
    from huggingface_hub import hf_hub_download

    hf_hub_download(
        repo_id="Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        filename="qwen2.5-1.5b-instruct-q4_k_m.gguf",
        local_dir=MODEL_DIR,
    )
    print(
        f"Model ready: {os.path.join(MODEL_DIR, 'qwen2.5-1.5b-instruct-q4_k_m.gguf')}"
    )
except Exception as e:
    print(f"Model download failed: {e}", file=sys.stderr)
    ok = False

if ok:
    print("Local model setup complete — zero-token inference available")
else:
    print("Local model not available — will use API fallback", file=sys.stderr)

sys.exit(0)  # Non-blocking: always exit 0
