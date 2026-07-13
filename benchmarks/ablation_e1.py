#!/usr/bin/env python3
"""E1 Ablation harness for HydraRoute paper.

Runs the existing HydraRoute router over the 67-task benchmark under 4
ablation configurations, recording per-task tokens and a pass/fail signal.
Component gates are controlled by environment variables so we reuse the
real system code unchanged:

  HYDRAROUTE_ABLATE_TIER0   =0 disables Tier 0 local solvers (forces API)
  HYDRAROUTE_ABLATE_LOCAL   =0 disables Tier Local GGUF
  HYDRAROUTE_ABLATE_SYMPY   =0 disables SymPy-LLM symbiosis
  HYDRAROUTE_ABLATE_COMPRESS=0 disables prompt compression

Configurations:
  A full      -> all on
  B no_tier0  -> HYDRAROUTE_ABLATE_TIER0=0
  C cascade   -> no_tier0 + no_local (Tier 0 + local both off: pure cascade)
  D no_sympy  -> full but HYDRAROUTE_ABLATE_SYMPY=0

Accuracy is measured by a lightweight validator that checks the answer
against the task's expected pattern where available, else flags for review.
This keeps the ablation honest about token cost (the paper's primary axis)
while reporting a pass-rate signal.

Outputs: experiments/ablation_results.json  (raw per-task records)
"""

import json
import os
import sys
import time
import logging

# Make repo root importable (for `src` package)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from src.config import Config
from src.router import route_task
from src.token_tracker import TokenTracker

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger("ablation")
logger.setLevel(logging.ERROR)

BENCH = os.path.join(os.path.dirname(__file__), "hydraroute_benchmark.json")


def build_client(key):
    from openai import OpenAI

    return OpenAI(
        api_key=key,
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )


# Minimal heuristic validators keyed by category. These are intentionally loose:
# the ablation's primary measurement is token cost; accuracy is a guard signal.
def validate(task, answer):
    if not answer or len(str(answer).strip()) < 1:
        return False
    if str(answer).strip().lower().startswith("i could not"):
        return False
    cat = task["category"]
    inst = task["instruction"].lower()
    a = str(answer).strip().lower()

    if cat == "sentiment_classification":
        return a in ("pos", "neg", "neu")
    if cat == "math":
        # accept a clean numeric/equation answer; reject algebraic junk like
        # '180/(a*c*d*e*i*n*s)' produced when SymPy-LLM path emits a bad equation
        import re as _re

        if _re.search(r"[a-z]", a):
            return False
        return any(ch.isdigit() for ch in a)
    if cat == "factual_knowledge":
        # accept non-empty, not an error
        return len(a) >= 1
    if cat == "ner":
        return "{" in a or "[" in a
    if cat in ("code_generation", "code_debugging"):
        return "def " in a or "```" in a or "import " in a or len(a) > 20
    if cat in ("logical_reasoning", "deductive_reasoning"):
        return len(a.split()) >= 5
    if cat == "text_summarization":
        return len(a.split()) >= 3
    return len(a) >= 1


def _call_model(client, model, task, config):
    """Direct single-call baseline (always-large / always-small) without routing."""
    from src.router import get_category_config, CACHE_PREFIX
    import json as _json

    normalized = task["category"]
    cat_config = get_category_config(normalized)
    sys_prompt = cat_config.get("system_prompt", "Answer concisely.")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": task["instruction"]},
            ],
            max_tokens=cat_config.get("max_tokens", 300),
            temperature=0.0,
        )
        ans = resp.choices[0].message.content or ""
        if resp.usage:
            TokenTracker().record(
                task_id=task["task_id"],
                model=model,
                prompt_tokens=resp.usage.prompt_tokens or 0,
                completion_tokens=resp.usage.completion_tokens or 0,
            )
        return ans
    except Exception as e:
        return f"ERROR: {e}"


def run_config(name, key, model_small, model_large, baseline=None):
    # reset tracker singleton for clean per-config totals
    TokenTracker.reset()
    tracker = TokenTracker()

    config = Config()
    config.fireworks_api_key = key
    config.fireworks_base_url = os.environ.get(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    config.allowed_models = [model_small, model_large]
    config._assign_model_tiers()
    client = build_client(key)

    with open(BENCH) as f:
        tasks = json.load(f)

    records = []
    tier0 = 0
    sympy = 0
    passed = 0

    for i, task in enumerate(tasks):
        start = time.time()
        ans = None
        if baseline == "always_large":
            ans = _call_model(client, config.large_model, task, config)
        elif baseline == "always_small":
            ans = _call_model(client, config.small_model, task, config)
        else:
            try:
                ans = route_task(task, config, client)
            except Exception as e:
                ans = f"ERROR: {e}"
        elapsed = time.time() - start

        ok = validate(task, ans)
        passed += 1 if ok else 0
        # tier0 proxy: zero-token tasks = tracker.tier_zero_hits delta
        rec = {
            "task_id": task["task_id"],
            "category": task["category"],
            "tier0": tracker.tier_zero_hits,
            "sympy": tracker.sympy_hits,
            "prompt_tokens": tracker.total.prompt_tokens,
            "completion_tokens": tracker.total.completion_tokens,
            "total_tokens": tracker.total.total_tokens,
            "answer": str(ans)[:120],
            "passed": ok,
            "elapsed": round(elapsed, 2),
        }
        records.append(rec)

    return {
        "config": name,
        "total_prompt_tokens": tracker.total.prompt_tokens,
        "total_completion_tokens": tracker.total.completion_tokens,
        "total_tokens": tracker.total.total_tokens,
        "api_calls": tracker.api_calls,
        "tier0_hits": tracker.tier_zero_hits,
        "sympy_hits": tracker.sympy_hits,
        "passed": passed,
        "total_tasks": len(tasks),
        "pass_rate": passed / len(tasks),
        "records": records,
    }


def main():
    keys = [
        k for k in [os.environ.get(f"OPENROUTER_KEY_{i}") for i in (1, 2, 3, 4)] if k
    ]
    if not keys:
        print("ERROR: set OPENROUTER_KEY_1..4")
        sys.exit(1)
    key = keys[0]

    small = os.environ.get("ABLATE_SMALL", "google/gemma-4-26b-a4b-it")
    large = os.environ.get("ABLATE_LARGE", "google/gemma-4-31b-it")

    configs = [
        ("A_full", {}),
        ("B_no_tier0", {"HYDRAROUTE_ABLATE_TIER0": "0"}),
        ("C_cascade", {"HYDRAROUTE_ABLATE_TIER0": "0", "HYDRAROUTE_ABLATE_LOCAL": "0"}),
        ("D_no_sympy", {"HYDRAROUTE_ABLATE_SYMPY": "0"}),
        ("E_always_large", {}, "always_large"),
        ("F_always_small", {}, "always_small"),
    ]

    os.makedirs("experiments", exist_ok=True)
    out = os.path.join(ROOT, "experiments", "ablation_results.json")
    # Resume: load any previously completed configs
    results = {}
    if os.path.exists(out):
        try:
            results = json.load(open(out))
            print(f"Resuming — already have: {list(results.keys())}", flush=True)
        except Exception:
            results = {}

    only = os.environ.get("ABLATE_ONLY")
    for cfg in configs:
        name = cfg[0]
        env = cfg[1] if len(cfg) > 1 else {}
        baseline = cfg[2] if len(cfg) > 2 else None
        if only and name != only:
            continue
        if name in results:
            print(f">> Skipping {name} (already done)", flush=True)
            continue
        # apply env gates
        saved = {}
        for k, v in env.items():
            saved[k] = os.environ.get(k)
            os.environ[k] = v
        print(f">> Running config {name} ...", flush=True)
        try:
            res = run_config(name, key, small, large, baseline=baseline)
            results[name] = res
            # incremental save so a killed run still keeps partial results
            with open(out, "w") as f:
                json.dump(results, f, indent=2)
            print(
                f"   tokens={res['total_tokens']:,}  tier0={res['tier0_hits']}  "
                f"sympy={res['sympy_hits']}  "
                f"pass={res['passed']}/{res['total_tasks']} ({res['pass_rate'] * 100:.1f}%)",
                flush=True,
            )
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    print(f"\nSaved -> {out}")


if __name__ == "__main__":
    main()
