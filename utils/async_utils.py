"""Async utilities for improved performance and concurrency."""
import asyncio
import aiohttp
import logging
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
import time

logger = logging.getLogger("crawllama")


class AsyncFetcher:
    """Async HTTP fetcher for parallel requests."""

    def __init__(
        self,
        timeout: int = 30,
        max_concurrent: int = 10,
        headers: Optional[Dict[str, str]] = None,
        use_safe_fetcher: bool = True,
        max_size_mb: int = 50,
        allow_redirects: bool = False
    ):
        """
        Initialize async fetcher.

        Args:
            timeout: Request timeout in seconds
            max_concurrent: Maximum concurrent requests
            headers: Default headers for requests
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_concurrent = max_concurrent
        self.max_size_mb = max_size_mb
        self.headers = headers or {
            "User-Agent": "CrawlLama/1.0 (Educational Web Crawler)"
        }
        self.use_safe_fetcher = use_safe_fetcher
        self.allow_redirects = allow_redirects

        self._semaphore = asyncio.Semaphore(max_concurrent)
        logger.info(f"Async fetcher initialized (max_concurrent={max_concurrent})")

    def _safe_fetch_sync(self, url: str) -> Dict[str, Any]:
        """Run SafeFetcher in a thread-safe sync context."""
        from utils.safe_fetch import get_safe_fetcher

        fetcher = get_safe_fetcher()
        response = fetcher.get(
            url,
            timeout=int(self.timeout.total),
            headers=self.headers,
            max_size_mb=self.max_size_mb,
            allow_redirects=self.allow_redirects
        )

        if response is None:
            return {"url": url, "content": None, "status": None, "headers": {}, "error": "Fetch failed"}

        return {
            "url": url,
            "content": response.text,
            "status": response.status_code,
            "headers": dict(response.headers),
            "error": None
        }

    async def fetch_one(
        self,
        session: Optional[aiohttp.ClientSession],
        url: str
    ) -> Dict[str, Any]:
        """
        Fetch single URL asynchronously.

        Args:
            session: Aiohttp client session
            url: URL to fetch

        Returns:
            Dictionary with url, content, status, error
        """
        async with self._semaphore:
            try:
                logger.debug(f"Fetching: {url}")

                if self.use_safe_fetcher:
                    return await asyncio.to_thread(self._safe_fetch_sync, url)

                if session is None:
                    raise ValueError("Session is required when use_safe_fetcher is False")

                async with session.get(url, timeout=self.timeout, allow_redirects=False) as response:
                    content = await response.text()

                    return {
                        "url": url,
                        "content": content,
                        "status": response.status,
                        "headers": dict(response.headers),
                        "error": None
                    }

            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching {url}")
                return {"url": url, "content": None, "status": None, "error": "Timeout"}

            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                return {"url": url, "content": None, "status": None, "error": str(e)}

    async def fetch_many(
        self,
        urls: List[str],
        return_dict: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetch multiple URLs asynchronously.

        Args:
            urls: List of URLs to fetch
            return_dict: Return as dict keyed by URL

        Returns:
            List or dict of fetch results
        """
        logger.info(f"Async fetching {len(urls)} URLs")
        start_time = time.time()

        if self.use_safe_fetcher:
            tasks = [self.fetch_one(None, url) for url in urls]
            results = await asyncio.gather(*tasks)
        else:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                tasks = [self.fetch_one(session, url) for url in urls]
                results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time
        success_count = sum(1 for r in results if r["error"] is None)

        logger.info(f"Async fetch complete: {success_count}/{len(urls)} successful in {elapsed:.2f}s")

        if return_dict:
            return {r["url"]: r for r in results}

        return results

    def fetch_urls_sync(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Synchronous wrapper for async fetch.

        Args:
            urls: URLs to fetch

        Returns:
            List of fetch results
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.fetch_many(urls))


class AsyncSearchAggregator:
    """Aggregate search results from multiple sources asynchronously."""

    def __init__(self, max_concurrent: int = 5):
        """
        Initialize search aggregator.

        Args:
            max_concurrent: Maximum concurrent searches
        """
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def search_one(
        self,
        search_func: Callable[[str], str],
        query: str,
        source_name: str
    ) -> Dict[str, Any]:
        """
        Perform single async search.

        Args:
            search_func: Search function (will be run in executor)
            query: Search query
            source_name: Name of search source

        Returns:
            Search result dict
        """
        async with self._semaphore:
            try:
                logger.debug(f"Searching {source_name}: {query}")

                # Run blocking search function in executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    search_func,
                    query
                )

                return {
                    "source": source_name,
                    "query": query,
                    "result": result,
                    "error": None
                }

            except Exception as e:
                logger.error(f"Search error ({source_name}): {e}")
                return {
                    "source": source_name,
                    "query": query,
                    "result": None,
                    "error": str(e)
                }

    async def aggregate_searches(
        self,
        query: str,
        search_sources: Dict[str, Callable[[str], str]]
    ) -> Dict[str, Any]:
        """
        Aggregate searches from multiple sources.

        Args:
            query: Search query
            search_sources: Dict of source_name -> search_function

        Returns:
            Aggregated results
        """
        logger.info(f"Aggregating searches from {len(search_sources)} sources")

        tasks = [
            self.search_one(func, query, name)
            for name, func in search_sources.items()
        ]

        results = await asyncio.gather(*tasks)

        # Separate successful and failed results
        successful = [r for r in results if r["error"] is None]
        failed = [r for r in results if r["error"] is not None]

        return {
            "query": query,
            "successful": successful,
            "failed": failed,
            "total_sources": len(search_sources),
            "success_count": len(successful)
        }

    def aggregate_sync(
        self,
        query: str,
        search_sources: Dict[str, Callable[[str], str]]
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for aggregate searches.

        Args:
            query: Search query
            search_sources: Search sources dict

        Returns:
            Aggregated results
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.aggregate_searches(query, search_sources)
        )


class AsyncBatchProcessor:
    """Process items in async batches."""

    def __init__(self, batch_size: int = 10, max_concurrent: int = 5):
        """
        Initialize batch processor.

        Args:
            batch_size: Items per batch
            max_concurrent: Max concurrent tasks
        """
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent

    async def process_batch(
        self,
        items: List[Any],
        process_func: Callable[[Any], Any],
        show_progress: bool = True
    ) -> List[Any]:
        """
        Process items in async batches.

        Args:
            items: Items to process
            process_func: Processing function
            show_progress: Log progress

        Returns:
            List of results
        """
        total = len(items)
        logger.info(f"Processing {total} items in async batches")

        all_results = []

        for i in range(0, total, self.batch_size):
            batch = items[i:i + self.batch_size]

            # Process batch
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                tasks = [
                    loop.run_in_executor(executor, process_func, item)
                    for item in batch
                ]
                batch_results = await asyncio.gather(*tasks)

            all_results.extend(batch_results)

            if show_progress:
                logger.info(f"Progress: {min(i + self.batch_size, total)}/{total}")

        return all_results

    def process_sync(
        self,
        items: List[Any],
        process_func: Callable[[Any], Any]
    ) -> List[Any]:
        """
        Synchronous wrapper for batch processing.

        Args:
            items: Items to process
            process_func: Processing function

        Returns:
            List of results
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.process_batch(items, process_func)
        )


async def async_timeout(coro, timeout: float):
    """
    Run coroutine with timeout.

    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds

    Returns:
        Result or None on timeout
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Async operation timed out after {timeout}s")
        return None


def run_async(coro):
    """
    Helper to run async coroutine in sync context.

    Args:
        coro: Coroutine to run

    Returns:
        Coroutine result
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)
