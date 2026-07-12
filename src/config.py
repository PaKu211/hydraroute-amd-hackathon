"""
Configuration module for HydraRoute Agent.
Reads environment variables and configures the routing system.
"""

import os
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("hydraroute")


@dataclass
class Config:
    """Runtime configuration loaded from environment variables."""

    fireworks_api_key: str = ""
    fireworks_base_url: str = "https://api.fireworks.ai/inference/v1"
    allowed_models: list[str] = field(default_factory=list)
    input_path: str = "/input/tasks.json"
    output_path: str = "/output/results.json"

    # Model tier assignments (populated at runtime from ALLOWED_MODELS)
    smallest_model: str = ""
    small_model: str = ""
    large_model: str = ""

    # Known model size rankings (smallest to largest)
    MODEL_SIZE_ORDER: dict[str, int] = field(
        default_factory=lambda: {
            "llama-v3p2-1b-instruct": 1,
            "llama-v3p2-3b-instruct": 3,
            "mistral-7b-instruct": 7,
            "llama-v3-8b-instruct": 8,
            "llama-v3p1-8b-instruct": 8,
            "gemma-4-26b-a4b-it": 10,  # MoE, ~4B active params = efficient
            "deepseek-v4-flash": 20,
            "gemma-4-31b-it": 31,
            "llama-v3p1-70b-instruct": 70,
            "llama-v3p3-70b-instruct": 70,
            "qwen2p5-72b-instruct": 72,
            "deepseek-v3": 671,
            "deepseek-r1": 671,
            "qwen3-235b-a22b": 235,
            "deepseek-v4-pro": 700,
        }
    )

    @property
    def is_gemma(self) -> bool:
        """Check if currently active models are Gemma-family."""
        return any("gemma" in m.lower() for m in self.allowed_models)

    def __post_init__(self):
        self._load_from_env()

    def _load_from_env(self):
        """Load configuration from environment variables."""
        self.fireworks_api_key = os.environ.get("FIREWORKS_API_KEY", "")
        self.fireworks_base_url = os.environ.get(
            "FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"
        )

        # Parse ALLOWED_MODELS - comma-separated list
        models_str = os.environ.get("ALLOWED_MODELS", "")
        if models_str:
            self.allowed_models = [
                m.strip() for m in models_str.split(",") if m.strip()
            ]
        else:
            self.allowed_models = []

        # Detect and set adaptive paths
        self.input_path = os.environ.get("INPUT_PATH", "/input/tasks.json")
        if not os.path.exists(os.path.dirname(self.input_path)) or not os.access(
            os.path.dirname(self.input_path), os.R_OK
        ):
            self.input_path = "./input/tasks.json"

        self.output_path = os.environ.get("OUTPUT_PATH", "/output/results.json")
        out_dir = os.path.dirname(self.output_path)
        try:
            if not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            # Test writability of output directory
            test_file = os.path.join(out_dir, ".write_test")
            with open(test_file, "w") as f:
                f.write("")
            os.remove(test_file)
        except (OSError, IOError):
            self.output_path = "./output/results.json"
            os.makedirs("./output", exist_ok=True)

        # Auto-assign models based on size (3 tiers)
        self._assign_model_tiers()

        logger.info(
            "Config loaded: %d models available, smallest=%s, small=%s, large=%s",
            len(self.allowed_models),
            self.smallest_model,
            self.small_model,
            self.large_model,
        )

    def _get_model_size(self, model_id: str) -> int:
        """Get estimated model size in billions of parameters."""
        # Extract the model name from full ID
        # e.g., "accounts/fireworks/models/llama-v3p1-8b-instruct" -> "llama-v3p1-8b-instruct"
        name = model_id.split("/")[-1] if "/" in model_id else model_id

        # Check known sizes
        for key, size in self.MODEL_SIZE_ORDER.items():
            if key in name:
                return size

        # Try to extract size from name (e.g., "70b", "8b")
        import re

        match = re.search(r"(\d+)b", name.lower())
        if match:
            return int(match.group(1))

        # Default: treat as medium
        return 50

    def _assign_model_tiers(self):
        """Assign models to 3 tiers based on their size:
        - smallest: for sentiment, NER (cheapest)
        - small: for factual, summarization, math (medium)
        - large: for code, reasoning (largest)
        """
        if not self.allowed_models:
            return

        sorted_models = sorted(
            self.allowed_models, key=lambda m: self._get_model_size(m)
        )

        self.smallest_model = sorted_models[0]

        # Pick median for small, last for large
        mid = len(sorted_models) // 2
        if len(sorted_models) >= 3:
            self.small_model = sorted_models[mid]
        else:
            self.small_model = sorted_models[0]
        self.large_model = sorted_models[-1]

        logger.info(
            "Model tiers: smallest=%s (size=%d), small=%s (size=%d), large=%s (size=%d)",
            self.smallest_model,
            self._get_model_size(self.smallest_model),
            self.small_model,
            self._get_model_size(self.small_model),
            self.large_model,
            self._get_model_size(self.large_model),
        )

    def get_model_for_category(self, category: str) -> str:
        """Select the optimal model for a given category using per-category preferences."""
        from src.config import CATEGORY_MODEL_PREFERENCE

        pref = CATEGORY_MODEL_PREFERENCE.get(category, "small")
        if pref == "smallest":
            return self.smallest_model or self.small_model or self.large_model
        elif pref == "large":
            return self.large_model or self.small_model
        else:
            return self.small_model or self.large_model


# Cache-optimized common prefix (for Fireworks prompt caching 50% discount)
# The common prefix structure ensures cache hits across same-category tasks.
# Fireworks caches from the first token to the first newline after the last user message.
# By keeping system prompts short + structured, we maximize reuse.
CACHE_PREFIX = "HydraRoute"

# Per-category model preferences (for optimal cost-quality tradeoff)
# Based on analysis of pricing + capability across Fireworks models
CATEGORY_MODEL_PREFERENCE = {
    "sentiment_classification": "smallest",  # Tiny models handle this fine
    "ner": "smallest",  # JSON extraction, no reasoning needed
    "factual_knowledge": "small",  # 3B-8B models know common facts
    "text_summarization": "small",  # 8B is sufficient for summarization
    "math": "small",  # With Tier 0, math rarely hits API
    "mathematical_reasoning": "small",
    "code_generation": "large",  # Code quality scales with model size
    "code_debugging": "large",  # Debugging benefits from larger models
    "logical_reasoning": "large",  # Reasoning chain requires capacity
    "deductive_reasoning": "large",
}

# Category-specific configurations
# System prompts are structured with COMMON PREFIX for Fireworks prompt caching
# The common prefix (first ~30 chars) will be cached across ALL tasks in the same category
CATEGORY_CONFIG = {
    "factual_knowledge": {
        "tier": 1,
        "system_prompt": f"{CACHE_PREFIX} | factual | Answer concisely. No explanations.",
        "max_tokens": 200,
        "temperature": 0.1,
    },
    "math": {
        "tier": 0,  # Zero-cost: Python execution
        "system_prompt": f"{CACHE_PREFIX} | math | Solve and output only the final answer.",
        "max_tokens": 150,
        "temperature": 0.0,
    },
    "mathematical_reasoning": {
        "tier": 0,
        "system_prompt": f"{CACHE_PREFIX} | math | Solve and output only the final answer.",
        "max_tokens": 150,
        "temperature": 0.0,
    },
    "sentiment_classification": {
        "tier": 1,
        "system_prompt": f"{CACHE_PREFIX} | sentiment | Classify: POS, NEG, or NEU.",
        "max_tokens": 4,  # Just POS/NEG/NEU + buffer = maximum savings
        "temperature": 0.0,
    },
    "text_summarization": {
        "tier": 1,
        "system_prompt": f"{CACHE_PREFIX} | summarize | Summarize this text concisely.",
        "max_tokens": 300,
        "temperature": 0.3,
    },
    "ner": {
        "tier": 1,
        "system_prompt": f"{CACHE_PREFIX} | ner | Extract named entities as JSON.",
        "max_tokens": 150,
        "temperature": 0.0,
    },
    "named_entity_recognition": {
        "tier": 1,
        "system_prompt": f"{CACHE_PREFIX} | ner | Extract named entities as JSON.",
        "max_tokens": 150,
        "temperature": 0.0,
    },
    "code_debugging": {
        "tier": 2,
        "system_prompt": f"{CACHE_PREFIX} | debug | Fix this code. Output only the corrected code.",
        "max_tokens": 500,
        "temperature": 0.1,
    },
    "logical_reasoning": {
        "tier": 2,
        "system_prompt": f"{CACHE_PREFIX} | reason | Solve step-by-step, ending with the final conclusion.",
        "max_tokens": 500,
        "temperature": 0.1,
    },
    "deductive_reasoning": {
        "tier": 2,
        "system_prompt": f"{CACHE_PREFIX} | reason | Solve step-by-step, ending with the final conclusion.",
        "max_tokens": 500,
        "temperature": 0.1,
    },
    "code_generation": {
        "tier": 2,
        "system_prompt": f"{CACHE_PREFIX} | code | Write code to solve this. No explanations.",
        "max_tokens": 500,
        "temperature": 0.1,
    },
}

# Default config for unknown categories
DEFAULT_CATEGORY_CONFIG = {
    "tier": 1,
    "system_prompt": f"{CACHE_PREFIX} | answer | Answer concisely and accurately.",
    "max_tokens": 300,
    "temperature": 0.2,
    "fallback_tier": 2,
}
