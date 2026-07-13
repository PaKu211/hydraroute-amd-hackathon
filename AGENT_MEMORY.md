# HydraRoute — Cross-Session Memory (for AI agents)

> Purpose: this file is the durable, authoritative memory of the HydraRoute project so any
> AI agent picking up this repo in a new session can recover state instantly. Keep it in sync.

## What HydraRoute is
A production-oriented LLM **routing** system with a **four-tier fallback chain**:
1. **Tier 0 — Deterministic Pre-LLM solvers** (11 local, no-LLM solvers incl. SymPy algebra).
2. **Tier Local** — quantized GGUF on-device LLM (designed fallback, rarely exercised).
3. **Tier 1 — Small API model** (Gemma-4-26B via OpenRouter).
4. **Tier 2 — Large API model** (Gemma-4-31B via OpenRouter) + 1-token YES/NO judge.
Headline novelty: **SymPy-LLM Symbiosis** (LLM = NL→equation translator, SymPy solves deterministically).

## Ground truth (VERIFIED, do not regress)
- E1 ablation (6 configs × 67 tasks, Gemma-4 via OpenRouter): A=11,352 tok/tier0=22/sympy=1/66-67(98.5%);
  B=11,403(+51 vs A)/67-67; C=11,642/67-67; D=10,506/tier0=22/sympy=0/64-67(95.5%); E=6,534/67-67; F=7,217/63-67(94.0%).
  Tier 0 serves 22/67 = 33% at ZERO token cost. c2 failure mode = Tier-0 mis-fires "True" on code_gen.
- E2 (FRONTIER pricing $10/M in, $30/M out large; $0.10/M in, $0.30/M out small), MEASURED routing:
  **HydraRoute = $0.2305, Always-Large = $0.1310, Always-Small = $0.0015**. HydraRoute is **+76%** vs always-large
  (over-escalates 29/45 paid tasks to large tier). Real saving = Tier-0 offload = **$0.029** API cost.
  ⚠️ The OLD "55% saving / $0.0905" claim was FALSE and has been corrected everywhere. NEVER restore it.
- E3 GPU serving (vLLM 0.23.0, 1× RTX PRO 6000 Blackwell): Qwen2.5-0.5B small = 0.804s mean / 216 tok/s;
  Qwen2.5-7B large = 1.687s mean / 90 tok/s. Both 67/67 OK. Small ≈ 2.1× faster.
- 67-task benchmark: 10 math / 10 factual / 10 sentiment / 10 code_gen / 10 code_dbg / 7 logical / 5 ner / 3 deductive / 2 summarization.
- SymPy-LLM Symbiosis validated 5/10 harder algebra WPs (failures = LLM translation errors, solver is exact).

## Credentials & keys (DO NOT COMMIT)
- OpenRouter 4 keys used for TESTING/EXECUTION ONLY. Keys 1&2 = HTTP 402 (dead). Use keys 3&4.
- **Fireworks API key = DO NOT USE / must be removed** (user instruction). Only env-var plumbing remains in code.
- NotebookLM = RESEARCH ONLY (CLI authenticated). Deep research done via perplexity/sonar-deep-research.

## Repo layout
- `src/` router + tiers + token_tracker (ablation gates wired in).
- `benchmarks/` ablation_e1.py + hydraroute_benchmark.json (67 tasks).
- `experiments/` ablation_results.json (E1), e2_cost_model.json (HONEST), e3_*.json (E3).
- `figures/` E1/E3 PNGs (+ e2 regenerated). `scripts/` figure generators.
- `paper/` paper.tex (ACL 2-col, author block editable lines 18-31), paper.md, custom.bib (11 verified cites).
- `literature-review.md` (47 verified papers), `reasoning.md`, `methodology.md`, `research-state.md`, `research/`.

## Local build quirks
- Read-only agent fs: sympy+matplotlib installed to `.venv_libs/`. Run python with
  `PYTHONPATH=/home/smiley/projek/agy/hackathon-lablab/.venv_libs:$PYTHONPATH MPLCONFIGDIR=/tmp/mplcache`.
- PDF compiled on marimo box sb-64b1d6f5148ecd10 (full TeX Live). Local compile:
  `cd paper && pdflatex paper.tex && bibtex paper && pdflatex paper.tex && pdflatex paper.tex`.

## Git hygiene
- `.gitignore` excludes: .venv/, .venv_libs/, .openscience/, paper/figures/, paper/paper.pdf,
  paper/acl.sty, paper/acl_natbib.bst, *.env, research/notebooklm_*.md.
- Never commit secrets. Paper source (tex/md/bib) is committed; PDF/figures are NOT.

## Submission status
- Hackathon: AMD Track 1, SUBMITTED (8/8 tasks pass), Docker ghcr.io/paku211/hydraroute:latest.
- Paper target venue: ACL/EMNLP System Demonstrations (best fit) OR co-located Efficient-LLM workshops.
  Do NOT claim "55% saving" anywhere in submissions.
