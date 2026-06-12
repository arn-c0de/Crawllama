"""Breach sources and manager exports."""
from .base import BreachResult, BreachSource, SourceHealth, SourceType
from .dehashed_source import DeHashedBreachSource
from .github_source import GitHubLeakSource
from .hibp_source import HIBPBreachSource
from .intelx_source import IntelXBreachSource
from .leakcheck_source import LeakCheckBreachSource
from .local_db_source import LocalDBBreachSource
from .manager import BreachManager
from .paste_source import PasteBreachSource
from .snusbase_source import SnusbaseBreachSource


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
