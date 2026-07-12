"""
Tier 2 - Large model execution with exponential backoff.
Reserved for complex reasoning: code debugging, logical reasoning, code generation.
Uses the largest available model from ALLOWED_MODELS.

Features:
- Prompt caching support (no seed randomization)
- Reasoning suppression
- Conservative backoff for large model rate limits
"""

import logging
import time

from openai import OpenAI, RateLimitError, APIError

from src.token_tracker import TokenTracker

logger = logging.getLogger("hydraroute")

MAX_RETRIES = 3
BACKOFF_BASE = 2.0


def execute(
    client: OpenAI,
    model: str,
    instruction: str,
    category: str,
    category_config: dict,
    task_id: str = "",
) -> str | None:
    system_prompt = category_config.get(
        "system_prompt",
        "Reason carefully and provide a complete, accurate answer.",
    )
    max_tokens = category_config.get("max_tokens", 500)
    temperature = category_config.get("temperature", 0.1)

    logger.info(
        "Tier 2 [%s] task=%s model=%s max_tokens=%d",
        category,
        task_id,
        model.split("/")[-1],
        max_tokens,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            model_lower = model.lower()
            params: dict = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": instruction},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            # Context overflow protection: truncate instead of error
            params.setdefault("extra_body", {})["context_length_exceeded_behavior"] = (
                "truncate"
            )

            # OpenRouter-specific: verbose output suppression + reasoning exclusion
            params.setdefault("extra_body", {})["verbosity"] = "low"
            if any(m in model_lower for m in ["gemma"]):
                params["extra_body"]["reasoning"] = {"exclude": True}

            # Disable thinking for reasoning models (saves reasoning tokens)
            if any(m in model_lower for m in ["deepseek", "qwen", "r1"]):
                params.setdefault("extra_body", {})["thinking"] = {"type": "disabled"}

            response = client.chat.completions.create(**params)

            answer = response.choices[0].message.content
            if not answer or not answer.strip():
                msg = response.choices[0].message
                reasoning = getattr(msg, "reasoning_content", None)
                if not reasoning and hasattr(msg, "model_extra") and msg.model_extra:
                    reasoning = msg.model_extra.get("reasoning_content")
                if reasoning:
                    answer = reasoning.strip()
                    logger.info(
                        "Using reasoning_content as fallback for task %s", task_id
                    )

            if answer:
                answer = answer.strip()

            usage = response.usage
            if usage:
                TokenTracker().record(
                    task_id=task_id,
                    model=model,
                    prompt_tokens=usage.prompt_tokens or 0,
                    completion_tokens=usage.completion_tokens or 0,
                )

            logger.debug("Tier 2 answer[:100]: %s", (answer or "")[:100])
            return answer

        except RateLimitError as e:
            import random

            wait = (BACKOFF_BASE**attempt) + random.uniform(0.5, 1.5)
            logger.warning(
                "Tier 2 rate limit (attempt %d/%d) for task %s, waiting %.1fs: %s",
                attempt,
                MAX_RETRIES,
                task_id,
                wait,
                e,
            )
            time.sleep(wait)
        except APIError as e:
            logger.error("Tier 2 API error for task %s: %s", task_id, e)
            if attempt < MAX_RETRIES:
                import random

                wait = BACKOFF_BASE + random.uniform(0.5, 1.0)
                time.sleep(wait)
            else:
                return None
        except Exception as e:
            logger.error("Tier 2 unexpected error for task %s: %s", task_id, e)
            return None

    logger.error("Tier 2 exhausted all %d retries for task %s", MAX_RETRIES, task_id)
    return None
