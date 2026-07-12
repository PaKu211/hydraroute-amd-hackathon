# Literature Review: Token-Efficient LLM Routing & Optimization

## Summary
Four parallel literature reviews synthesized findings on: (1) token compression techniques, (2) Gemma 4 API optimization, (3) LLM-hackathon winning strategies, and (4) local SLM deployment in Docker. Key findings converge on three high-impact, implementable-today strategies: (a) OpenRouter `verbosity=low` + `reasoning.exclude=true` for massive output token savings, (b) prompt KV-cache prefix reuse already implemented, (c) bundled Qwen2.5-1.5B GGUF via llama.cpp for 0-token local inference.

## Key Findings by Facet

### Facet 1: Token Compression
- LLMLingua achieves 2-20x compression with minimal accuracy loss (Jiang et al., 2023, EMNLP)
- Structure-aware pruning preserves discourse integrity better than token-level deletion
- Grammar-constrained decoding (XGrammar, 2024-2025) achieves near-zero-overhead structured output
- Output token minimization via forced short formats saves 40-60%

### Facet 2: Gemma 4 API Optimization
- OpenRouter exposes `verbosity` (low/medium/high/xhigh) and `reasoning.exclude=true` parameters
- 26B MoE: $0.06/M input (half of 31B's $0.12/M), same strong accuracy (82.6% vs 85.2% MMLU Pro)
- Default sampling: temperature=1.0, top_p=0.95 — lower temperature recommended for deterministic output
- 256K context on both models

### Facet 3: Winning Hackathon Strategies
- FrugalGPT: 98% cost reduction matching GPT-4 quality (Chen et al., 2023)
- RouteLLM: 85% cost savings at 95% GPT-4 quality (Ong et al., 2024)
- MixLLM: 97.25% GPT-4 quality at 24.18% cost — current SOTA Pareto frontier (Wang et al., 2025, NAACL)
- KV-cache reuse (CachedAttention): 70% cost reduction in multi-turn (Gao et al., 2024)
- Router methods > cascade methods for <12h hackathon builds

### Facet 4: Local SLM in Docker
- llama.cpp + GGUF = gold standard for Docker CPU inference
- Pre-built image: ghcr.io/ggml-org/llama.cpp (<20 MB binary)
- Qwen2.5-1.5B Q4_K_M ≈ 0.9 GB — fits easily in 4 GB container
- Phi-3-mini 3.8B Q4 ≈ 2.2 GB — pushes container limit but better reasoning
- llama.cpp 3-10x faster than PyTorch for CPU inference

## Actionable Conclusions
1. **IMMEDIATE**: Add `verbosity=low` + `reasoning.exclude=true` to OpenRouter calls — saves 40-80% reasoning tokens
2. **OPTIONAL HIGH-IMPACT**: Bundle Qwen2.5-1.5B GGUF via llama.cpp for 0-token sentiment/NER/factual
3. **ALREADY DONE**: Prompt caching, max_tokens minimization, system prompt compression

## References
- Jiang et al. (2023). LLMLingua. EMNLP 2023. arXiv:2310.05736
- Chen et al. (2023). FrugalGPT. arXiv:2305.05176
- Ong et al. (2024). RouteLLM. arXiv:2406.18665
- Wang et al. (2025). MixLLM. NAACL 2025
- Gao et al. (2024). CachedAttention.
- Google DeepMind (2026). Gemma 4 Technical Report.
