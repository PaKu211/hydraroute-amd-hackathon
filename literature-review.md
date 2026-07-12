# Literature Review: Token-Efficient LLM Routing & Optimization

## Summary
Final sweep with 3 parallel literature-review agents across papers (30 papers 2023-2026), GitHub repos (20 repos), and hackathon write-ups. Key findings: (1) calibration-first routing (UCCI 2026) validates our FrugalGPT approach, (2) token compression frameworks (LLMLingua 20x, copium 65-90%) confirm compression direction, (3) leaderboard shows 0-token submissions exist but with accuracy trade-offs — our hybrid approach targets the accuracy gate survival + token minimization.

## Key Findings by Facet

### Facet 1: Latest Papers (2025-2026)
- **UCCI** (Kotte, 2026): Calibration-first router, 31% cost savings on H100, isotonic regression for confidence scores
- **Cascadia** (Jiang et al., 2025): Co-optimizes deployment + routing, 2.3x tighter latency SLOs
- **VLLM Semantic Router** (Chen et al., 2026): Workload-Router-Pool architecture — three-dimensional routing framework
- **Calibrated cascading validates our approach**: Our FrugalGPT cascade with YES/NO judge maps directly to UCCI's calibration-gated escalation

### Facet 2: Top GitHub Repos
- **LLMLingua** (Microsoft, ★6,400): 20x compression, <5% quality loss, pip install llmlingua
- **copium** (★11, fast-growing): 65-90% token savings, zero quality loss, MCP-compatible
- **token-optimizer-mcp** (★434): 95%+ token reduction, caching + compression + smart tool intelligence
- **Our approach validated**: Relevance Compression + RTK + Session Dedup aligns with proven compression patterns

### Facet 3: Hackathon Competitive Analysis
- **Top 4 (0 tokens)**: Metis, LeAgent, yassai, how deep is your love — all 0 tokens but only 84.2-94.7% accuracy
- **NidraRoute**: 1,352 tokens, 100% accuracy — benchmark for hybrid approach
- **Frugal Router**: 5,443 tokens, 100% accuracy
- **Key insight**: Only ~73 submissions scored; 216+ failed (PULL_ERROR, TIMEOUT, ACCURACY_GATE_FAILED)
- **Our advantage**: Token count between NidraRoute (1,352) and Frugal Router (5,443) is achievable with higher accuracy

### Facet 4: Common Failure Patterns
- **PULL_ERROR**: Most common failure (30+ entries) — Docker image not public or wrong reference
- **TIMEOUT**: 2nd most common — container exceeded time limit
- **ACCURACY_GATE_FAILED**: 30+ entries with 0-78% accuracy — local-only approaches failing on hard tasks
- **RUNTIME_ERROR**: Container crashed during evaluation
- **OUTPUT_MISSING**: No /output/results.json written

## Identified Gaps & Opportunities
1. **No competitor uses SymPy-LLM Symbiosis** — verified across all top submissions
2. **No competitor has Session Dedup** (shared context batching) — unique advantage
3. **Gemma-aware routing + token optimization** not seen in any top submission
4. **0-token submissions have accuracy ceiling** (~95%) — our hybrid approach can beat them

## Actionable Conclusions
1. ✅ Already implemented: FrugalGPT cascade, compression, per-category max_tokens, prompt caching
2. ✅ Already implemented: 11 Tier-0 solvers, SymPy-LLM, Session Dedup
3. ✅ Already implemented: Gemma tag cleaner, Unicode sanitization, health check
4. ⚠️ Need Fireworks API key for final verification — then ready to submit

## References
- Kotte (2026). UCCI: Calibrated Uncertainty for Cost-Optimal LLM Cascade Routing. arXiv:2605.18796
- Jiang et al. (2025). Cascadia: Co-optimizing Deployment and Routing for LLM Cascades.
- Chen et al. (2026). VLLM Semantic Router.
- Jiang et al. (2023). LLMLingua. EMNLP 2023. arXiv:2310.05736
- Chen et al. (2023). FrugalGPT. arXiv:2305.05176
- Ong et al. (2024). RouteLLM. arXiv:2406.18665
- Wang et al. (2025). MixLLM. NAACL 2025
