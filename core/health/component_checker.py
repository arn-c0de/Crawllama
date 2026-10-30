"""Component Health Checker - Verify all system components.

This module performs health checks on:
- LLM Client connectivity and configuration
- Cache system functionality
- RAG system and embeddings
- Search tools (web, wiki, etc.)
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from utils.async_utils import run_async


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a component."""
    name: str
    status: HealthStatus
    message: str
    response_time_ms: float
    last_checked: datetime
    details: dict | None = None


# (status, message, details) as returned by a component probe
CheckOutcome = tuple[HealthStatus, str, dict | None]


class ComponentHealthChecker:
    """Check health of all system components."""

    def __init__(self, project_root: Path):
        """Initialize health checker.
        
        Args:
            project_root: Path to project root directory
        """
        self.project_root = project_root
        self.last_results: dict[str, ComponentHealth] = {}

    async def check_all_async(self) -> dict[str, ComponentHealth]:
        """Check all components asynchronously.
        
        Returns:
            Dictionary mapping component name to health status
        """
        checks = [
            self._check_llm_client(),
            self._check_cache_system(),
            self._check_rag_system(),
            self._check_search_tools(),
            self._check_file_system(),
            self._check_config()
        ]
        
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        # Store results
        self.last_results = {}
        for result in results:
            if isinstance(result, ComponentHealth):
                self.last_results[result.name] = result
            elif isinstance(result, Exception):
                # Handle exception
                self.last_results["error"] = ComponentHealth(
                    name="Error",
                    status=HealthStatus.UNHEALTHY,
                    message=str(result),
                    response_time_ms=0.0,
                    last_checked=datetime.now()
                )
        
        return self.last_results

    def check_all(self) -> dict[str, ComponentHealth]:
        """Check all components (synchronous wrapper).
        
        Returns:
            Dictionary mapping component name to health status
        """
        return run_async(self.check_all_async())

    @staticmethod
    def _run_check(name: str, probe: Callable[[], CheckOutcome]) -> ComponentHealth:
        """Run one probe, timing it and turning any exception into UNHEALTHY.

        Args:
            name: Display name of the component
            probe: Callable returning ``(status, message, details)``
        """
        start = time.perf_counter()
        try:
            status, message, details = probe()
        except Exception as e:
            status, message, details = HealthStatus.UNHEALTHY, f"Error: {e}", None
        return ComponentHealth(
            name=name,
            status=status,
            message=message,
            response_time_ms=(time.perf_counter() - start) * 1000,
            last_checked=datetime.now(),
            details=details,
        )

    async def _check_llm_client(self) -> ComponentHealth:
        """Check LLM client health."""
        return self._run_check("LLM Client", self._probe_llm_client)

    async def _check_cache_system(self) -> ComponentHealth:
        """Check cache system health."""
        return self._run_check("Cache System", self._probe_cache_system)

    async def _check_rag_system(self) -> ComponentHealth:
        """Check RAG system health."""
        return self._run_check("RAG System", self._probe_rag_system)

    async def _check_search_tools(self) -> ComponentHealth:
        """Check search tools health."""
        return self._run_check("Search Tools", self._probe_search_tools)

    async def _check_file_system(self) -> ComponentHealth:
        """Check file system health."""
        return self._run_check("File System", self._probe_file_system)

    async def _check_config(self) -> ComponentHealth:
        """Check configuration health."""
        return self._run_check("Configuration", self._probe_config)

    def _probe_llm_client(self) -> CheckOutcome:
        from core.llm_client import OllamaClient

        config_path = self.project_root / "config.json"
        if not config_path.exists():
            return HealthStatus.UNHEALTHY, "Config file not found", None

        client = OllamaClient(str(config_path))
        if not getattr(client, 'model', None):
            return HealthStatus.DEGRADED, "Model not configured", None

        return (
            HealthStatus.HEALTHY,
            "LLM client initialized successfully",
            {'model': client.model},
        )

    def _probe_cache_system(self) -> CheckOutcome:
        from core.cache import CacheManager

        cache_dir = self.project_root / "data" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache = CacheManager(cache_dir=str(cache_dir), ttl_hours=1)

        # Round-trip a probe value
        test_key = "__health_check__"
        test_value = {"test": "data", "timestamp": time.time()}
        cache.set(test_key, test_value)
        if cache.get(test_key) != test_value:
            status, message = HealthStatus.DEGRADED, "Cache read/write mismatch"
        else:
            status, message = HealthStatus.HEALTHY, "Cache operating normally"

        cache_files = list(cache_dir.glob("*.json"))
        cache_size_mb = sum(f.stat().st_size for f in cache_files) / (1024 ** 2)
        return status, message, {
            'cache_files': len(cache_files),
            'cache_size_mb': f"{cache_size_mb:.2f}",
        }

    def _probe_rag_system(self) -> CheckOutcome:
        from tools.rag import RAGManager

        embeddings_dir = self.project_root / "data" / "embeddings"
        if not embeddings_dir.exists():
            return HealthStatus.DEGRADED, "Embeddings directory not found", None

        rag = RAGManager(persist_dir=str(embeddings_dir))

        # RAG is healthy even if no documents are indexed yet
        try:
            collection = rag.collection
            doc_count = collection.count() if hasattr(collection, 'count') else 0
            if doc_count == 0:
                message = "RAG initialized (no documents indexed)"
            else:
                message = f"RAG operational with {doc_count} documents"
        except Exception:
            doc_count = 0
            message = "RAG initialized successfully"

        return HealthStatus.HEALTHY, message, {'document_count': doc_count}

    def _probe_search_tools(self) -> CheckOutcome:
        from tools.web_search import web_search
        from tools.wiki_lookup import wiki_lookup

        if not callable(web_search):
            raise ValueError("web_search is not callable")
        if not callable(wiki_lookup):
            raise ValueError("wiki_lookup is not callable")

        return (
            HealthStatus.HEALTHY,
            "All search tools available",
            {'tools': ['web_search', 'wiki_lookup']},
        )

    def _probe_file_system(self) -> CheckOutcome:
        import psutil

        critical_dirs = ['data', 'logs', 'tools', 'core']
        missing_dirs = [d for d in critical_dirs if not (self.project_root / d).exists()]
        if missing_dirs:
            status = HealthStatus.DEGRADED
            message = f"Missing directories: {', '.join(missing_dirs)}"
        else:
            status = HealthStatus.HEALTHY
            message = "All critical directories present"

        disk_free_gb = psutil.disk_usage(str(self.project_root)).free / (1024 ** 3)
        if disk_free_gb < 1.0:
            status = HealthStatus.UNHEALTHY
            message = f"Low disk space: {disk_free_gb:.2f} GB free"
        elif disk_free_gb < 5.0:
            status = HealthStatus.DEGRADED
            message = f"Limited disk space: {disk_free_gb:.2f} GB free"

        return status, message, {'disk_free_gb': f"{disk_free_gb:.2f}"}

    def _probe_config(self) -> CheckOutcome:
        import json

        config_path = self.project_root / "config.json"
        if not config_path.exists():
            return HealthStatus.UNHEALTHY, "config.json not found", None

        with open(config_path, encoding='utf-8') as f:
            config = json.load(f)

        # Support both nested (llm.model) and flat (model) structures
        llm_config = config.get('llm', config)
        missing_keys = [key for key in ('model', 'base_url') if key not in llm_config]
        if missing_keys:
            status = HealthStatus.DEGRADED
            message = f"Missing config keys: {', '.join(missing_keys)}"
        else:
            status, message = HealthStatus.HEALTHY, "Configuration valid"

        return status, message, {'config_keys': len(config)}
