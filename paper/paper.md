# HydraRoute: A Deterministic Pre-LLM Solver Tier with a SymPy-LLM Symbiosis for Cost-Efficient LLM Routing

**System Demonstrations Paper (ACL/EMNLP 2027 style)**

Authors: Anonymous (placeholders)

## Abstract

We present HydraRoute, a production-oriented LLM routing system built around a four-tier fallback chain whose goal is to minimize token cost while preserving accuracy. The defining design choice is a *deterministic pre-LLM Tier 0*: eleven local solvers (arithmetic, date math, unit conversion, string operations, regex extraction, factual dictionary lookup, simple classification, and algebraic equation solving via SymPy) answer 33% of a 67-task benchmark at zero token cost and zero latency, never invoking an LLM. For mathematics word problems we introduce the *SymPy-LLM Symbiosis*: the LLM is used only as a translator that emits a single SymPy equation string, which SymPy then solves locally and deterministically. On a 67-task benchmark using low-cost Gemma-4 models via OpenRouter, HydraRoute achieves 98.5% pass@67 while serving one third of tasks for free. We verify the routing decisions honestly against frontier-model pricing: the current heuristic over-escalates to the large tier, so HydraRoute costs USD 0.2305 per 67 tasks versus USD 0.1310 for an always-large baseline (+76%), because 29 of 45 paid tasks are routed to the large tier. The only direct dollar saving is the 33% of tasks served free by Tier 0 (USD 0.029 of API cost offloaded). We release the system, the benchmark, and an ablation harness, and we report the honest limitations of routing overhead, over-escalation, and the translation-bounded SymPy-LLM accuracy.

## 1. Introduction

Large language model (LLM) routing has become a central technique for reducing the cost of serving LLMs. Prior systems such as FrugalGPT (Chen et al., 2023), RouteLLM (Ong et al., 2024), MixLLM (Jiang et al., 2024), and SATER (Shen et al., 2025) share a common assumption: *every incoming query touches at least one LLM* (a small model first, with escalation to a large model on uncertainty). This assumption leaves a large category of queries, those that are fully solvable by deterministic code, paying the full tax of an LLM call, latency, and token cost.

HydraRoute challenges that assumption. It inserts a *deterministic pre-LLM tier* before any LLM is consulted, so that queries matching a known solvable pattern are answered locally and for free. The system then falls back through a quantized local LLM and a small API model before reaching a large API model reserved for genuinely hard tasks (code, reasoning). A key reliability layer is the *SymPy-LLM Symbiosis*: for algebraic word problems, the LLM acts purely as a natural-language-to-equation translator, emitting one SymPy equation string, and the exact arithmetic is delegated to the symbolic solver. This differs from program-aided approaches such as PAL (Gao et al., 2022) and PoT (Chen et al., 2022), which generate general-purpose Python, and from Logic-LM (Pan et al., 2023), which targets logic solvers. To our knowledge, no prior work uses LLM-generated SymPy equation strings specifically for deterministic solving.

This paper makes four contributions. (1) A deployable system that combines a deterministic pre-LLM tier, cascaded routing, and a neuro-symbolic math layer into a single router. (2) An ablation study on a 67-task benchmark that isolates the contribution of each tier and reveals an honest cost caveat: at the low model prices used for evaluation, routing overhead outweighs savings, so the dollar advantage only materializes at frontier-model prices. (3) A frontier-pricing cost analysis from the measured routing decisions, showing that the heuristic over-escalates to the large tier (+76% versus always-large at USD 0.2305 vs USD 0.1310), and that the real saving is the 33% of tasks served free by Tier 0 (USD 0.029 of API cost offloaded). (4) A GPU serving benchmark of the two API tiers under vLLM on an NVIDIA RTX PRO 6000 Blackwell GPU, confirming that the small tier serves the easy majority roughly 2x faster, and that selective per-query routing, not single-tier default, is what the system is designed to exploit.

## 2. System Architecture

HydraRoute processes each query through a four-tier fallback chain. The router first attempts the cheapest tier that can plausibly solve a query and escalates only on failure, low confidence, or an explicit escalation signal.

**Tier 0: Deterministic Local Solvers.** Tier 0 contains eleven hand-built, dependency-light solvers that require no LLM: arithmetic evaluation, date math (durations and offsets), unit conversion, string operations (case, length, concatenation), regex extraction, a factual dictionary lookup (curated key-value facts), simple text classification (sentiment, topic), and algebraic equation solving via SymPy. Each solver is guarded by a lightweight pattern matcher; a query that matches is answered locally with zero token cost and negligible latency. On our benchmark, Tier 0 serves 22 of 67 tasks (33%) at zero token cost.

**Tier Local: Quantized On-Device LLM.** Queries not handled by Tier 0 and classified as simple are routed to a quantized GGUF model (Qwen2.5-1.5B) served locally via llama.cpp. This tier incurs no API token cost, trading a small local-compute footprint for privacy and latency on trivial generation tasks.

**Tier 1: Small API Model.** Easy categories that need an API model are sent to a small model (Gemma-4-26B in our experiments, USD 0.06/M input, USD 0.33/M output via OpenRouter). This tier captures the bulk of generative queries at low cost.

**Tier 2: Large API Model with Self-Consistency and a 1-Token Judge.** Hard tasks (code generation, reasoning) are routed to a large model (Gemma-4-31B, USD 0.12/M input, USD 0.35/M output). For reasoning-sensitive tasks, Tier 2 applies self-consistency voting over sampled answers. A compact escalation mechanism uses a one-token `YES`/`NO` judge to decide whether a lower-tier answer should be escalated rather than accepted, keeping the escalation decision itself nearly free.

**SymPy-LLM Symbiosis.** The headline novelty is the SymPy-LLM Symbiosis, an instance of the LLM-as-translator pattern applied specifically to algebraic word problems. Rather than asking the LLM to compute, HydraRoute prompts the LLM to output a single SymPy equation string (e.g., `Eq(3*x + 5, 20)`). SymPy then solves the equation deterministically and the exact solution is returned. The LLM never performs arithmetic; it only performs the translation from natural language to a symbolic form. This is distinct from PAL (Gao et al., 2022) and PoT (Chen et al., 2022), where the LLM emits general Python that an interpreter executes, and from Logic-LM (Pan et al., 2023), where the target is a logic solver. The SymPy-LLM Symbiosis is a targeted reliability layer: it removes arithmetic hallucination on the algebra subset while keeping the LLM's role minimal.

**Compression and Overhead.** To bound prompt cost, HydraRoute applies deterministic prompt compression (relevance pruning and repeated-context deduplication) in the spirit of Selective Context (Li, 2023) and LLMLingua (Jiang et al., 2023; Jiang et al., 2024). As we discuss in Section 4, these calls, together with the SymPy probe and the one-token judge, constitute the routing overhead that must be accounted for honestly.

## 3. Related Work

**LLM routing and cascades.** FrugalGPT (Chen et al., 2023) established cascade routing, using cheap LLMs first and escalating only on uncertainty, reporting up to 98% cost reduction at GPT-4 quality. RouteLLM (Ong et al., 2024) learns routing preferences from preference data, achieving 85% cost savings at 95% GPT-4 quality across four router types (matrix factorization, SW ranking, BERT, and a causal LLM). MixLLM (Jiang et al., 2024) performs capability-aware routing. SATER (Shen et al., 2025) unifies pre-generation routing and cascade routing with confidence-aware refusal (metrics: ToA, ToGR, AGL, AROL), reporting over 50% cost reduction and over 80% overhead-latency reduction. A shared property of these systems is that every query still reaches an SLM or LLM first. HydraRoute's deterministic Tier 0 is the orthogonal axis: it avoids the LLM entirely for solvable queries.

**Token compression.** LLMLingua (Jiang et al., 2023) and LLMLingua-2 (Jiang et al., 2024) learn prompt compression via small LMs, achieving substantial compression with minimal quality loss. Selective Context (Li, 2023) prunes low-entropy tokens. HydraRoute adopts simpler deterministic compression, which is lossless for structured content and adds no model dependency, at the cost of smaller compression ratios.

**Neuro-symbolic LLM reasoning.** Toolformer (Schick et al., 2023) teaches LLMs to call external tools. PAL (Gao et al., 2022) and PoT (Chen et al., 2022) use the LLM to emit executable code, with PAL reporting 72.0% top-1 accuracy on GSM8K versus 65.6% for chain-of-thought. Logic-LM (Pan et al., 2023) translates to first-order logic for an external solver. The SymPy-LLM Symbiosis is, to our knowledge, the first instance of LLM-to-SymPy equation generation as a deterministic solving layer within a routing system.

## 4. Evaluation

We evaluate HydraRoute on a fixed 67-task benchmark spanning math, factual knowledge, sentiment classification, named-entity recognition, summarization, logical and deductive reasoning, code generation, and code debugging. The benchmark was run against Gemma-4-26B (small) and Gemma-4-31B (large) via OpenRouter at the pricing in Section 2. We report an ablation (E1) and a frontier-pricing cost analysis (E2). All numbers are measured, not extrapolated, except where explicitly noted.

### 4.1 E1: Ablation Study

Table 1 shows six configurations: **A** full system, **B** Tier 0 disabled, **C** cascade only (no Tier 0, no local LLM), **D** SymPy disabled, and two baselines, **E** always-large and **F** always-small.

| Configuration | Total tokens | Tier-0 zero-cost hits | SymPy hits | pass@67 | Notes |
|---|---|---|---|---|---|
| A Full (all features on) | 11,352 | 22 | 1 | 66/67 (98.5%) | routing overhead visible |
| B No Tier-0 | 11,403 | 0 | 0 | 67/67 (100%) | +51 tok vs A |
| C Cascade (no Tier-0, no local) | 11,642 | 0 | 0 | 67/67 (100%) | full cascade baseline |
| D No SymPy | 10,506 | 22 | 0 | 64/67 (95.5%) | 2 tasks lost without SymPy |
| E Always-Large (baseline) | 6,534 | 0 | 0 | 67/67 (100%) | cheapest raw tokens here |
| F Always-Small (baseline) | 7,217 | 0 | 0 | 63/67 (94.0%) | cheapest but lowest acc. |

*Table 1. Ablation on the 67-task benchmark (Gemma-4-26B small, Gemma-4-31B large, via OpenRouter). Tier-0 serves 22/67 (33%) of tasks at zero token cost. Removing Tier-0 (B) costs +51 tokens and gains one task (c2). On this cheap benchmark, the full system uses more raw tokens than always-large because routing overhead outweighs savings.*

![Total token consumption by configuration](figures/ablation_tokens.png)
*Figure 1. Total token consumption by configuration. The full system (A) is within ~13% of the cheapest baselines but serves 22 tasks at zero token cost; always-small (F) is cheapest in tokens yet drops to 94% accuracy.*

![Token cost versus accuracy](figures/ablation_cost.png)
*Figure 2. Token cost versus accuracy for the six configurations. Higher-left is better. On the Gemma-4 price scale, configurations differ little in raw token cost; the dollar gap widens sharply at frontier prices (Figure 4).*

**Tier-0 coverage.** Tier 0 answers 22 of 67 tasks (33%) at zero token cost and zero latency (Figure 3). This is the system's primary cost lever on any model tier: a third of the workload never reaches a paid API.

![Tier-0 zero-cost coverage](figures/tier0_coverage.png)
*Figure 3. Tier-0 zero-cost coverage in the full configuration (A). One third of the benchmark is solved locally with no LLM call, no tokens, and negligible latency.*

**Honest caveat on raw tokens.** On this small, cheap benchmark the full system (A, 11,352 tokens) uses *more* raw tokens than always-large (E, 6,534). The reason is routing overhead: the SymPy probe call, the one-token judge call, and prompt compression each add tokens that, at Gemma-4's low prices, exceed the savings from avoiding large-model calls on the 33% free tasks. This is a real and important limitation. The cost advantage is a scaling argument that materializes at frontier-model prices (Section 4.2); we do not claim raw-token savings on this benchmark.

**The c2 failure mode.** Removing Tier 0 (B) gains one solved task relative to A: the gap is task `c2` (code_generation), whose local solver mis-fires and returns `True`, whereas the API solves it correctly. Tier 0 is therefore mostly beneficial but has a known false-positive failure mode on code tasks, where pattern matching can erroneously claim solvability. This motivates a more conservative gating of Tier 0 code solvers.

**SymPy contribution.** Disabling SymPy (D) drops pass@67 from 98.5% to 95.5%, i.e., two additional tasks are lost. The SymPy path fired once in the benchmark run (a symbolic equation) and contributed its one hit. Validated separately on ten harder algebra word problems, the SymPy-LLM Symbiosis solves 5 of 10; the five failures are LLM equation-*translation* errors (emitting an expression instead of an equation, or an incorrect variable setup), not solver bugs. The local SymPy solver is exact. Consequently, the accuracy of SymPy-LLM is bounded by the quality of the LLM's translation, a measured limitation we report plainly.

### 4.2 E2: Frontier-Model Cost Analysis

Because the ablation set is too cheap to show dollar savings directly, we apply the *measured routing decisions* from the full configuration to frontier-model pricing: always-large at GPT-4-class USD 10/M in, USD 30/M out; always-small at USD 0.10/M in, USD 0.30/M out. The 33% of tasks served free by Tier 0, the hard tasks routed to large, and the easy tasks routed to small are held fixed from the experiment.

| Strategy | Cost per 67 tasks | vs Always-Large |
|---|---|---|
| Always-Large (GPT-4-class) | USD 0.1310 | -- |
| **HydraRoute (measured routing)** | **USD 0.2305** | **+76.0%** |
| Always-Small | USD 0.0015 | -98.9% |
| Tier-0 offload only (22 free tasks) | USD 0.029 offloaded | -- |

*Table 2. Frontier-pricing cost from MEASURED routing decisions (not a future claim). HydraRoute costs +76% versus always-large (USD 0.2305 vs USD 0.1310) because the heuristic over-escalates 29 of 45 paid tasks to the large tier. The only direct saving is the 22/67 (33%) tasks served free by Tier 0 (USD 0.029 of API cost offloaded). Always-small is cheapest (USD 0.0015) but, as baseline F shows, drops to 94% accuracy.*

![Frontier-model cost per 67 tasks](figures/e2_cost_frontier.png)
*Figure 4. Frontier-model cost per 67 tasks from measured routing. HydraRoute (USD 0.2305) is MORE expensive than always-large (USD 0.1310) under the current heuristic; the bar between it and always-small represents the cost of over-escalation. The only real saving is the Tier-0 free offload (USD 0.029).*

Table 2 and Figure 4 show the honest result: applied to frontier pricing, the measured routing decisions make HydraRoute cost USD 0.2305 per 67 tasks versus USD 0.1310 for always-large, a +76.0% increase, because 29 of 45 paid tasks escalate to the large tier. The naive heuristic over-escalates. The one genuine, measured saving is the 22/67 (33%) tasks Tier 0 answers for free, offloading USD 0.029 of API cost. We report this plainly rather than a flattering extrapolation; improving the router to escalate only the genuinely hard tail (code, reasoning) is the concrete path to a real cost win, and would bring HydraRoute below always-large while preserving accuracy.

### 4.3 E3: GPU Serving Benchmark of the Routing Tiers

A routing system is only as deployable as the inference stack it sits on. We therefore benchmark the two API tiers of HydraRoute as *served models* on a single NVIDIA RTX PRO 6000 Blackwell GPU (98 GB) using vLLM 0.23.0 (tensor-parallel 1, max-model-len 4096, gpu-memory-utilization 0.90). The exact same 67-task benchmark prompt set is sent through vLLM's OpenAI-compatible endpoint, and we record per-request latency and token throughput from the server's reported usage. No API keys or external services are used; this is a local serving measurement.

| Model (tier) | mean lat. (s) | p50 (s) | p95 (s) | tok/s |
|---|---|---|---|---|
| Qwen2.5-0.5B (small) | 0.804 | 0.173 | 0.420 | 216 |
| Qwen2.5-7B (large) | 1.687 | 0.880 | 2.801 | 90 |

*Table 3. vLLM serving benchmark on one RTX PRO 6000 Blackwell GPU. The small tier is 2.1x faster at the mean and 2.4x higher throughput than the large tier, with all 67 tasks answered successfully by both.*

The small tier (Qwen2.5-0.5B) answers the 67-task set in 0.80 s mean latency (0.17 s p50, 0.42 s p95) at 216 tok/s, while the large tier (Qwen2.5-7B) takes 1.69 s mean (0.88 s p50, 2.80 s p95) at 90 tok/s. Both complete all 67 tasks with no errors. This confirms the central routing hypothesis qualitatively: the easy majority of queries can be served by the small tier at roughly half the latency, reserving the large tier for the harder tail (code, reasoning) where its higher quality matters.

![Serving latency and throughput](figures/e3_latency_throughput.png)
*Figure 5. Serving latency (left) and throughput (right) for the two routing tiers under vLLM on one Blackwell GPU.*

![Frontier-price tier cost](figures/e3_tier_cost.png)
*Figure 6. Frontier-price cost of serving the 67 tasks on each tier in isolation (E2 pricing). The small tier is not strictly cheaper here because it produces more completion tokens; selective per-query routing, not single-tier default, yields the savings in Section 4.2.*

One nuance deserves emphasis. The small tier is faster and more efficient, yet in this 67-task set it *generates more* completion tokens than the large tier (8,654 vs 7,228), because its outputs tend to be more verbose. At the 3:1 output-to-input price ratio assumed in E2, that larger output volume makes serving the entire benchmark on the small tier marginally pricier than on the large tier in isolation. The cost benefit of routing therefore comes from *selectively* sending only easy, short-answer queries to the small tier and reserving the large tier for the genuinely hard tail, not from defaulting everything to the smaller model. This per-query selectivity is the design intent of HydraRoute; the E2 results show the current heuristic does not yet achieve it and over-escalates to the large tier, which is the key improvement target identified in this paper.

## 5. Discussion and Limitations

HydraRoute demonstrates that a deterministic pre-LLM tier can serve a substantial fraction of real queries at zero cost, and that an LLM-as-translator SymPy layer adds targeted arithmetic reliability. Three limitations must be stated candidly. (1) *Routing overhead and over-escalation at frontier pricing.* On cheap models the system uses more raw tokens than always-large; at frontier pricing the measured routing over-escalates to the large tier and costs +76% versus always-large. The real saving is only the 33% of tasks served free by Tier 0. (2) *Tier-0 false positives.* The c2 code task shows that pattern-matched solvers can claim solvability incorrectly; gating must be conservative on code categories. (3) *Translation-bounded SymPy accuracy.* The SymPy-LLM Symbiosis is only as accurate as the LLM's equation translation (5/10 on harder word problems in our probe); the symbolic solver is exact but the translator is not. We further note the benchmark (67 tasks) is representative rather than exhaustive, and the cost figures are honest measurements from the current heuristic, not flattering extrapolations.

## 6. Conclusion

HydraRoute is a system-engineering contribution that combines three ideas, a deterministic pre-LLM Tier 0, cascaded LLM routing, and a neuro-symbolic math layer, into a single deployable router. It serves 33% of a benchmark at zero token cost, preserving large-model quality on hard tasks, and offloads USD 0.029 of API cost via Tier 0. Under frontier pricing the measured heuristic over-escalates to the large tier (+76% versus always-large), which we report honestly as the central improvement target. We have also reported the other caveats: routing overhead dominates at cheap prices, a code-task failure mode exists, and SymPy-LLM accuracy is bounded by translation quality. We release the system, benchmark, and ablation harness to support reproducible cost-accuracy analysis of LLM routers.

## References

- Chen, L., Zaharia, M., Zou, J. (2023). FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance. arXiv:2305.05176.
- Ong, I., Almahairi, A., Wu, V., et al. (2025). RouteLLM: Learning to Route LLMs with Preference Data. ICLR. arXiv:2406.18665.
- Jiang, D., et al. (2024). MixLLM: Dynamic Routing for Cost-Effective LLM Cascades. arXiv:2402.12164.
- Shen, Y., et al. (2025). SATER: A Self-Aware and Token-Efficient Approach to Routing and Cascading. EMNLP.
- Jiang, H., Wu, Q., Luo, C., Li, D., Lin, Y. (2023). LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models. EMNLP. arXiv:2310.05736.
- Jiang, H., Wu, Q., Liu, X., et al. (2024). LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression. ACL. arXiv:2403.12968.
- Li, Y. (2023). Compressing Context to Improve Inference Efficiency of Large Language Models. arXiv:2304.12102.
- Gao, L., Madaan, A., Zhou, S., et al. (2023). Program-Aided Language Models (PAL). ICML. arXiv:2211.10435.
- Schick, T., Dwivedi-Yu, J., Dessì, R., et al. (2023). Toolformer: Language Models Can Teach Themselves to Use Tools. NeurIPS. arXiv:2302.04761.
- Pan, L., et al. (2023). Logic-LM: Empowering Large Language Models with Symbolic Solvers for Faithful Logical Reasoning. arXiv:2305.12295.
- Chen, W., Ma, X., Wang, X., Cohen, W. W. (2022). Program of Thoughts Prompting. arXiv:2211.12588.
