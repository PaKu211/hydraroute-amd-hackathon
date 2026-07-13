# Research State: HydraRoute Paper

## Current Stage
SCOPE ✅ → LITERATURE ✅ → REASON ✅ → METHODOLOGY ✅ → DEEP RESEARCH ✅ → COMPUTE ✅ (E1,E2,E3) → ANALYZE ✅ → SYNTHESIZE ✅ → WRITE ✅ → VERIFY+REVISE ✅ (E2 false-claim fixed, PDF recompiled)

## VERIFICATION FIX (2026-07-13)
During user's "is it verified / not halu?" check, found and fixed REAL errors:
1. E2 "55% saving" was FALSE. Recomputed honest frontier cost from MEASURED routing
   (CATEGORY_MODEL_PREFERENCE table): 16 small / 29 large of 45 paid tasks.
   - HydraRoute (measured) = $0.2305 ; Always-Large = $0.1310 ; Always-Small = $0.0015
   - HydraRoute is +76% vs always-large (over-escalation to large tier), NOT -55%.
   - Only real saving = Tier-0 offload: 22 free tasks = $0.029 vs API.
   - Paper §4.2, Table 2, Fig 4, Discussion, Conclusion all corrected; e2_cost_frontier.png regenerated.
2. Config B "costs +1,306 tok vs A" was wrong → actually +51 (11,403 vs 11,352). Fixed in §4.1 caption.
3. Architecture text said factual/sentiment → GGUF; measured run shows deterministic Tier-0
   solved all 22 free (math+factual+sentiment+1 code). Clarified Tier-Local is designed fallback, not exercised.
4. SATER bib author typo (Yilong→Yuanzhe Shen, arXiv:2510.05164) fixed + eprint added.
5. CITATIONS VERIFIED REAL (not hallucinated): all 11 papers exist. SATER = arXiv:2510.05164
   Shen et al. EMNLP 2025. PAL, FrugalGPT, RouteLLM, LLMLingua, LLMLingua-2, Selective Context,
   Toolformer, Logic-LM, PoT all genuine.
PDF recompiled on marimo sb-64b1d6f5148ecd10: paper/paper.pdf = 291,423 B, 0 undefined cites, 0 errors.

## Deliverables (WRITE ✅)
- paper/paper.tex (ACL 2-col, natbib, 181 lines) — compile: pdflatex→bibtex→pdflatex×2
- paper/paper.md (plain MD mirror)
- paper/custom.bib (11 verified citations)
- paper/figures/ (6 figures: ablation_tokens, ablation_cost, tier0_coverage, e2_cost_frontier, e3_latency_throughput, e3_tier_cost)
All numbers verbatim from real E1/E2/E3 data. Honest caveats preserved.

## E3 GPU Serving Benchmark (COMPUTE ✅)
Ran on marimo notebook sb-64b1d6f5148ecd10 (NVIDIA RTX PRO 6000 Blackwell, 98 GB,
vLLM 0.23.0, CUDA 13.0). AMD/ROCm path dropped per user (AMD no longer available).
Served the same 67-task benchmark via vLLM OpenAI endpoint, TP=1, max-len 4096, gpu-mem 0.90.

| model (tier)       | mean lat (s) | p50 (s) | p95 (s) | tok/s | compl tok | n_ok |
|--------------------|--------------|---------|---------|-------|-----------|------|
| Qwen2.5-0.5B (small) | 0.804      | 0.173   | 0.420   | 216   | 8,654     | 67/67 |
| Qwen2.5-7B (large)   | 1.687      | 0.880   | 2.801   | 90    | 7,228     | 67/67 |

Findings:
- Small tier 2.1x faster (mean) and 2.4x higher throughput than large tier.
- Both complete all 67 tasks with no errors.
- NUANCE: small tier generates MORE completion tokens (8,654 vs 7,228) → at E2's 3:1
  output:input price ratio, serving whole benchmark on small tier is marginally pricier
  than on large tier in isolation. Cost benefit comes from SELECTIVE per-query routing,
  not single-tier default. Stated honestly in paper E3 section.
- Files: experiments/e3_qwen7b.json, experiments/e3_qwen05b.json
  Figures: figures/e3_latency_throughput.png, figures/e3_tier_cost.png
  Local transfer via base64 pull from notebook.

## E2 Cost Analysis (COMPUTE ✅, later CORRECTED in VERIFY)
Frontier-model pricing model (always-large = GPT-4-class $10/M in, $30/M out;
always-small = $0.10/M in, $0.30/M out).
*** CORRECTED (was a false 55% saving). Honest numbers from measured routing: ***
- HydraRoute (measured routing): $0.2305  |  Always-Large: $0.1310  |  Always-Small: $0.0015
- HydraRoute costs +76% vs always-large (heuristic over-escalates 29/45 paid tasks to large).
- REAL saving = Tier-0 offload only: 22 free tasks remove $0.029 of API cost.
- File: experiments/e2_cost_model.json (STALE — kept for provenance), Figure regenerated.

## Research Question
Does adding a deterministic pre-LLM solver tier (Tier 0: 11 local solvers + SymPy-LLM
Symbiosis) to an LLM cascade routing system improve the cost-accuracy Pareto frontier
compared to cascade-only approaches?

## Key Decisions
- Venue: ACL/EMNLP System Demonstrations (4-6 pp) or AAAI Applied AI. System-engineering contribution.
- Paper core claim: **SymPy-LLM Symbiosis** (LLM translates word problem → single SymPy
  equation string; SymPy solves locally, deterministically). No prior paper does LLM→SymPy
  equation generation specifically (PAL uses general Python; Logic-LM uses logic solvers).
- OpenRouter keys = TESTING/EXECUTION ONLY (4 keys). NotebookLM = RESEARCH ONLY.
  Fireworks key = DO NOT USE (user explicit).

## Resources
- OpenRouter: ✅ 4 keys (testing). Gemma-4-26B/31B available via OpenRouter.
- sympy: ✅ installed locally to .venv_libs (read-only FS; add to PYTHONPATH).
- Kaggle: ✅ 30h GPU (E3).  Malimo: ⬜ 12h 96GB (menunggu user).
- CORRECTION: Fireworks key was used in hackathon but must NOT be used for paper (user: hapus).

## E1 Ablation Results (COMPUTE ✅)
6 configs × 67-task benchmark, Gemma-4-26B (small) + Gemma-4-31B (large) via OpenRouter.
Models: small=$0.06/M in, $0.33/M out; large=$0.12/M in, $0.35/M out.

| config | tokens | tier0 hits | sympy | pass |
|--------|--------|-----------|-------|------|
| A_full (all on) | 11,352 | 22 | 1 | 66/67 (98.5%) |
| B_no_tier0 | 11,403 | 0 | 0 | 67/67 (100%) |
| C_cascade (no T0, no local) | 11,642 | 0 | 0 | 67/67 (100%) |
| D_no_sympy | 10,506 | 22 | 0 | 64/67 (95.5%) |
| E_always_large (baseline) | 6,534 | 0 | 0 | 67/67 (100%) |
| F_always_small (baseline) | 7,217 | 0 | 0 | 63/67 (94.0%) |

Key findings:
- Tier 0 serves 22/67 = 33% of tasks at ZERO token cost & zero latency. (One of these,
  c2 a code_generation task, mis-fires the local solver returning "True" — see bug below.)
- Removing Tier 0 (B_no_tier0) adds +51 tokens and GAINS +1 task solved: the
  gap is c2 (code_generation), which Tier 0 mis-solves as "True" but the API solves
  correctly. HydraRoute (A) therefore scores 66/67 vs B's 67/67 on this benchmark.
- HydraRoute (A) uses MORE raw tokens than always-large (E) on this tiny set because
  routing overhead (SymPy probe + judge calls + compression) outweighs savings at this
  scale with cheap models. REAL cost advantage comes from avoiding large-model calls for
  33% of tasks and scales with expensive frontier models — must be stated honestly.
- SymPy-LLM Symbiosis: validated separately on 10 harder word problems → 5/10 correct.
  Failures are LLM equation-translation errors (e.g. emits expression not equation, or
  wrong variable setup), NOT solver bugs. Honest accuracy ceiling = bounded by LLM.
  In the benchmark run, the SymPy path fired once (m10, a date-math task) and emitted
  garbage '180/(a*c*d*e*i*n*s)' — a ROUTING BUG (SymPy path should be gated to algebraic
  word problems, not date math). Loosened validator had counted m10 as passed; tightened.

## Bug Fixes Made During COMPUTE
1. router.py: ablation gates were module-level constants (read once at import) → env
   changes per-run had NO effect. Fixed to runtime `_ablate(name)` helper. Re-ran all configs.
2. sympy NOT installed in this env → entire SymPy-LLM feature silently no-op'd (import
   fail returned None). Installed sympy to .venv_libs; added PYTHONPATH. Feature now works.
3. solve_equation_string: LLM returns `Eq(a, b)` form and `==` and `**` exponent — all
   now normalized. Safe-pattern expanded to allow `*`/`^`.
4. SymPy-LLM fires on date-math tasks (m10) producing garbage `180/(a*c*d*e*i*n*s)`.
   Routing bug: SymPy path should be gated to algebraic word problems, not date math.
   (Note as limitation; m10 still correct via Tier 0 in normal flow.)

## Experiment Log
| Attempt | Method | Result | Status |
|---------|--------|--------|--------|
| 1 | E1 ablation 6 configs | Tier 0 = 33% zero-cost; routing overhead > savings at small scale | ✅ done |
| 2 | SymPy-LLM probe (10 hard WP) | 5/10 correct; bounded by LLM translation | ✅ done |

## What Worked
- Env-flag ablation harness (benchmarks/ablation_e1.py) with resume + per-config increment.
- Gemma-4 via OpenRouter is cheap enough for full ablation at ~$0.01 total.

## What Didn't Work
- NotebookLM CLI does NOT execute web search (prints tool-call plan only). Used OpenRouter
  sonar-deep-research as research substitute (key 3 & 4 work; keys 1 & 2 = 402).
- sympy absent → feature dead until install.

## Open Questions
1. E2 full cost analysis at frontier-model prices (GPT-4-class) to show real $ savings. — ✅ DONE
2. E3 GPU benchmark — ✅ DONE as vLLM serving benchmark (NVIDIA RTX PRO 6000 Blackwell, not
   AMD ROCm — AMD path dropped per user; marimo notebook URL changed twice, final
   sb-64b1d6f5148ecd10). Qwen2.5-0.5B (small) and Qwen2.5-7B (large) served via vLLM 0.23.0.
3. SymPy-LLM routing guard (gate to algebraic-only) — noted as limitation in paper.

## Artifacts
- literature-review.md ✅  paper_feasibility.md ✅  reasoning.md ✅  methodology.md ✅
- research/deep_pal_sater.md ✅  research/notebooklm_*.md (partial)
- experiments/ablation_results.json ✅  benchmarks/ablation_e1.py ✅
- figures/: EMPTY (need ≥1 data figure before SYNTHESIZE)
