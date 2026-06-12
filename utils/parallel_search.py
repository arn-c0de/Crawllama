"""Parallel search utilities for multi-aspect information gathering."""
import logging
from typing import List, Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from utils.validators import validate_query, sanitize_for_log_injection

logger = logging.getLogger("crawllama")


class ParallelSearchManager:
    """Manager for parallel search operations across multiple aspects."""

    def __init__(self, max_workers: int = 4, timeout: int = 30):
        """
        Initialize parallel search manager.

        Args:
            max_workers: Maximum number of parallel workers
            timeout: Timeout per search task in seconds
        """
        self.max_workers = max_workers
        self.timeout = timeout
        logger.info(f"Parallel search manager initialized (workers={max_workers})")

    def parallel_search(
        self,
        base_query: str,
        aspects: List[str],
        search_func: Callable[[str], str],
        combine_strategy: str = "concatenate"
    ) -> Dict[str, Any]:
        """
        Perform parallel searches for different aspects of a query.

        Args:
            base_query: Base search query
            aspects: List of aspects to search (e.g., ["technical", "historical", "current"])
            search_func: Function to perform single search (takes query string, returns result)
            combine_strategy: How to combine results ("concatenate", "summarize")

        Returns:
            Dictionary with combined results and metadata
        """
        logger.info(f"Starting parallel search for {len(aspects)} aspects")
        start_time = time.time()

        results = {}
        errors = []

        if not validate_query(base_query):
            raise ValueError("Invalid base query")

        # Create aspect-specific queries
        aspect_queries = {
            aspect: f"{base_query} {aspect}"
            for aspect in aspects
        }

        # Execute searches in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_aspect = {
                executor.submit(self._safe_search, search_func, query, aspect): aspect
                for aspect, query in aspect_queries.items()
            }

            # Collect results as they complete
            for future in as_completed(future_to_aspect, timeout=self.timeout * len(aspects)):
                aspect = future_to_aspect[future]
                try:
                    result = future.result(timeout=self.timeout)
                    results[aspect] = result
                    logger.info(f"Completed search for aspect: {aspect}")

                except Exception as e:
                    error_msg = f"Search failed for aspect '{aspect}': {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    results[aspect] = None

        # Combine results
        combined = self._combine_results(results, combine_strategy)

        elapsed = time.time() - start_time
        logger.info(f"Parallel search completed in {elapsed:.2f}s")

        return {
            "combined_result": combined,
            "aspect_results": results,
            "errors": errors,
            "elapsed_time": elapsed,
            "aspects_completed": len([r for r in results.values() if r is not None]),
            "total_aspects": len(aspects)
        }

    def _safe_search(
        self,
        search_func: Callable[[str], str],
        query: str,
        aspect: str
    ) -> str:
        """
        Safely execute search with error handling.

        Args:
            search_func: Search function to execute
            query: Search query
            aspect: Aspect being searched

        Returns:
            Search result or error message
        """
        try:
            if not validate_query(query):
                raise ValueError("Invalid query")

            safe_query = sanitize_for_log_injection(query)
            logger.debug(f"Executing search for aspect '{aspect}': {safe_query}")
            result = search_func(query)
            return result

        except Exception as e:
            safe_err = sanitize_for_log_injection(str(e))
            logger.error(f"Search error for aspect '{aspect}': {safe_err}")
            return f"Error: {str(e)}"

    def _combine_results(
        self,
        results: Dict[str, Optional[str]],
        strategy: str
    ) -> str:
        """
        Combine results from multiple aspects.

        Args:
            results: Dictionary of aspect -> result
            strategy: Combination strategy

        Returns:
            Combined result string
        """
        # Filter out None results
        valid_results = {k: v for k, v in results.items() if v is not None}

        if not valid_results:
            return "No results found for any aspect."

        if strategy == "concatenate":
            combined = []
            for aspect, result in valid_results.items():
                combined.append(f"=== {aspect.upper()} ===\n{result}\n")
            return "\n".join(combined)

        elif strategy == "summarize":
            # For summarize, just provide structured output
            combined = ["Combined results from multiple aspects:\n"]
            for aspect, result in valid_results.items():
                # Take first 500 chars of each result
                preview = result[:500] + "..." if len(result) > 500 else result
                combined.append(f"{aspect}: {preview}\n")
            return "\n".join(combined)

        else:
            return str(valid_results)

    def multi_aspect_search(
        self,
        query: str,
        search_func: Callable[[str], str],
        aspect_templates: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Convenience method for common multi-aspect searches.

        Args:
            query: Base search query
            search_func: Search function
            aspect_templates: Custom aspect query templates

        Returns:
            Combined search results
        """
        # Default aspect templates
        default_templates = {
            "overview": "{query} overview",
            "technical": "{query} technical details",
            "current": "{query} latest news",
            "comparison": "{query} comparison alternatives"
        }

        templates = aspect_templates or default_templates

        # Generate aspect queries
        aspect_queries = {
            aspect: template.format(query=query)
            for aspect, template in templates.items()
        }

        results = {}
        errors = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_aspect = {
                executor.submit(search_func, aspect_query): aspect
                for aspect, aspect_query in aspect_queries.items()
            }

            for future in as_completed(future_to_aspect, timeout=self.timeout * len(templates)):
                aspect = future_to_aspect[future]
                try:
                    if not validate_query(aspect_queries[aspect]):
                        raise ValueError("Invalid query")
                    result = future.result(timeout=self.timeout)
                    results[aspect] = result
                except Exception as e:
                    safe_err = sanitize_for_log_injection(str(e))
                    logger.error(f"Multi-aspect search failed for '{aspect}': {safe_err}")
                    errors.append(str(e))
                    results[aspect] = None

        combined = self._combine_results(results, "concatenate")

        return {
            "combined_result": combined,
            "aspect_results": results,
            "errors": errors
        }


class BatchProcessor:
    """Process multiple items in parallel batches."""

    def __init__(self, max_workers: int = 4, batch_size: int = 10):
        """
        Initialize batch processor.

        Args:
            max_workers: Maximum parallel workers
            batch_size: Items per batch
        """
        self.max_workers = max_workers
        self.batch_size = batch_size

    def process_batch(
        self,
        items: List[Any],
        process_func: Callable[[Any], Any],
        show_progress: bool = True
    ) -> List[Any]:
        """
        Process items in parallel batches.

        Args:
            items: Items to process
            process_func: Function to process each item
            show_progress: Log progress

        Returns:
            List of processed results
        """
        total_items = len(items)
        logger.info(f"Processing {total_items} items in batches")

        results = []
        processed = 0

        # Process in batches
        for i in range(0, total_items, self.batch_size):
            batch = items[i:i + self.batch_size]

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                batch_results = list(executor.map(process_func, batch))

            results.extend(batch_results)
            processed += len(batch)

            if show_progress:
                logger.info(f"Batch progress: {processed}/{total_items} items")

        logger.info(f"Batch processing complete: {len(results)} results")
        return results


def parallel_map(
    func: Callable[[Any], Any],
    items: List[Any],
    max_workers: int = 4,
    timeout: Optional[int] = None
) -> List[Any]:
    """
    Simple parallel map operation.

    Args:
        func: Function to apply to each item
        items: Items to process
        max_workers: Maximum parallel workers
        timeout: Optional timeout per item

    Returns:
        List of results
    """
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        if timeout:
            futures = [executor.submit(func, item) for item in items]
            for future in as_completed(futures, timeout=timeout):
                try:
                    results.append(future.result(timeout=timeout))
                except Exception as e:
                    logger.error(f"Parallel map error: {e}")
                    results.append(None)
        else:
            results = list(executor.map(func, items))

    return results


def compare_entities_parallel(
    entities: List[str],
    search_func: Callable[[str], str],
    comparison_aspects: List[str]
) -> Dict[str, Any]:
    """
    Compare multiple entities across different aspects in parallel.

    Args:
        entities: List of entities to compare (e.g., ["Python", "JavaScript"])
        search_func: Search function
        comparison_aspects: Aspects to compare (e.g., ["performance", "popularity"])

    Returns:
        Structured comparison results
    """
    logger.info(f"Comparing {len(entities)} entities across {len(comparison_aspects)} aspects")

    comparison_results = {}

    # For each aspect, search all entities in parallel
    for aspect in comparison_aspects:
        aspect_queries = [f"{entity} {aspect}" for entity in entities]

        with ThreadPoolExecutor(max_workers=len(entities)) as executor:
            results = list(executor.map(search_func, aspect_queries))

        comparison_results[aspect] = {
            entity: result
            for entity, result in zip(entities, results)
        }

    return {
        "entities": entities,
        "aspects": comparison_aspects,
        "comparisons": comparison_results
    }
