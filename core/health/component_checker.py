"""Component Health Checker - Verify all system components.

This module performs health checks on:
- LLM Client connectivity and configuration
- Cache system functionality
- RAG system and embeddings
- Search tools (web, wiki, etc.)
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio
from pathlib import Path


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
    details: Optional[Dict] = None


class ComponentHealthChecker:
    """Check health of all system components."""

    def __init__(self, project_root: Path):
        """Initialize health checker.
        
        Args:
            project_root: Path to project root directory
        """
        self.project_root = project_root
        self.last_results: Dict[str, ComponentHealth] = {}

    async def check_all_async(self) -> Dict[str, ComponentHealth]:
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

    def check_all(self) -> Dict[str, ComponentHealth]:
        """Check all components (synchronous wrapper).
        
        Returns:
            Dictionary mapping component name to health status
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.check_all_async())

    async def _check_llm_client(self) -> ComponentHealth:
        """Check LLM client health."""
        start = time.time()
        
        try:
            # Import and check LLM client
            from core.llm_client import LLMClient
            
            config_path = self.project_root / "config.json"
            if not config_path.exists():
                return ComponentHealth(
                    name="LLM Client",
                    status=HealthStatus.UNHEALTHY,
                    message="Config file not found",
                    response_time_ms=(time.time() - start) * 1000,
                    last_checked=datetime.now()
                )
            
            # Try to initialize client
            client = LLMClient(str(config_path))
            
            # Check if model is configured
            if not hasattr(client, 'model') or not client.model:
                return ComponentHealth(
                    name="LLM Client",
                    status=HealthStatus.DEGRADED,
                    message="Model not configured",
                    response_time_ms=(time.time() - start) * 1000,
                    last_checked=datetime.now()
                )
            
            response_time = (time.time() - start) * 1000
            
            return ComponentHealth(
                name="LLM Client",
                status=HealthStatus.HEALTHY,
                message="LLM client initialized successfully",
                response_time_ms=response_time,
                last_checked=datetime.now(),
                details={'model': getattr(client, 'model', 'unknown')}
            )
            
        except Exception as e:
            return ComponentHealth(
                name="LLM Client",
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {str(e)}",
                response_time_ms=(time.time() - start) * 1000,
                last_checked=datetime.now()
            )

    async def _check_cache_system(self) -> ComponentHealth:
        """Check cache system health."""
        start = time.time()
        
        try:
            from core.cache import SmartCache
            
            cache_dir = self.project_root / "data" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Try to initialize cache
            cache = SmartCache(cache_dir=str(cache_dir), ttl=3600)
            
            # Test basic operations
            test_key = "__health_check__"
            test_value = {"test": "data", "timestamp": time.time()}
            
            cache.set(test_key, test_value)
            retrieved = cache.get(test_key)
            
            if retrieved != test_value:
                status = HealthStatus.DEGRADED
                message = "Cache read/write mismatch"
            else:
                status = HealthStatus.HEALTHY
                message = "Cache operating normally"
            
            # Get cache stats
            cache_files = list(cache_dir.glob("*.json"))
            cache_size_mb = sum(f.stat().st_size for f in cache_files) / (1024 ** 2)
            
            response_time = (time.time() - start) * 1000
            
            return ComponentHealth(
                name="Cache System",
                status=status,
                message=message,
                response_time_ms=response_time,
                last_checked=datetime.now(),
                details={
                    'cache_files': len(cache_files),
                    'cache_size_mb': f"{cache_size_mb:.2f}"
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="Cache System",
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {str(e)}",
                response_time_ms=(time.time() - start) * 1000,
                last_checked=datetime.now()
            )

    async def _check_rag_system(self) -> ComponentHealth:
        """Check RAG system health."""
        start = time.time()
        
        try:
            from tools.rag import RAG
            
            embeddings_dir = self.project_root / "data" / "embeddings"
            
            if not embeddings_dir.exists():
                return ComponentHealth(
                    name="RAG System",
                    status=HealthStatus.DEGRADED,
                    message="Embeddings directory not found",
                    response_time_ms=(time.time() - start) * 1000,
                    last_checked=datetime.now()
                )
            
            # Try to initialize RAG
            rag = RAG(persist_dir=str(embeddings_dir))
            
            # Check if collection exists and has documents
            try:
                collection = rag.collection
                doc_count = collection.count() if hasattr(collection, 'count') else 0
                
                if doc_count == 0:
                    status = HealthStatus.DEGRADED
                    message = "RAG initialized but no documents indexed"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"RAG operational with {doc_count} documents"
            except:
                doc_count = 0
                status = HealthStatus.HEALTHY
                message = "RAG initialized successfully"
            
            response_time = (time.time() - start) * 1000
            
            return ComponentHealth(
                name="RAG System",
                status=status,
                message=message,
                response_time_ms=response_time,
                last_checked=datetime.now(),
                details={'document_count': doc_count}
            )
            
        except Exception as e:
            return ComponentHealth(
                name="RAG System",
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {str(e)}",
                response_time_ms=(time.time() - start) * 1000,
                last_checked=datetime.now()
            )

    async def _check_search_tools(self) -> ComponentHealth:
        """Check search tools health."""
        start = time.time()
        
        try:
            from tools.web_search import web_search
            from tools.wiki_lookup import wiki_lookup
            
            # Check if tools are importable and callable
            if not callable(web_search):
                raise ValueError("web_search is not callable")
            if not callable(wiki_lookup):
                raise ValueError("wiki_lookup is not callable")
            
            response_time = (time.time() - start) * 1000
            
            return ComponentHealth(
                name="Search Tools",
                status=HealthStatus.HEALTHY,
                message="All search tools available",
                response_time_ms=response_time,
                last_checked=datetime.now(),
                details={'tools': ['web_search', 'wiki_lookup']}
            )
            
        except Exception as e:
            return ComponentHealth(
                name="Search Tools",
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {str(e)}",
                response_time_ms=(time.time() - start) * 1000,
                last_checked=datetime.now()
            )

    async def _check_file_system(self) -> ComponentHealth:
        """Check file system health."""
        start = time.time()
        
        try:
            # Check critical directories
            critical_dirs = ['data', 'logs', 'tools', 'core']
            missing_dirs = []
            
            for dir_name in critical_dirs:
                dir_path = self.project_root / dir_name
                if not dir_path.exists():
                    missing_dirs.append(dir_name)
            
            if missing_dirs:
                status = HealthStatus.DEGRADED
                message = f"Missing directories: {', '.join(missing_dirs)}"
            else:
                status = HealthStatus.HEALTHY
                message = "All critical directories present"
            
            # Check disk space
            import psutil
            disk = psutil.disk_usage(str(self.project_root))
            disk_free_gb = disk.free / (1024 ** 3)
            
            if disk_free_gb < 1.0:
                status = HealthStatus.UNHEALTHY
                message = f"Low disk space: {disk_free_gb:.2f} GB free"
            elif disk_free_gb < 5.0:
                status = HealthStatus.DEGRADED
                message = f"Limited disk space: {disk_free_gb:.2f} GB free"
            
            response_time = (time.time() - start) * 1000
            
            return ComponentHealth(
                name="File System",
                status=status,
                message=message,
                response_time_ms=response_time,
                last_checked=datetime.now(),
                details={'disk_free_gb': f"{disk_free_gb:.2f}"}
            )
            
        except Exception as e:
            return ComponentHealth(
                name="File System",
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {str(e)}",
                response_time_ms=(time.time() - start) * 1000,
                last_checked=datetime.now()
            )

    async def _check_config(self) -> ComponentHealth:
        """Check configuration health."""
        start = time.time()
        
        try:
            import json
            
            config_path = self.project_root / "config.json"
            
            if not config_path.exists():
                return ComponentHealth(
                    name="Configuration",
                    status=HealthStatus.UNHEALTHY,
                    message="config.json not found",
                    response_time_ms=(time.time() - start) * 1000,
                    last_checked=datetime.now()
                )
            
            # Try to load config
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Check for required keys
            required_keys = ['model', 'base_url']
            missing_keys = [key for key in required_keys if key not in config]
            
            if missing_keys:
                status = HealthStatus.DEGRADED
                message = f"Missing config keys: {', '.join(missing_keys)}"
            else:
                status = HealthStatus.HEALTHY
                message = "Configuration valid"
            
            response_time = (time.time() - start) * 1000
            
            return ComponentHealth(
                name="Configuration",
                status=status,
                message=message,
                response_time_ms=response_time,
                last_checked=datetime.now(),
                details={'config_keys': len(config)}
            )
            
        except Exception as e:
            return ComponentHealth(
                name="Configuration",
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {str(e)}",
                response_time_ms=(time.time() - start) * 1000,
                last_checked=datetime.now()
            )
