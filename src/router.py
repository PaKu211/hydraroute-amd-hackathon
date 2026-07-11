"""
Router module for HydraRoute Agent (v3 - Dynamic Heuristic Difficulty Estimation).
Determines the target execution tier dynamically using category heuristics and prompt complexity indicators.
Implements fallback chains: Tier 0 -> Tier 1 -> Tier 2.
"""

import logging
from openai import OpenAI

from src.config import Config, CATEGORY_CONFIG, DEFAULT_CATEGORY_CONFIG
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
        "debug", "fix the bug", "traceback", "runtimeerror", "syntaxerror",
        "logical puzzle", "explain step by step", "prove", "mathematical proof",
        "write a class", "implement a complex", "algorithm", "recursive", "concurrency",
        "nested", "complex", "o(n", "space complexity"
    ]
    has_indicators = any(ind in text for ind in complex_indicators)

    # Coding structural characters (indicates code block analysis)
    has_code_structure = "```" in text or "def " in text or "class " in text or "import " in text

    # Ambiguity and conditional logic clauses (indicates high reasoning difficulty)
    conditional_keywords = ["unless", "except when", "only if", "provided that", "otherwise"]
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
            logger.info("Task classified as SIMPLE reasoning (score=%d), downgrading to Tier 1", score)
            return 1
        return 2

    if category in ("factual_knowledge", "text_summarization", "ner"):
        # Default is Tier 1, but escalate to Tier 2 if extremely long, complex, or conditional-heavy
        if score >= 4 or (has_conditionals and word_count > 50):
            logger.info("Task classified as COMPLEX context (score=%d), escalating to Tier 2", score)
            return 2
        return 1

    return 1


def _normalize_json_string(text: str) -> str:
    """Strips markdown code block wrappers from JSON output if present."""
    import re
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", cleaned, re.DOTALL)
    if match:
        return match.group(1).strip()
    return cleaned


def _is_valid_tier_one_response(answer: str, category: str) -> bool:
    """Validate output of Tier 1 using heuristics to decide if escalation is required."""
    if not answer or len(answer.strip()) == 0:
        return False

    cleaned = answer.strip()
    import json

    # 1. Detection of failure/apology phrases
    apologies = [
        "i do not know", "i cannot answer", "i'm sorry", "sorry, but",
        "i am unable to", "as an ai", "could not determine", "api error"
    ]
    if any(apology in cleaned.lower() for apology in apologies):
        logger.warning("Tier 1 output contains apology/failure indicator. Escalating...")
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


def route_task(
    task: dict,
    config: Config,
    client: OpenAI,
) -> str:
    """Route a single task to the appropriate tier and return the answer.

    Implements fallback chain:
        Tier 0 (local) -> Tier 1 (small model) -> Tier 2 (large model)

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
    config_tier = cat_config.get("tier", 1)

    # 1. Math tasks go to Tier 0 (local execution)
    if config_tier == 0:
        logger.info("Routing task %s [%s] -> Tier 0 (Local Math Solver)", task_id, category)
        try:
            answer = tier_zero.execute(instruction)
            if answer is not None:
                TokenTracker().record_tier_zero()
                logger.info("Task %s solved by Tier 0", task_id)
                return answer
        except Exception as e:
            logger.warning("Tier 0 failed for task %s: %s", task_id, e)

        # Fallback: Tier 0 -> Tier 1 (or Tier 2 if overall difficulty is high)
        logger.info("Tier 0 fallback initiated for task %s", task_id)
        # Check difficulty of the math problem for API fallback
        fallback_tier = estimate_difficulty(instruction, normalized_cat)
        target_tier = fallback_tier
        # Setup fallback prompt config
        cat_config = {
            "system_prompt": "Solve this and output only the final numerical answer.",
            "max_tokens": cat_config.get("max_tokens", 50),
            "temperature": 0.0,
        }
    else:
        # 2. Non-math tasks: Dynamically determine tier using Heuristic Difficulty Estimator
        target_tier = estimate_difficulty(instruction, normalized_cat)
        logger.info("Routing task %s [%s] -> Tier %d (Estimated)", task_id, category, target_tier)

    answer: str | None = None

    # Apply prompt compression for API calls (Tier 1 & Tier 2) to save input tokens
    try:
        from src.compression import PromptCompressor
        instruction_optimized = PromptCompressor().optimize(instruction, normalized_cat)
    except Exception as e:
        logger.warning("Prompt compression failed: %s", e)
        instruction_optimized = instruction

    # ── Tier 1: Small model ──
    if target_tier <= 1 and config.small_model:
        try:
            answer = tier_one.execute(
                client=client,
                model=config.small_model,
                instruction=instruction_optimized,
                category=category,
                category_config=cat_config,
                task_id=task_id,
            )
            # FrugalGPT Cascade validation: escalate if output is invalid
            if answer and _is_valid_tier_one_response(answer, normalized_cat):
                # Ensure NER is returned as clean normalized JSON string
                if normalized_cat in ("ner", "named_entity_recognition"):
                    answer = _normalize_json_string(answer)
                return answer
        except Exception as e:
            logger.warning("Tier 1 failed for task %s: %s", task_id, e)

        # Fallback: Tier 1 -> Tier 2
        logger.info("Tier 1 fallback -> Tier 2 for task %s", task_id)

    # ── Tier 2: Large model ──
    if config.large_model:
        try:
            # Use original category config parameters for the Tier 2 execution
            t2_config = CATEGORY_CONFIG.get(normalized_cat, cat_config)
            answer = tier_two.execute(
                client=client,
                model=config.large_model,
                instruction=instruction_optimized,
                category=category,
                category_config=t2_config,
                task_id=task_id,
            )
            if answer:
                # Ensure NER JSON is normalized even from Tier 2
                if normalized_cat in ("ner", "named_entity_recognition"):
                    answer = _normalize_json_string(answer)
                return answer
        except Exception as e:
            logger.error("Tier 2 failed for task %s: %s", task_id, e)

    # ── All tiers exhausted ──
    logger.error("All tiers failed for task %s", task_id)
    return "I could not determine the answer."
