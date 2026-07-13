# Research Deliberation: HydraRoute as an Academic Paper

## Knowledge Consolidation

From 47 verified papers across three facets, the following picture emerges:

1. **LLM routing is a maturing field** — FrugalGPT (849+ citations) established cascades; RouteLLM (ICLR 2025) and MixLLM (NAACL 2025) extended with learned routing; SATER (EMNLP 2025) unified routing paradigms. **No system demonstration paper exists.**

2. **Token compression is well-studied** — LLMLingua (1,200+ combined citations) dominates learned compression. **No comparison between learned and deterministic compression in routing context.**

3. **LLM + symbolic solver is established but focused on code generation** — PAL (NeurIPS 2022) generates Python; PoT generates code; Logic-LM generates first-order logic. **No paper specifically uses LLMs to generate SymPy equations.**

4. **System-level papers for LLM routing are absent** — 11 papers on routing theory, zero papers presenting an end-to-end production routing agent.

## Knowledge Gaps & Contradictions

- **Gap 1**: No system combines pre-LLM deterministic solvers + cascade routing + compression
- **Gap 2**: No paper compares learned compression vs. deterministic compression in routing
- **Gap 3**: SymPy-LLM (LLM as equation translator) is novel — not in existing literature
- **Gap 4**: System demo gap — routing theory papers exist but no practical implementation

## Candidate Hypotheses

### H1: Deterministic pre-LLM tier outperforms cascade-only routing on cost-accuracy
- Test: Ablation study — HydraRoute (all tiers) vs. HydraRoute (Tier 0 disabled)
- Novelty: HIGH — no existing paper has this comparison
- Feasibility: HIGH — we have the system and benchmark suite

### H2: Deterministic compression achieves comparable savings to learned (LLMLingua)
- Requires integrating LLMLingua as baseline — engineering cost
- Feasibility: MEDIUM

### H3: SymPy-LLM achieves 100% math accuracy vs. direct LLM solving
- Easy to test, but confirmatory (PAL already shows similar)
- Feasibility: HIGH, Novelty: LOW

### H4: HydraRoute as a system demo fills a literature gap
- Best publication path: ACL/EMNLP System Demo (4-6 pages)
- Feasibility: HIGH, Novelty: HIGH for demo venues

## Structured Deliberation

| Hypothesis | Strengths | Key Uncertainty | Info Gain |
|------------|-----------|----------------|-----------|
| H1 (Pre-LLM tier) | Strong data, testable, novel | Does Tier 0 contribute enough? | HIGH |
| H2 (Deterministic compression) | Fills gap | LLMLingua integration cost | MEDIUM |
| H3 (SymPy-LLM accuracy) | Easy to test | Confirms known result | LOW |
| H4 (System demo) | Strongest pub path | Novelty bar? | HIGH |

## Selected Direction

**Chosen**: H1 (pre-LLM tier improves cascade) + H4 (system demo paper)

**Rationale**: 
- H1 is the strongest scientific claim — the concept "avoid LLM calls entirely for solvable tasks before routing" is absent from all 11 routing papers
- H4 is the most realistic publication path

**Success criteria**:
1. Ablation: Tier 0 provides ≥40% token savings with ≥95% accuracy
2. System processes 67 benchmark tasks within 5 minutes
3. Cost analysis shows ≥60% savings vs. always-large-model

**Fallback**: If H1 evidence weak, pivot to SymPy-LLM (H3) as novelty — narrower but solid.
