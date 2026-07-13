import json, os, time, subprocess, sys, signal, argparse
from datetime import datetime

E3_DIR = "/tmp/e3"
BENCH = os.path.join(E3_DIR, "benchmark.json")
RESULTS = os.path.join(E3_DIR, "e3_{model_tag}.json")


def log(msg):
    ts = datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def wait_for_server(base_url, timeout=600):
    import urllib.request

    # vLLM OpenAI server health is at /health (not /v1/health)
    health = base_url.replace("/v1", "").rstrip("/") + "/health"
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(health, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def run_bench(model_tag, model_id, port, tensor_parallel):
    from openai import OpenAI

    base_url = f"http://localhost:{port}/v1"
    # launch server
    cmd = [
        sys.executable,
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        model_id,
        "--port",
        str(port),
        "--tensor-parallel-size",
        str(tensor_parallel),
        "--max-model-len",
        "4096",
        "--gpu-memory-utilization",
        "0.90",
    ]
    log(f"launching vLLM server for {model_id} on port {port}")
    proc = subprocess.Popen(
        cmd,
        stdout=open(f"{E3_DIR}/vllm_{model_tag}.log", "ab"),
        stderr=subprocess.STDOUT,
    )
    if not wait_for_server(base_url, timeout=600):
        log("server failed to start; tail log:")
        os.system(f"tail -20 {E3_DIR}/vllm_{model_tag}.log")
        proc.terminate()
        return None
    log("server ready")
    client = OpenAI(base_url=base_url, api_key="x")
    tasks = json.load(open(BENCH))
    records = []
    t_start = time.time()
    for i, t in enumerate(tasks):
        prompt = t["instruction"]
        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
                temperature=0.0,
            )
            tt = time.time() - t0
            usage = resp.usage
            rec = {
                "task_id": t["task_id"],
                "category": t["category"],
                "latency_s": round(tt, 4),
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "output_chars": len(resp.choices[0].message.content or ""),
            }
        except Exception as e:
            rec = {
                "task_id": t["task_id"],
                "category": t["category"],
                "error": str(e)[:200],
            }
        records.append(rec)
        if (i + 1) % 10 == 0:
            log(f"  {i + 1}/{len(tasks)} done")
    t_total = time.time() - t_start
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except Exception:
        proc.kill()
    # aggregate
    ok = [r for r in records if "error" not in r]
    agg = {
        "model_tag": model_tag,
        "model_id": model_id,
        "n_tasks": len(tasks),
        "n_ok": len(ok),
        "total_wall_s": round(t_total, 2),
        "sum_latency_s": round(sum(r["latency_s"] for r in ok), 2),
        "mean_latency_s": round(sum(r["latency_s"] for r in ok) / len(ok), 4)
        if ok
        else None,
        "p50_latency_s": None,
        "p95_latency_s": None,
        "sum_prompt_tokens": sum(r["prompt_tokens"] for r in ok),
        "sum_completion_tokens": sum(r["completion_tokens"] for r in ok),
        "sum_total_tokens": sum(r["total_tokens"] for r in ok),
        "throughput_tok_s": round(sum(r["total_tokens"] for r in ok) / t_total, 2)
        if t_total > 0
        else None,
        "completion_tok_s": round(sum(r["completion_tokens"] for r in ok) / t_total, 2)
        if t_total > 0
        else None,
    }
    if ok:
        lats = sorted(r["latency_s"] for r in ok)
        agg["p50_latency_s"] = round(lats[len(lats) // 2], 4)
        agg["p95_latency_s"] = round(lats[min(len(lats) - 1, int(len(lats) * 0.95))], 4)
    out = {"aggregate": agg, "records": records}
    out_path = RESULTS.format(model_tag=model_tag)
    json.dump(out, open(out_path, "w"), indent=2)
    log(f"saved {out_path}")
    log(
        f"mean_latency={agg['mean_latency_s']}s throughput={agg['throughput_tok_s']} tok/s"
    )
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-tag", required=True)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--tp", type=int, default=1)
    a = ap.parse_args()
    run_bench(a.model_tag, a.model_id, a.port, a.tp)
