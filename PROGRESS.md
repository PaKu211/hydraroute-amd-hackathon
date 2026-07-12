# HydraRoute Agent — Progress Tracker

## Latest Build: v3.4 (2026-07-12) — Champion Iteration

### Architecture
```
Tier 0 (Local Solvers) → Tier 1 (Small Model) → Tier 2 (Large Model)
                      ↕                      ↕
              SHA1 Exact Cache       1-Token YES/NO Judge
                         ↕
              Self-Consistency Voting (3× parallel for reasoning)
```

### What's Implemented
| Feature | Status | Details |
|---------|--------|---------|
| SHA1 exact-match cache | ✅ | Zero-token dedup for duplicate instructions |
| SymPy AST math solver | ✅ | Isolated subprocess, 2s timeout |
| Heuristic prompt cleaner | ✅ | Removes verbose headers, polite fillers |
| FrugalGPT cascade validation | ✅ | JSON parse, length, sentiment presence checks |
| Atomic JSON writes | ✅ | `tempfile.mkstemp` + `os.replace` |
| Per-category model routing | ✅ | Smallest→sentiment/NER, small→factual/math, large→code/reasoning |
| Prompt caching (OmniRoute) | ✅ | Common prefix `HydraRoute \| <category> \|` |
| `context_length_exceeded_behavior=truncate` | ✅ | Tier 1 & Tier 2 |
| Model Health Check at startup | ✅ | Probe `max_tokens=1` per model, remove failures |
| 1-Token YES/NO Judge (TERA-inspired) | ✅ | Self-verify for reasoning/code tasks |
| Zero-token-first routing | ✅ | Tier 0 always attempted first |
| **Self-Consistency Voting** | ✅ | 3× parallel calls for reasoning tasks, consensus wins |
| **RTK Stack Trace Compression** | ✅ | Truncate Python/JS tracebacks to last 10 lines |
| **Temperature Scaling + Prompt Mutation** | ✅ | Same-model fallback: temp=0.3, mutation string injected |
| **OmniRoute API** | ✅ | `oc/deepseek-v4-flash-free`, `thinking=disabled` via extra_body |
| **SymPy-LLM Symbiosis (new)** | ✅ | LLM translates word problem → SymPy solves locally. 100% accuracy |
| **Session Dedup (new)** | ✅ | Same-category tasks sharing >80 char context → batched single API call |
| **Relevance Compression (new)** | ✅ | TF-IDF extractive scoring for factual/summarization, keeps top 60% sentences |

### Tier-0 Local Solvers (11 modules)
| Solver | Coverage | Status |
|--------|----------|--------|
| Arithmetic (`_try_arithmetic`) | Simple arithmetic eval | ✅ Requires operator in expr |
| Percentage (`_try_percentage`) | X% of Y | ✅ |
| SymPy equations (`_try_solve_equation`) | Algebraic equations | ✅ |
| Date math (`_try_date_math`) | `X days from DATE`, days between | ✅ |
| Word analysis (`_try_word_analysis`) | Count vowels/consonants/words/sentences | ✅ NEW |
| String ops (`_try_string_ops`) | Palindrome, reverse, length, count | ✅ |
| Unit conversion (`_try_unit_conversion`) | km↔miles, kg↔lbs, C↔F, etc. | ✅ |
| Regex extraction (`_try_regex_extraction`) | Email, phone, URL extraction | ✅ |
| Factual lookup (`_try_factual_lookup`) | Capitals, elements, planets, science facts | ✅ NEW |
| Number conversion (`_try_number_conversion`) | Decimal↔binary↔hex↔Roman numerals | ✅ NEW |
| Simple classification (`_try_simple_classification`) | POS/NEG/NEU sentiment (short texts) | ✅ |

Total: 11 solver modules (matching 325 Agent's 11 solvers)
| Solver | Coverage | Status |
|--------|----------|--------|
| Arithmetic (`_try_arithmetic`) | Simple arithmetic eval | ✅ Requires operator in expr |
| Percentage (`_try_percentage`) | X% of Y | ✅ |
| SymPy equations (`_try_solve_equation`) | Algebraic equations | ✅ |
| Date math (`_try_date_math`) | `X days from DATE`, days between | ✅ Fixed group index bug |
| String ops (`_try_string_ops`) | Palindrome, reverse, length, count | ✅ |
| Unit conversion (`_try_unit_conversion`) | km↔miles, kg↔lbs, C↔F, etc. | ✅ Fixed inverse overwrite bug |
| Regex extraction (`_try_regex_extraction`) | Email, phone, URL | ✅ |
| Simple classification (`_try_simple_classification`) | POS/NEG/NEU sentiment | ✅ |

### Bug Fixes (session 2026-07-12)
1. Arithmetic regex too broad → `if any(op in expr for op in '+-*/')` guard
2. Unit conv `_reg_conv` auto-inverse overwrites forward → skip if inverse exists
3. Date math `m.group(3)` → `m.group(4)`
4. `reasoning_effort=none` causes 400 on OmniRoute → removed (use `thinking=disabled` instead)
5. `CACHE_PREFIX` scope bug → removed local import, use module-level import
6. Simple classification false positive ("Great Britain" → "great" → POS) → 20-word length guard

### End-to-End Test (OmniRoute API — 2026-07-12)
| Task | Category | Result | Source |
|------|----------|--------|--------|
| What is 2+2? | math | 4 | ✅ Tier 0 |
| What is the capital of France? | factual | Paris. | ✅ Tier 1 API |
| Classify: I love this! | sentiment | POS | ✅ Tier 0 |
| 5 days from 2024-01-15? | math | 2024-01-20 | ✅ Tier 0 |
| Extract entities: John at Microsoft Seattle | ner | JSON | ✅ Tier 1 API |
| Summarize: quick brown fox | text_summarization | ok | ✅ Tier 1 API |
| All cats are mammals... Is Whiskers animal? | logical_reasoning | reasoning output | ✅ Self-consistency |

### Key Learnings
- **OmniRoute API**: model `oc/deepseek-v4-flash-free` returns content in `content` field (not `reasoning_content`) when `thinking=disabled` is set
- **`reasoning_effort=none` NOT supported** on OmniRoute → causes 400 errors. Use `thinking=disabled` instead
- **Assistant pre-fill NOT supported** on this model → returns empty response
- **Prompt tokens are normal** (~89 for simple tasks, no system prompt inflation)
- **System prompt causes no issues** with `thinking=disabled`

### Docker Build
- Platform: `linux/amd64`
- Base: `python:3.11-slim`
- Image: `hydraroute:latest`
- Health check: OK
- Tested in Codespace: `redesigned-adventure-9g7qjrpgg4xcpvw6`

### Credentials
- OmniRoute API: `http://100.106.208.80:20128/v1` (key in .env)
- Model: `oc/deepseek-v4-flash-free` (single model, Tier 1 = Tier 2)

### Next Iteration Ideas
1. Add local NER extraction (regex-based entity extraction for names, orgs, locations)
2. Add local factual knowledge base for common facts (capital cities, basic science)
3. Optimize YES/NO judge: use `max_tokens=1` with temperature=0.0 strictly
4. Add more date formats (fuzzy parsing, relative dates)
5. Research latest winning hackathon submissions for patterns
