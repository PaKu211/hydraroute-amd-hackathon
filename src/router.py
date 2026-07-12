"""
Router module for HydraRoute Agent (v3 - Dynamic Heuristic Difficulty Estimation).
Determines the target execution tier dynamically using category heuristics and prompt complexity indicators.
Implements fallback chains: Tier 0 -> Tier 1 -> Tier 2.
"""

import logging
import re

from openai import OpenAI

from src.config import Config, CATEGORY_CONFIG, DEFAULT_CATEGORY_CONFIG, CACHE_PREFIX
from src.token_tracker import TokenTracker
from src.tiers import tier_zero, tier_one, tier_two

logger = logging.getLogger("hydraroute")

# Map category name variations to canonical names
CATEGORY_ALIASES: dict[str, str] = {
    "math": "math",
    "mathematical_reasoning": "mathematical_reasoning",
    "maths": "math",
    "arithmetic": "math",
    "sentiment": "sentiment_classification",
    "sentiment_classification": "sentiment_classification",
    "sentiment_analysis": "sentiment_classification",
    "summarization": "text_summarization",
    "text_summarization": "text_summarization",
    "summary": "text_summarization",
    "ner": "ner",
    "named_entity_recognition": "named_entity_recognition",
    "entity_recognition": "ner",
    "factual_knowledge": "factual_knowledge",
    "factual": "factual_knowledge",
    "knowledge": "factual_knowledge",
    "code_debugging": "code_debugging",
    "debugging": "code_debugging",
    "debug": "code_debugging",
    "logical_reasoning": "logical_reasoning",
    "deductive_reasoning": "logical_reasoning",
    "reasoning": "logical_reasoning",
    "logic": "logical_reasoning",
    "code_generation": "code_generation",
    "code_gen": "code_generation",
    "coding": "code_generation",
}


def normalize_category(category: str) -> str:
    """Normalize category name to match CATEGORY_CONFIG keys."""
    cat = category.strip().lower().replace("-", "_").replace(" ", "_")

    # Check aliases
    if cat in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[cat]

    # Check if it directly matches a config key
    if cat in CATEGORY_CONFIG:
        return cat

    # Fuzzy match: check if any config key is contained in the category
    for key in CATEGORY_CONFIG:
        if key in cat or cat in key:
            return key

    logger.warning("Unknown category '%s', using default config", category)
    return cat


def get_category_config(category: str) -> dict:
    """Get the configuration for a normalized category."""
    normalized = normalize_category(category)
    return CATEGORY_CONFIG.get(normalized, DEFAULT_CATEGORY_CONFIG)


def estimate_difficulty(instruction: str, category: str) -> int:
    """Dynamically estimate prompt difficulty using local heuristics (Marginal Utility / RouteLMT inspired).

    Returns:
        1: Tier 1 (Small model is sufficient)
        2: Tier 2 (Large reasoning model required)
    """
    # Marginal Utility: Sentiment classification NEVER needs Tier 2 reasoning (utility is zero)
    if category == "sentiment_classification":
        return 1

    text = instruction.lower()
    word_count = len(text.split())

    # Indicators of high logical/debugging complexity
    complex_indicators = [
        "debug",
        "fix the bug",
        "traceback",
        "runtimeerror",
        "syntaxerror",
        "logical puzzle",
        "explain step by step",
        "prove",
        "mathematical proof",
        "write a class",
        "implement a complex",
        "algorithm",
        "recursive",
        "concurrency",
        "nested",
        "complex",
        "o(n",
        "space complexity",
    ]
    has_indicators = any(ind in text for ind in complex_indicators)

    # Coding structural characters (indicates code block analysis)
    has_code_structure = (
        "```" in text or "def " in text or "class " in text or "import " in text
    )

    # Ambiguity and conditional logic clauses (indicates high reasoning difficulty)
    conditional_keywords = [
        "unless",
        "except when",
        "only if",
        "provided that",
        "otherwise",
    ]
    has_conditionals = any(cond in text for cond in conditional_keywords)

    # Score calculation
    score = 0
    if word_count > 80:
        score += 2
    elif word_count > 40:
        score += 1

    if has_indicators:
        score += 2
    if has_code_structure:
        score += 3
    if has_conditionals:
        score += 2  # Ambiguity penalty: escalate to protect Accuracy Gate

    # Dynamic adjustment based on Marginal Utility
    if category in ("code_generation", "code_debugging", "logical_reasoning"):
        # Default is Tier 2, but downgrade to Tier 1 if extremely short, simple, and has no conditionals
        if score <= 1 and word_count < 25 and not has_conditionals:
            logger.info(
                "Task classified as SIMPLE reasoning (score=%d), downgrading to Tier 1",
                score,
            )
            return 1
        return 2

    if category in ("factual_knowledge", "text_summarization", "ner"):
        # Default is Tier 1, but escalate to Tier 2 if extremely long, complex, or conditional-heavy
        if score >= 4 or (has_conditionals and word_count > 50):
            logger.info(
                "Task classified as COMPLEX context (score=%d), escalating to Tier 2",
                score,
            )
            return 2
        return 1

    return 1


def _normalize_json_string(text: str) -> str:
    """Extracts and normalizes a JSON object or list from text, stripping markdown and text wrappers, and compacts it (Headroom compression)."""
    if not text:
        return ""
    cleaned = text.strip()
    import re
    import json

    # 1. Search for a JSON structure '{...}' or '[...]'
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if match:
        json_candidate = match.group(1).strip()
        try:
            parsed = json.loads(json_candidate)
            # Serialize to minified JSON (Headroom compression)
            return json.dumps(parsed, separators=(",", ":"))
        except Exception:
            pass

    # 2. Fallback to parsing the raw cleaned string
    try:
        parsed = json.loads(cleaned)
        return json.dumps(parsed, separators=(",", ":"))
    except Exception:
        pass

    return cleaned


def _is_valid_tier_one_response(answer: str, category: str) -> bool:
    """Validate output of Tier 1 using heuristics to decide if escalation is required."""
    if not answer or len(answer.strip()) == 0:
        return False

    cleaned = answer.strip()
    import json

    # 1. Detection of failure/apology phrases
    apologies = [
        "i do not know",
        "i cannot answer",
        "i'm sorry",
        "sorry, but",
        "i am unable to",
        "as an ai",
        "could not determine",
        "api error",
    ]
    if any(apology in cleaned.lower() for apology in apologies):
        logger.warning(
            "Tier 1 output contains apology/failure indicator. Escalating..."
        )
        return False

    # 2. Sentiment validation (must be POS, NEG, or NEU)
    if category == "sentiment_classification":
        import re

        label = re.sub(r"[^a-zA-Z]", "", cleaned).upper()
        if label not in ("POS", "NEG", "NEU"):
            logger.warning("Tier 1 sentiment '%s' is invalid. Escalating...", cleaned)
            return False

    # 3. Named Entity Recognition validation (must be JSON parseable)
    if category in ("ner", "named_entity_recognition"):
        normalized = _normalize_json_string(cleaned)
        try:
            json.loads(normalized)
        except Exception:
            logger.warning("Tier 1 NER output is not valid JSON. Escalating...")
            return False

    # 4. Fallback math tasks
    if category in ("math", "mathematical_reasoning"):
        if len(cleaned.split()) > 20:
            logger.warning("Tier 1 math output is too verbose. Escalating...")
            return False

    # 5. Logical/Deductive reasoning tasks
    if category in ("logical_reasoning", "deductive_reasoning"):
        # If the task requests step-by-step or explanation, ensure the output has sufficient length
        if len(cleaned.split()) < 10:
            logger.warning("Tier 1 reasoning output is too short. Escalating...")
            return False

    return True


def route_batch(
    batched_task: dict,
    config: Config,
    client: OpenAI,
) -> list[dict]:
    """Route a batched task: multiple questions sharing context, single API call.

    batched_task has _subtasks list and optionally _shared_context.
    Sends combined prompt, parses JSON array response, maps answers to subtasks.
    """
    subtasks = batched_task.get("_subtasks", [])
    if not subtasks:
        return [
            {
                "task_id": batched_task.get("task_id"),
                "answer": str(batched_task.get("answer", "")),
            }
        ]

    category = batched_task.get("category", "unknown")
    shared_context = batched_task.get("_shared_context", "")

    # Build numbered questions
    questions = []
    for i, st in enumerate(subtasks, 1):
        inst = str(st.get("instruction", "")).strip()
        # Remove the shared context from the instruction to avoid redundancy
        if shared_context and shared_context in inst:
            inst = inst.replace(shared_context, "").strip().strip(".,;: ")
        questions.append(f"{i}. {inst}")

    combined_prompt = (
        f"Answer all {len(questions)} questions below based on the shared context. "
        f"Return a JSON array of answers in order.\n\n"
        f"Shared context: {shared_context}\n\n"
        f"Questions:\n" + "\n".join(questions)
    )

    logger.info(
        "Batched task [%s]: %d subtasks, combined prompt %d chars",
        category,
        len(subtasks),
        len(combined_prompt),
    )

    model = config.get_model_for_category(batched_task.get("category", ""))
    if not model:
        model = config.large_model
    if not model:
        return [
            {"task_id": st["task_id"], "answer": "I could not determine the answer."}
            for st in subtasks
        ]

    cat_config = get_category_config(category)
    system_prompt = cat_config.get("system_prompt", "Answer concisely.")

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt + " Return answers as a JSON array.",
                },
                {"role": "user", "content": combined_prompt},
            ],
            max_tokens=cat_config.get("max_tokens", 300) * len(subtasks),
            temperature=0.0,
            extra_body={
                "context_length_exceeded_behavior": "truncate",
                "thinking": {"type": "disabled"},
            },
        )
        raw = resp.choices[0].message.content or ""
        import json

        # Parse JSON array from response
        answers = _extract_json_array(raw)
        if answers and len(answers) == len(subtasks):
            results = []
            for st, ans in zip(subtasks, answers):
                results.append({"task_id": st["task_id"], "answer": str(ans)})
                logger.debug("Batched subtask %s: [%s]", st["task_id"], str(ans)[:80])
            # Record tokens once for the batch
            from src.token_tracker import TokenTracker

            if resp.usage:
                TokenTracker().record(
                    task_id=f"batch_{category}",
                    model=model,
                    prompt_tokens=resp.usage.prompt_tokens or 0,
                    completion_tokens=resp.usage.completion_tokens or 0,
                )
            return results
        else:
            logger.warning(
                "Batched response parse failed or size mismatch, falling back to individual routing"
            )
    except Exception as e:
        logger.warning(
            "Batched call failed (%s), falling back to individual routing", e
        )

    # Fallback: process each subtask individually
    return [route_task(st, config, client) for st in subtasks]


def _extract_json_array(text: str) -> list | None:
    """Extract a JSON array from model response text."""
    if not text:
        return None
    import json

    # Try direct parse
    text = text.strip()
    try:
        return json.loads(text) if isinstance(json.loads(text), list) else None
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code block
    m = __import__("re").search(
        r"```(?:json)?\s*(\[.*?\])\s*```", text, __import__("re").DOTALL
    )
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try extracting [...] pattern
    m = __import__("re").search(r"(\[.*?\])", text, __import__("re").DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


def route_task(
    task: dict,
    config: Config,
    client: OpenAI,
) -> str:
    """Route a single task to the appropriate tier and return the answer.

    Implements zero-token-first fallback chain:
        Tier 0 (local solvers) -> Tier 1 (small model) -> Tier 2 (large model)

    Always attempts Tier 0 first regardless of category (zero token cost).
    Falls back to dynamic heuristic difficulty estimation for API tiers.

    Args:
        task: Task dict with task_id, category, instruction.
        config: Runtime configuration with model assignments.
        client: OpenAI-compatible client for API calls.

    Returns:
        Answer string. Never returns None - falls back to error message.
    """
    task_id = task["task_id"]
    category = task["category"]
    instruction = task["instruction"]

    normalized_cat = normalize_category(category)
    cat_config = get_category_config(normalized_cat)

    # ── Step 0: Always try Tier 0 first (zero token cost) ──
    logger.info("Routing task %s [%s] -> Tier 0 (Local Solvers)", task_id, category)
    try:
        answer = tier_zero.execute(instruction)
        if answer is not None:
            TokenTracker().record_tier_zero()
            logger.info("Task %s solved by Tier 0", task_id)
            return answer
    except Exception as e:
        logger.warning("Tier 0 failed for task %s: %s", task_id, e)

    # ── Step 1: Estimate difficulty for API tier selection ──
    target_tier = estimate_difficulty(instruction, normalized_cat)
    logger.info(
        "Routing task %s [%s] -> Tier %d (Estimated)", task_id, category, target_tier
    )

    answer = None

    # Apply prompt compression for API calls (Tier 1 & Tier 2)
    try:
        from src.compression import PromptCompressor

        instruction_optimized = PromptCompressor().optimize(instruction, normalized_cat)
    except Exception as e:
        logger.warning("Prompt compression failed: %s", e)
        instruction_optimized = instruction

    # ── SymPy-LLM Symbiosis: LLM translates word problem → SymPy solves locally ──
    # Zero-risk: LLM only generates equation string, SymPy guarantees correct solution
    if normalized_cat in ("math", "mathematical_reasoning") and config.large_model:
        logger.info("Task %s: Trying SymPy-LLM Symbiosis", task_id)
        try:
            eq_prompt = (
                "Translate this math word problem into a single valid Python SymPy equation "
                "string. DO NOT solve it. Output ONLY the equation string, nothing else.\n\n"
                f"Word problem: {instruction}"
            )
            eq_resp = client.chat.completions.create(
                model=config.large_model,
                messages=[
                    {
                        "role": "system",
                        "content": f"{CACHE_PREFIX} | math | Translate to SymPy equation. Output ONLY the equation string.",
                    },
                    {"role": "user", "content": eq_prompt},
                ],
                max_tokens=100,
                temperature=0.0,
                extra_body={"context_length_exceeded_behavior": "truncate"},
            )
            eq_raw = eq_resp.choices[0].message.content
            if not eq_raw or not eq_raw.strip():
                eq_raw = getattr(eq_resp.choices[0].message, "reasoning_content", None)
            if eq_raw:
                # Clean the equation string: strip markdown, backticks, code fences
                eq_clean = eq_raw.strip()
                eq_clean = (
                    re.sub(r"```(?:python|sympy)?", "", eq_clean)
                    .replace("```", "")
                    .strip()
                )
                eq_clean = re.sub(r"^[^a-zA-Z0-9(=]+", "", eq_clean)  # leading noise
                eq_clean = eq_clean.rstrip(".,; ")
                logger.info("SymPy-LLM equation: %s", eq_clean)
                sympy_answer = tier_zero.solve_equation_string(eq_clean)
                if sympy_answer is not None:
                    TokenTracker().record(
                        task_id=task_id,
                        model=config.large_model,
                        prompt_tokens=eq_resp.usage.prompt_tokens or 0,
                        completion_tokens=eq_resp.usage.completion_tokens or 0,
                    )
                    logger.info(
                        "Task %s solved by SymPy-LLM Symbiosis: %s",
                        task_id,
                        sympy_answer,
                    )
                    return sympy_answer
        except Exception as e:
            logger.warning("SymPy-LLM Symbiosis failed for task %s: %s", task_id, e)

    # ── Tier 1: Category-appropriate model ──
    tier1_model = config.get_model_for_category(normalized_cat)
    is_same_model_fallback = False

    if target_tier <= 1 and tier1_model:
        # Self-Consistency Majority Voting for reasoning tasks (3 parallel calls)
        if normalized_cat in ("logical_reasoning", "deductive_reasoning"):
            import concurrent.futures

            def _single_call() -> str | None:
                return tier_one.execute(
                    client=client,
                    model=tier1_model,
                    instruction=instruction_optimized,
                    category=category,
                    category_config=cat_config,
                    task_id=task_id,
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                futures = [pool.submit(_single_call) for _ in range(3)]
                votes: list[str] = []
                for f in futures:
                    try:
                        r = f.result(timeout=20)
                        if r:
                            votes.append(r.strip())
                    except Exception:
                        continue

            if len(votes) >= 2:
                from collections import Counter

                counter = Counter(votes)
                top_answer, top_count = counter.most_common(1)[0]
                if top_count >= 2:
                    logger.info(
                        "Task %s: Self-consistency consensus (%d/3) -> '%s'",
                        task_id,
                        top_count,
                        top_answer[:80],
                    )
                    return top_answer
                elif len(votes) == 3:
                    logger.info(
                        "Task %s: No consensus (all differ), using first: '%s'",
                        task_id,
                        votes[0][:80],
                    )
                    answer = votes[0]
                else:
                    answer = None
            else:
                answer = None
        else:
            answer = None

        # Normal single-call path
        try:
            if answer is None:
                answer = tier_one.execute(
                    client=client,
                    model=tier1_model,
                    instruction=instruction_optimized,
                    category=category,
                    category_config=cat_config,
                    task_id=task_id,
                )

            if answer and _is_valid_tier_one_response(answer, normalized_cat):
                if normalized_cat in ("ner", "named_entity_recognition"):
                    answer = _normalize_json_string(answer)

                # TERA-inspired 1-Token YES/NO judge
                if normalized_cat in (
                    "logical_reasoning",
                    "deductive_reasoning",
                    "code_debugging",
                    "code_generation",
                ):
                    judge_prompt = (
                        f"Does this answer logically solve the prompt? "
                        f"Reply only YES or NO.\n\n"
                        f"Prompt: {instruction}\n\n"
                        f"Answer: {answer}"
                    )
                    try:
                        judge_resp = client.chat.completions.create(
                            model=tier1_model,
                            messages=[
                                {
                                    "role": "system",
                                    "content": f"{CACHE_PREFIX} | judge | Validate correctness. Reply only YES or NO.",
                                },
                                {"role": "user", "content": judge_prompt},
                            ],
                            max_tokens=2,
                            temperature=0.0,
                            extra_body={"context_length_exceeded_behavior": "truncate"},
                        )
                        verdict = (
                            (judge_resp.choices[0].message.content or "")
                            .strip()
                            .upper()
                        )
                        if not verdict.startswith("YES"):
                            logger.info(
                                "Task %s: Self-judge '%s', escalating", task_id, verdict
                            )
                            answer = None
                    except Exception as judge_e:
                        logger.warning(
                            "Task %s: Judge failed (%s), accepting answer",
                            task_id,
                            judge_e,
                        )

                if answer:
                    return answer
        except Exception as e:
            logger.warning("Tier 1 failed for task %s: %s", task_id, e)

        logger.info("Tier 1 fallback -> Tier 2 for task %s", task_id)
        is_same_model_fallback = tier1_model == config.large_model

    # ── Tier 2: Large model (category-preferred or fallback) ──
    if config.large_model:
        try:
            t2_config = CATEGORY_CONFIG.get(normalized_cat, cat_config)

            # Temperature scaling + prompt mutation for same-model fallback
            if is_same_model_fallback:
                mutated_config = dict(t2_config)
                mutated_config["temperature"] = 0.3
                mutated_system = mutated_config.get(
                    "system_prompt",
                    "Provide a correct answer.",
                )
                mutated_config["system_prompt"] = (
                    f"{mutated_system} CRITICAL: Your previous attempt was invalid. "
                    f"Respond with a completely different approach. "
                    f"Ensure all required formatting (JSON, labels, etc.) is correct."
                )
                t2_config = mutated_config

            answer = tier_two.execute(
                client=client,
                model=config.large_model,
                instruction=instruction_optimized,
                category=category,
                category_config=t2_config,
                task_id=task_id,
            )
            if answer:
                if normalized_cat in ("ner", "named_entity_recognition"):
                    answer = _normalize_json_string(answer)
                return answer
        except Exception as e:
            logger.error("Tier 2 failed for task %s: %s", task_id, e)

    logger.error("All tiers failed for task %s", task_id)
    return "I could not determine the answer."
