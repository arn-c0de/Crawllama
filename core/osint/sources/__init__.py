"""Breach sources and manager exports."""
from .base import BreachSource, BreachResult, SourceType, SourceHealth
from .manager import BreachManager
from .hibp_source import HIBPBreachSource
from .leakcheck_source import LeakCheckBreachSource
from .intelx_source import IntelXBreachSource
from .dehashed_source import DeHashedBreachSource
from .snusbase_source import SnusbaseBreachSource
from .local_db_source import LocalDBBreachSource
from .github_source import GitHubLeakSource
from .paste_source import PasteBreachSource


def create_default_manager(config=None) -> BreachManager:
    manager = BreachManager(config=config)
    manager.register_source(HIBPBreachSource(config))
    manager.register_source(LeakCheckBreachSource(config))
    manager.register_source(IntelXBreachSource(config))
    manager.register_source(DeHashedBreachSource(config))
    manager.register_source(SnusbaseBreachSource(config))
    manager.register_source(LocalDBBreachSource(config))
    manager.register_source(GitHubLeakSource(config))
    manager.register_source(PasteBreachSource(config))
    return manager


__all__ = [
    "BreachSource",
    "BreachResult",
    "SourceType",
    "SourceHealth",
    "BreachManager",
    "create_default_manager",
    "HIBPBreachSource",
    "LeakCheckBreachSource",
    "IntelXBreachSource",
    "DeHashedBreachSource",
    "SnusbaseBreachSource",
    "LocalDBBreachSource",
    "GitHubLeakSource",
    "PasteBreachSource"
]
