"""
Hybrid Cache for HydraRoute Agent (v3 - Dynamic Semantic/Fuzzy Caching).
Avoids redundant API calls for exact and semantically similar instructions.
Uses category-aware TF-IDF/Bag-of-Words Cosine Similarity.
Thread-safe for concurrent task processing.
"""

import hashlib
import logging
import math
import re
import threading
from collections import Counter
from typing import Optional, Any

logger = logging.getLogger("hydraroute.cache")

# Common stop words to exclude from similarity comparison to improve semantic precision
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "and", "or", "to", "in",
    "for", "on", "at", "by", "with", "please", "what", "how", "why", "who",
    "where", "which", "does", "do", "did", "this", "that", "these", "those"
}

# Similarity threshold (e.g. 0.88 means 88% word frequency alignment)
SIMILARITY_THRESHOLD = 0.88


class InMemoryCache:
    """Thread-safe Hybrid Cache supporting exact SHA1 matches and fuzzy Cosine Similarity."""

    _instance: Optional["InMemoryCache"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "InMemoryCache":
        """Singleton pattern - one cache shared across all threads."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._exact_cache: dict[str, str] = {}
                    instance._fuzzy_cache: list[dict[str, Any]] = []
                    instance._cache_lock = threading.Lock()
                    instance._exact_hits = 0
                    instance._fuzzy_hits = 0
                    instance._misses = 0
                    cls._instance = instance
        return cls._instance

    def _make_key(self, instruction: str, category: str) -> str:
        """Generate a SHA1 hash key from the category and instruction text."""
        combined = f"{category}:{instruction.strip()}"
        return hashlib.sha1(combined.encode("utf-8")).hexdigest()

    def _tokenize(self, text: str) -> Counter:
        """Clean, lower-case, remove stop words, and tokenize instruction text."""
        # Lowercase and keep alphanumeric + spaces
        cleaned = re.sub(r"[^\w\s]", "", text.lower())
        words = cleaned.split()
        # Filter stop words and single characters (unless they are digits/variables)
        filtered_words = [
            w for w in words
            if w not in STOP_WORDS and (len(w) > 1 or w.isdigit() or w in ("x", "y", "z"))
        ]
        return Counter(filtered_words)

    def _cosine_similarity(self, vec1: Counter, vec2: Counter) -> float:
        """Calculate Cosine Similarity between two word frequency vectors."""
        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum(vec1[x] * vec2[x] for x in intersection)

        sum1 = sum(val ** 2 for val in vec1.values())
        sum2 = sum(val ** 2 for val in vec2.values())
        denominator = math.sqrt(sum1) * math.sqrt(sum2)

        if not denominator:
            return 0.0
        return float(numerator) / denominator

    def get(self, instruction: str, category: str = "default") -> Optional[str]:
        """Look up a cached answer for the given instruction.

        Tries exact SHA1 lookup first, then falls back to Cosine Similarity.

        Args:
            instruction: The task instruction text.
            category: The task category (to prevent cross-category mismatch).

        Returns:
            Cached answer string, or None if not found.
        """
        # 1. Exact Match Check (SHA1)
        exact_key = self._make_key(instruction, category)
        with self._cache_lock:
            cached_answer = self._exact_cache.get(exact_key)
            if cached_answer is not None:
                self._exact_hits += 1
                logger.info("Exact Cache HIT (key=%s...)", exact_key[:8])
                return cached_answer

        # 2. Fuzzy Semantic Check (Cosine Similarity on Bag-of-Words)
        input_tokens = self._tokenize(instruction)
        if not input_tokens:
            with self._cache_lock:
                self._misses += 1
            return None

        with self._cache_lock:
            best_similarity = 0.0
            best_answer: Optional[str] = None
            best_matched_text: str = ""

            # Scan cache items belonging to the SAME category to prevent mismatches
            for item in self._fuzzy_cache:
                if item["category"] != category:
                    continue

                sim = self._cosine_similarity(input_tokens, item["tokens"])
                if sim > best_similarity:
                    best_similarity = sim
                    best_answer = item["answer"]
                    best_matched_text = item["raw"]

            if best_similarity >= SIMILARITY_THRESHOLD and best_answer is not None:
                self._fuzzy_hits += 1
                logger.info(
                    "Fuzzy Cache HIT (Similarity: %.2f) for category [%s]. Matched: '%s...'",
                    best_similarity, category, best_matched_text[:40]
                )
                return best_answer

            self._misses += 1
            return None

    def set(self, instruction: str, answer: str, category: str = "default") -> None:
        """Store an answer in the cache for future exact/fuzzy matches.

        Args:
            instruction: The task instruction text.
            answer: The generated answer.
            category: The task category.
        """
        if not answer or not instruction:
            return

        exact_key = self._make_key(instruction, category)
        tokens = self._tokenize(instruction)

        with self._cache_lock:
            # Save to exact lookup
            self._exact_cache[exact_key] = answer
            # Save to fuzzy lookup
            self._fuzzy_cache.append({
                "category": category,
                "tokens": tokens,
                "answer": answer,
                "raw": instruction
            })
        logger.debug("Cache SET (key=%s..., category=%s)", exact_key[:8], category)

    def stats(self) -> dict:
        """Return cache statistics including hits breakdown."""
        with self._cache_lock:
            total_hits = self._exact_hits + self._fuzzy_hits
            total_requests = total_hits + self._misses
            hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
            return {
                "size": len(self._exact_cache),
                "exact_hits": self._exact_hits,
                "fuzzy_hits": self._fuzzy_hits,
                "misses": self._misses,
                "hit_rate_pct": round(hit_rate, 1),
            }

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._cache_lock:
            self._exact_cache.clear()
            self._fuzzy_cache.clear()
            self._exact_hits = 0
            self._fuzzy_hits = 0
            self._misses = 0
