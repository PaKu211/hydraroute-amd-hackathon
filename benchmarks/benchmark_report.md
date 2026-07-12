# HydraRoute Benchmark Report

**Date**: 2026-07-12 11:40:16
**Total Tasks**: 67
**Passed**: 65 (97.0%)
**Failed**: 2
**Total Time**: 229.5s
**Avg Time/Task**: 3.43s

## Architecture

| Component | Model/Solver |
|-----------|-------------|
| Tier 0 | 11 local solvers |
| Tier Local | Qwen2.5-1.5B GGUF (optional) |
| Tier 1 API | google/gemma-4-26b-a4b-it (MoE) |
| Tier 2 API | google/gemma-4-31b-it |

## Summary by Category

| Category | Total | Passed | Failed | Pass % | Avg Time (s) |
|----------|-------|--------|--------|--------|-------------|
| code_debugging | 10 | 10 | 0 | 100.0% | 1.86s |
| code_generation | 10 | 10 | 0 | 100.0% | 3.80s |
| deductive_reasoning | 3 | 3 | 0 | 100.0% | 7.89s |
| factual_knowledge | 10 | 9 | 1 | 90.0% | 0.25s |
| logical_reasoning | 7 | 7 | 0 | 100.0% | 14.87s |
| math | 10 | 9 | 1 | 90.0% | 0.66s |
| ner | 5 | 5 | 0 | 100.0% | 2.27s |
| sentiment_classification | 10 | 10 | 0 | 100.0% | 2.18s |
| text_summarization | 2 | 2 | 0 | 100.0% | 1.44s |

## Tier Distribution

| Tier | Count | Percentage |
|------|-------|------------|
| failed | 0 | 0.0% |
| tier_0 | 19 | 28.4% |
| tier_1 | 18 | 26.9% |
| tier_2 | 30 | 44.8% |
| tier_local | 0 | 0.0% |

## Detailed Results

| Task | Category | Result | Tier | Time |
|------|----------|--------|------|------|
| m1 | math | PASS | T0 | 0.3s |
| m2 | math | PASS | T0 | 0.0s |
| m3 | math | PASS | T0 | 0.0s |
| m4 | math | PASS | T0 | 0.0s |
| m5 | math | PASS | T0 | 0.1s |
| m6 | math | PASS | T0 | 0.0s |
| m7 | math | PASS | T0 | 0.0s |
| m8 | math | PASS | T0 | 0.0s |
| m9 | math | PASS | T0 | 1.9s |
| m10 | math | FAIL | T1 | 4.2s |
| f1 | factual_knowledge | PASS | T1 | 0.0s |
| f2 | factual_knowledge | PASS | T1 | 0.0s |
| f3 | factual_knowledge | PASS | T1 | 0.0s |
| f4 | factual_knowledge | PASS | T1 | 0.0s |
| f5 | factual_knowledge | PASS | T1 | 0.0s |
| f6 | factual_knowledge | FAIL | T1 | 0.0s |
| f7 | factual_knowledge | PASS | T1 | 0.4s |
| f8 | factual_knowledge | PASS | T1 | 1.0s |
| f9 | factual_knowledge | PASS | T1 | 0.5s |
| f10 | factual_knowledge | PASS | T1 | 0.7s |
| s1 | sentiment_classification | PASS | T0 | 0.0s |
| s2 | sentiment_classification | PASS | T0 | 0.0s |
| s3 | sentiment_classification | PASS | T0 | 0.0s |
| s4 | sentiment_classification | PASS | T0 | 7.3s |
| s5 | sentiment_classification | PASS | T0 | 0.0s |
| s6 | sentiment_classification | PASS | T0 | 3.7s |
| s7 | sentiment_classification | PASS | T0 | 0.0s |
| s8 | sentiment_classification | PASS | T0 | 10.7s |
| s9 | sentiment_classification | PASS | T0 | 0.0s |
| s10 | sentiment_classification | PASS | T0 | 0.0s |
| n1 | ner | PASS | T1 | 1.6s |
| n2 | ner | PASS | T1 | 2.4s |
| n3 | ner | PASS | T1 | 2.9s |
| n4 | ner | PASS | T1 | 2.0s |
| n5 | ner | PASS | T1 | 2.4s |
| sum1 | text_summarization | PASS | T1 | 2.3s |
| sum2 | text_summarization | PASS | T1 | 0.6s |
| l1 | logical_reasoning | PASS | T2 | 7.3s |
| l2 | logical_reasoning | PASS | T2 | 17.3s |
| l3 | logical_reasoning | PASS | T2 | 5.4s |
| l4 | logical_reasoning | PASS | T2 | 7.0s |
| l5 | logical_reasoning | PASS | T2 | 41.3s |
| l6 | deductive_reasoning | PASS | T2 | 7.5s |
| l7 | deductive_reasoning | PASS | T2 | 5.4s |
| l8 | logical_reasoning | PASS | T2 | 16.6s |
| l9 | logical_reasoning | PASS | T2 | 9.2s |
| l10 | deductive_reasoning | PASS | T2 | 10.8s |
| c1 | code_generation | PASS | T2 | 3.3s |
| c2 | code_generation | PASS | T2 | 0.0s |
| c3 | code_generation | PASS | T2 | 8.5s |
| c4 | code_generation | PASS | T2 | 4.4s |
| c5 | code_generation | PASS | T2 | 3.8s |
| c6 | code_generation | PASS | T2 | 2.3s |
| c7 | code_generation | PASS | T2 | 3.8s |
| c8 | code_generation | PASS | T2 | 2.4s |
| c9 | code_generation | PASS | T2 | 2.3s |
| c10 | code_generation | PASS | T2 | 7.1s |
| d1 | code_debugging | PASS | T2 | 1.5s |
| d2 | code_debugging | PASS | T2 | 1.6s |
| d3 | code_debugging | PASS | T2 | 1.8s |
| d4 | code_debugging | PASS | T2 | 2.6s |
| d5 | code_debugging | PASS | T2 | 4.3s |
| d6 | code_debugging | PASS | T2 | 1.5s |
| d7 | code_debugging | PASS | T2 | 0.6s |
| d8 | code_debugging | PASS | T2 | 1.7s |
| d9 | code_debugging | PASS | T2 | 2.1s |
| d10 | code_debugging | PASS | T2 | 0.9s |
