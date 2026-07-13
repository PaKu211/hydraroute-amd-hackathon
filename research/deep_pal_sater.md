# Deep Research: PAL & SATER (via NotebookLM)

## PAL — Program-Aided Language Models (Gao et al., 2022; ICML 2023)

**Mechanism**: PAL restructures neuro-symbolic reasoning. The LLM is used *only* as a
translator — it reads a natural-language problem and emits an intermediate Python program
(via few-shot exemplars with interleaved variable names and descriptive comments). All
arithmetic/logic computation is delegated to an external Python interpreter, producing
deterministic, mathematically exact output. This eliminates the arithmetic hallucination
that Chain-of-Thought (CoT) suffers from.

**Key numbers (verified, GSM8K)**:
- PAL + Codex (code-davinci-002): **72.0%** top-1 accuracy
- CoT + Codex (same model): **65.6%** → PAL improves by **+6.4% absolute**
- PAL + Codex **beats PaLM-540B with CoT by +15%** absolute
- GSM-Hard: CoT drops ~70% (arithmetic failure); PAL only drops 14.3% (to 61.2%) because
  the interpreter is immune to large numbers
- BIG-Bench Hard: Colored Objects 95.1%, Penguins 93.3% (+8–14 pts vs CoT)

**Relevance to HydraRoute**: PAL generates *general-purpose Python code*. HydraRoute's
SymPy-LLM Symbiosis instead generates a *single SymPy equation string* that SymPy solves
deterministically. This is a narrower, more targeted "LLM-as-translator" pattern — the
LLM never executes code, only emits an equation. **No prior paper uses LLM→SymPy equation
generation specifically.** This is our novelty wedge.

## SATER — Self-Aware Token-Efficient Routing (Shen et al., 2025, EMNLP)

**Mechanism — dual-mode routing**:
1. **Pre-generation routing**: incoming query is assessed; if the Small Language Model
   (SLM) refuses (confidence below threshold), it is routed directly to the LLM.
2. **Cascade routing**: SLM answers first; weighted majority voting (Ranged Confidence
   Voting / Fixed Confidence Voting) aggregates confidence-scored samples; if confidence
   fails the threshold, falls back to LLM.

**Two-stage training**:
- Stage I — Shortest-Response Preference Optimization (DPO): teaches SLM to prefer the
  shortest correct answer, suppressing redundant tokens (>50% token reduction).
- Stage II — Confidence-Aware Refusal Training (SFT): SLM is trained across confidence
  thresholds 0.1–1.0 to proactively refuse ("Sorry, I can't answer that") when predicted
  accuracy is below threshold.

**Key numbers (verified)**:
- Routing cost savings: **>50%** vs no-SATER strategy (when LLM:SLM cost ratio > 50)
- Cascade latency (AGL): reduced **>50%**
- Routing overhead latency (AROL): reduced **>80%**
- Approaches absolute LLM score while staying cheap

**Metrics defined**:
- **ToA** (Tradeoff Area): area under the cost-performance curve
- **ToGR** (Tradeoff Gain Ratio): ratio of actual routing gain vs ideal "golden routing"
  (corrects Performance Gap Bias)
- **AGL** (Average Generation Latency): latency when query fully resolved by SLM
- **AROL** (Average Routing Overhead Latency): extra latency from SLM failure → LLM fallback

**Relevance to HydraRoute**: SATER unifies routing+cascading with *learned* refusal.
HydraRoute instead uses a **deterministic pre-LLM Tier 0** (11 local solvers) that avoids
the LLM entirely for solvable tasks — a different axis of cost reduction not explored by
SATER (which still assumes every query hits an SLM first).
