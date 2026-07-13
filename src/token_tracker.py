"""
Token usage tracker for HydraRoute Agent.
Tracks prompt, completion, and total tokens per task and per model.
Uses a singleton pattern for global access.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("hydraroute")


@dataclass
class TokenUsage:
    """Token counts for a single API call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""


class TokenTracker:
    """Singleton tracker for token usage across all tasks."""

    _instance: "TokenTracker | None" = None

    def __new__(cls) -> "TokenTracker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self.total = TokenUsage()
        self.per_task: dict[str, TokenUsage] = {}
        self.per_model: dict[str, TokenUsage] = {}
        self.api_calls: int = 0
        self.tier_zero_hits: int = 0
        self.sympy_hits: int = 0

    def record(
        self,
        task_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Record token usage for a single API call."""
        total = prompt_tokens + completion_tokens
        self.api_calls += 1

        # Update totals
        self.total.prompt_tokens += prompt_tokens
        self.total.completion_tokens += completion_tokens
        self.total.total_tokens += total

        # Update per-task
        if task_id not in self.per_task:
            self.per_task[task_id] = TokenUsage()
        task_usage = self.per_task[task_id]
        task_usage.prompt_tokens += prompt_tokens
        task_usage.completion_tokens += completion_tokens
        task_usage.total_tokens += total
        # Keep the model name on the first API call attributed to this task.
        if not task_usage.model:
            task_usage.model = model

        # Update per-model
        if model not in self.per_model:
            self.per_model[model] = TokenUsage()
        model_usage = self.per_model[model]
        model_usage.prompt_tokens += prompt_tokens
        model_usage.completion_tokens += completion_tokens
        model_usage.total_tokens += total

        logger.debug(
            "Tokens for task %s [%s]: prompt=%d, completion=%d, total=%d",
            task_id,
            model,
            prompt_tokens,
            completion_tokens,
            total,
        )

    def record_tier_zero(self) -> None:
        """Record a successful Tier 0 (zero-cost) execution."""
        self.tier_zero_hits += 1

    def record_sympy(self) -> None:
        """Record a successful SymPy-LLM Symbiosis solve."""
        self.sympy_hits += 1

    def print_summary(self) -> None:
        """Print a summary of token usage."""
        print("\n" + "=" * 60)
        print("TOKEN USAGE SUMMARY")
        print("=" * 60)
        print(f"  Total API calls:      {self.api_calls}")
        print(f"  Tier 0 (free) hits:   {self.tier_zero_hits}")
        print(f"  SymPy-LLM Solves:     {self.sympy_hits}")
        print(f"  Prompt tokens:        {self.total.prompt_tokens:,}")
        print(f"  Completion tokens:    {self.total.completion_tokens:,}")
        print(f"  Total tokens:         {self.total.total_tokens:,}")

        if self.per_model:
            print("\n  Per-model breakdown:")
            for model, usage in sorted(self.per_model.items()):
                name = model.split("/")[-1] if "/" in model else model
                print(f"    {name}:")
                print(
                    f"      prompt={usage.prompt_tokens:,}  "
                    f"completion={usage.completion_tokens:,}  "
                    f"total={usage.total_tokens:,}"
                )

        total_tasks = len(self.per_task) + self.tier_zero_hits
        if total_tasks > 0:
            avg = self.total.total_tokens / max(len(self.per_task), 1)
            print(f"\n  Avg tokens per API task: {avg:.1f}")

        print("=" * 60 + "\n")

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for testing)."""
        cls._instance = None
