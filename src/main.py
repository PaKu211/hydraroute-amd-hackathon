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

    # Batched task: multiple subtasks sharing context
    if "_subtasks" in task:
        from src.router import route_batch

        batch_results = route_batch(task, config, client)
        elapsed = time.time() - task_start
        logger.info(
            "Batch %s (%d subtasks) completed in %.2fs",
            task_id,
            len(task["_subtasks"]),
            elapsed,
        )
        # Return first subtask result for ordering; individual results expand later
        return batch_results if isinstance(batch_results, list) else [batch_results]

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
            executor.submit(process_single_task, task, config, client, i + 1, total): i
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


def _batch_same_category(
    tasks: list[dict],
    logger,
) -> list[dict]:
    """Group same-category tasks with shared instruction context into batched calls.

    Detects tasks whose instructions share a long common substring (>80 chars),
    typically indicating they reference the same source text. Batched tasks share
    the system prompt across N questions, saving input tokens.

    Each batched task is a synthetic task with _subtasks list. The router handles
    batched tasks by sending a combined prompt and parsing the JSON array response.
    """
    # Build list of (task, normalized_category, instruction_lower)
    processed = []
    for t in tasks:
        cat = str(t.get("category", "")).strip().lower()
        inst = str(t.get("instruction", "")).strip()
        processed.append((t, cat, inst))

    # Group by category first
    from collections import defaultdict

    by_cat: dict[str, list[tuple[dict, str, str]]] = defaultdict(list)
    for t, cat, inst in processed:
        by_cat[cat].append((t, cat, inst))

    result: list[dict] = []
    for cat, group in by_cat.items():
        if len(group) < 2:
            result.append(group[0][0])
            continue

        # Within same category, find pairs sharing long substrings
        batched_set = set()
        for i in range(len(group)):
            if i in batched_set:
                continue
            t_i, _, inst_i = group[i]
            best_match = None
            best_substr = ""

            for j in range(i + 1, len(group)):
                if j in batched_set:
                    continue
                t_j, _, inst_j = group[j]
                # Find longest common substring
                shared = _longest_common_substring(inst_i.lower(), inst_j.lower())
                if len(shared) > len(best_substr):
                    best_substr = shared
                    best_match = j

            if best_match is not None and len(best_substr) > 80:
                # Create batched task
                t_j, _, inst_j = group[best_match]
                batched_set.add(i)
                batched_set.add(best_match)
                from src.router import normalize_category

                norm_cat = normalize_category(cat)
                batched_task = {
                    "task_id": f"batch_{cat}_{len(result)}",
                    "category": cat,
                    "instruction": inst_i,
                    "_subtasks": [t_i, t_j],
                    "_shared_context": best_substr,
                }
                result.append(batched_task)
                logger.info(
                    "Session Dedup: batched 2 tasks [%s] sharing %d chars",
                    cat,
                    len(best_substr),
                )
            else:
                result.append(t_i)

        # Add remaining unbatched tasks
        for idx in range(len(group)):
            if idx not in batched_set and idx not in [
                i
                for i, _ in enumerate(group)
                if group[i][0]
                in [r for r in result if not isinstance(r.get("_subtasks"), list)]
            ]:
                result.append(group[idx][0])

    return result


def _longest_common_substring(a: str, b: str) -> str:
    """Find the longest common substring between two strings."""
    if not a or not b:
        return ""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    max_len = 0
    end_pos = 0
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                if dp[i][j] > max_len:
                    max_len = dp[i][j]
                    end_pos = i
            else:
                dp[i][j] = 0
    return a[end_pos - max_len : end_pos]


def model_health_check(
    config: Config,
    client: OpenAI,
) -> None:
    """Validate all models in the allowed list by sending a minimal probe request.
    Removes models that return errors (offline, wrong ID, auth issues).
    Logs warnings for each failed model and updates config.allowed_models.
    """
    logger = logging.getLogger("hydraroute")
    healthy: list[str] = []

    for model in config.allowed_models:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                temperature=0.0,
            )
            if resp.choices and resp.choices[0].message.content is not None:
                healthy.append(model)
                logger.info("Health check PASS: %s", model.split("/")[-1])
            else:
                logger.warning("Health check FAIL (empty response): %s", model)
        except Exception as e:
            logger.warning("Health check FAIL: %s — %s", model.split("/")[-1], e)

    removed = len(config.allowed_models) - len(healthy)
    if removed:
        logger.warning(
            "Removed %d unhealthy model(s). Healthy: %d",
            removed,
            len(healthy),
        )
    config.allowed_models = healthy
    config._assign_model_tiers()


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

    # ── 4. Model health check: validate each model at startup ──
    if config.allowed_models:
        logger.info(
            "Running model health check on %d model(s)...", len(config.allowed_models)
        )
        model_health_check(config, client)

    # ── 5. Load tasks ──
    tasks = load_tasks(config.input_path)
    if not tasks:
        logger.warning("No tasks loaded — writing empty results")
        save_results([], config.output_path)
        sys.exit(0)

    # ── Pre-deduplicate tasks to avoid cache stampede and save API tokens ──
    unique_tasks = []
    seen_keys = set()
    dup_map = {}  # key -> list of task_ids

    for task in tasks:
        inst = task.get("instruction", "").strip()
        cat = task.get("category", "").strip()
        key = f"{cat}:{inst}"
        if key not in seen_keys:
            seen_keys.add(key)
            unique_tasks.append(task)
            dup_map[key] = [task["task_id"]]
        else:
            dup_map[key].append(task["task_id"])

    dedup_saved = len(tasks) - len(unique_tasks)
    logger.info(
        "Loaded %d tasks. Pre-deduplicated down to %d unique tasks (%d duplicate(s) bypassed).",
        len(tasks),
        len(unique_tasks),
        dedup_saved,
    )

    # ── Session Dedup: batch compatible tasks to share system prompt ──
    batched_tasks = _batch_same_category(unique_tasks, logger)
    logger.info(
        "Processing %d task(s) (%d individual + %d batched groups)",
        len(batched_tasks),
        sum(1 for t in batched_tasks if not isinstance(t.get("_subtasks"), list)),
        sum(1 for t in batched_tasks if isinstance(t.get("_subtasks"), list)),
    )

    # ── 6. Process unique tasks with concurrency ──
    try:
        unique_results = process_tasks_concurrent(
            unique_tasks,
            config,
            client,
            max_workers=3,
            per_task_timeout=25.0,
        )
    except Exception as e:
        logger.error("Concurrent processing failed (%s), falling back to sequential", e)
        unique_results = process_tasks_sequential(unique_tasks, config, client)

    # ── Expand unique results back to original tasks ──
    # Flatten: batched tasks return lists, individual tasks return dicts
    flat_results: list[dict] = []
    for r in unique_results:
        if isinstance(r, list):
            flat_results.extend(r)
        else:
            flat_results.append(r)
    unique_results_map = {res["task_id"]: res["answer"] for res in flat_results}
    results = []
    for task in tasks:
        inst = task.get("instruction", "").strip()
        cat = task.get("category", "").strip()
        key = f"{cat}:{inst}"
        # Fetch answer from representative unique task
        rep_task_id = dup_map[key][0]
        answer = unique_results_map.get(
            rep_task_id, "I could not determine the answer."
        )
        results.append({"task_id": task["task_id"], "answer": answer})

    # ── 7. Save results ──
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
