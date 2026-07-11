"""
HydraRoute Agent - Main entry point.
Token-efficient multi-tier routing agent for AMD Developer Hackathon ACT II.

Upgrades v2:
- Concurrent task processing (ThreadPoolExecutor, 4 workers)
- SHA1 in-memory cache
- Per-task 25s timeout
- Better error recovery
"""

import concurrent.futures
import logging
import sys
import time
from threading import Lock

from openai import OpenAI

from src.cache import InMemoryCache
from src.config import Config
from src.task_loader import load_tasks, ensure_output_dir
from src.token_tracker import TokenTracker
from src.router import route_task
from src.result_formatter import save_results

results_lock = Lock()


def setup_logging() -> None:
    """Configure logging for the agent."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def create_client(config: Config) -> OpenAI:
    """Create an OpenAI-compatible client for Fireworks AI."""
    return OpenAI(
        api_key=config.fireworks_api_key,
        base_url=config.fireworks_base_url,
    )


def process_single_task(
    task: dict,
    config: Config,
    client: OpenAI,
    index: int,
    total: int,
) -> dict:
    """Process one task and return the result dict.

    Args:
        task: Task dict with task_id, category, instruction.
        config: Runtime configuration.
        client: Fireworks AI client.
        index: Task index (1-based) for logging.
        total: Total number of tasks.

    Returns:
        Dict with task_id and answer.
    """
    logger = logging.getLogger("hydraroute")
    task_id = task.get("task_id", f"task_{index}")
    category = task.get("category", "unknown")

    logger.info("── Task %d/%d: %s [%s] ──", index, total, task_id, category)
    task_start = time.time()

    try:
        # Check cache first (zero tokens!)
        cache = InMemoryCache()
        instruction = task.get("instruction", "")
        cached = cache.get(instruction, category)
        if cached is not None:
            elapsed = time.time() - task_start
            logger.info("Task %s: CACHE HIT in %.2fs", task_id, elapsed)
            return {"task_id": task_id, "answer": cached}

        # Route task through tiers
        answer = route_task(task, config, client)

        # Store in cache for potential duplicates
        if answer:
            cache.set(instruction, answer, category)

        elapsed = time.time() - task_start
        logger.info("Task %s completed in %.2fs", task_id, elapsed)
        return {"task_id": task_id, "answer": answer}

    except Exception as e:
        logger.error("Unhandled error on task %s: %s", task_id, e)
        return {"task_id": task_id, "answer": "I could not determine the answer."}


def process_tasks_concurrent(
    tasks: list[dict],
    config: Config,
    client: OpenAI,
    max_workers: int = 3,
    per_task_timeout: float = 25.0,
) -> list[dict]:
    """Process tasks concurrently with per-task timeouts.

    Args:
        tasks: List of task dicts.
        config: Runtime configuration.
        client: Fireworks AI client.
        max_workers: Max concurrent threads (keep low to avoid rate limits).
        per_task_timeout: Per-task timeout in seconds.

    Returns:
        List of result dicts in original task order.
    """
    logger = logging.getLogger("hydraroute")
    total = len(tasks)
    results: dict[int, dict] = {}  # index -> result

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_idx = {
            executor.submit(
                process_single_task, task, config, client, i + 1, total
            ): i
            for i, task in enumerate(tasks)
        }

        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            task_id = tasks[idx].get("task_id", f"task_{idx}")
            try:
                result = future.result(timeout=per_task_timeout)
                results[idx] = result
            except concurrent.futures.TimeoutError:
                logger.error("Task %s timed out after %.0fs", task_id, per_task_timeout)
                results[idx] = {
                    "task_id": task_id,
                    "answer": "Task timed out.",
                }
            except Exception as e:
                logger.error("Task %s failed: %s", task_id, e)
                results[idx] = {
                    "task_id": task_id,
                    "answer": "I could not determine the answer.",
                }

    # Return in original order
    return [results[i] for i in range(total)]


def process_tasks_sequential(
    tasks: list[dict],
    config: Config,
    client: OpenAI,
) -> list[dict]:
    """Fallback: process tasks one by one (safe, no concurrency)."""
    total = len(tasks)
    return [
        process_single_task(task, config, client, i + 1, total)
        for i, task in enumerate(tasks)
    ]


def main() -> None:
    """Run the HydraRoute agent pipeline."""
    setup_logging()
    logger = logging.getLogger("hydraroute")

    logger.info("=" * 60)
    logger.info("HydraRoute Agent v2 starting")
    logger.info("=" * 60)

    start_time = time.time()

    # ── 1. Load configuration ──
    try:
        config = Config()
    except Exception as e:
        logger.error("Config error: %s, using defaults", e)
        config = Config.__new__(Config)
        config.fireworks_api_key = ""
        config.fireworks_base_url = "https://api.fireworks.ai/inference/v1"
        config.allowed_models = []
        config.small_model = ""
        config.large_model = ""
        config.input_path = "/input/tasks.json"
        config.output_path = "/output/results.json"

    logger.info("Small model  : %s", config.small_model or "(none)")
    logger.info("Large model  : %s", config.large_model or "(none)")
    logger.info("All models   : %d available", len(config.allowed_models))

    # ── 2. Ensure output directory ──
    ensure_output_dir(config.output_path)

    # ── 3. Create API client ──
    client = create_client(config)

    # ── 4. Load tasks ──
    tasks = load_tasks(config.input_path)
    if not tasks:
        logger.warning("No tasks loaded — writing empty results")
        save_results([], config.output_path)
        sys.exit(0)

    logger.info("Processing %d tasks (concurrent, max 3 workers)", len(tasks))

    # ── 5. Process tasks with concurrency ──
    try:
        results = process_tasks_concurrent(
            tasks, config, client,
            max_workers=3,
            per_task_timeout=25.0,
        )
    except Exception as e:
        logger.error("Concurrent processing failed (%s), falling back to sequential", e)
        results = process_tasks_sequential(tasks, config, client)

    # ── 6. Save results ──
    save_results(results, config.output_path)

    # ── 7. Print summaries ──
    total_elapsed = time.time() - start_time
    TokenTracker().print_summary()

    cache_stats = InMemoryCache().stats()
    exact_hits = cache_stats.get("exact_hits", 0)
    fuzzy_hits = cache_stats.get("fuzzy_hits", 0)
    total_hits = exact_hits + fuzzy_hits
    logger.info(
        "Cache stats: %d entries, %d total hits (exact=%d, fuzzy=%d), %d misses (%.1f%% hit rate)",
        cache_stats["size"],
        total_hits,
        exact_hits,
        fuzzy_hits,
        cache_stats["misses"],
        cache_stats["hit_rate_pct"],
    )

    logger.info("Total time   : %.2fs", total_elapsed)
    logger.info("Results      : %s", config.output_path)
    logger.info("HydraRoute v2 finished successfully ✓")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.getLogger("hydraroute").critical("Fatal error: %s", e)
        try:
            save_results([], "/output/results.json")
        except Exception:
            pass
    sys.exit(0)
