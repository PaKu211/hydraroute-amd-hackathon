# Methodology: HydraRoute Paper Experiments

## Research Question
Does adding a deterministic pre-LLM solver tier to an LLM cascade routing system improve the cost-accuracy Pareto frontier compared to cascade-only approaches?

## Hypothesis
**H1**: A hybrid system with 11 local deterministic solvers before cascade routing achieves lower token cost at equal or higher accuracy compared to cascade-only routing (FrugalGPT, RouteLLM paradigm).

**Success criteria**:
1. Tier 0 solves ≥40% of tasks at zero tokens
2. Overall accuracy ≥95% on 67-task benchmark
3. Dollar cost savings ≥60% vs. always-using-large-model baseline
4. Total pipeline time ≤5 minutes for 67 tasks

## Experiment 1: Ablation Study (primary)

Compare three configurations on the 67-task benchmark:

| Config | Tier 0 (Solvers) | Tier Local (Qwen) | Tier 1 (Gemma 26B) | Tier 2 (Gemma 31B) |
|--------|:---:|:---:|:---:|:---:|
| **A — Full HydraRoute** | ✅ | ✅ | ✅ | ✅ |
| **B — Cascade-only** | ❌ | ❌ | ✅ | ✅ |
| **C — Always-large** | ❌ | ❌ | ❌ | ✅ |
| **D — SymPy-LLM ablated** | ❌ arithmetic | ✅ | ✅ | ✅ |

For each config, measure:
- Total tokens consumed (input + output)
- Accuracy (pass/fail per task, LLM-judge style)
- Wall-clock time
- Dollar cost (at Fireworks/OpenRouter pricing)

**Prediction**: Config A will dominate B on token cost at equal or higher accuracy. Config A vs D isolates SymPy-LLM contribution.

## Experiment 2: Cost Analysis

Using token counts from Experiment 1, compute:

| Metric | Formula |
|--------|---------|
| Cost per 1000 tasks | (total_api_tokens / 67) × 1000 × $price_per_token |
| Savings vs always-large | (cost_B - cost_A) / cost_B × 100% |
| Savings vs cascade-only | (cost_C - cost_A) / cost_C × 100% |
| Zero-token rate | tier_0_tasks / total_tasks × 100% |

Pricing reference (Gemma 4 on Fireworks):
- Gemma 4 26B MoE: $0.06/M input, $0.18/M output (approximately)
- Gemma 4 31B: $0.12/M input, $0.36/M output (approximately)

## Experiment 3: AMD GPU Benchmark (optional)

If compute budget permits:
- Run HydraRoute's Tier Local (Qwen 1.5B GGUF via llama.cpp) on AMD GPU (MI300X, 96GB)
- Measure tokens/second speedup vs CPU baseline
- Show that local model becomes viable with GPU (not just CPU fallback)

## Compute Requirements

| Experiment | Platform | GPU | Estimated Time | Estimated Cost |
|------------|----------|-----|---------------|---------------|
| E1: Ablation (API calls) | Local + OpenRouter | None needed (API) | ~30 min total | ~$0.50 API calls |
| E2: Cost analysis | Derived from E1 | None | 0 min | $0 |
| E3: GPU benchmark | Malimo | 1× GPU (96GB) | ~2 hours | ~$2 (free credits) |
| **Optional**: Fine-tune Gemma 4 12B (LoRA) | Malimo/Kaggle | 1× GPU (24GB+) | ~4 hours | ~$4 (free credits) |
| **Total** | | | **~6.5 hours** | **~$0.50** |

## Limitations & Assumptions
- API costs based on OpenRouter pricing (may differ from Fireworks)
- 67-task benchmark representative but not exhaustive
- GPU benchmark depends on successful ROCm/driver setup
- Fine-tuning experiment is aspirational — may be dropped if time-limited
