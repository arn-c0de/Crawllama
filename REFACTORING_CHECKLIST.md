# ✅ Refactoring-Checkliste: Funktionskonsolidierung

**Ziel:** Schrittweise Umsetzung der Konsolidierungsempfehlungen aus REFACTORING_OPPORTUNITIES.md

---

## Phase 1: Kritische Konsolidierungen
- [x] 1. `utils/resource_monitor.py` zu Deprecation-Wrapper umgewandelt ✅ 2025-10-24
- [x] 2. Alle Monitoring-Nutzer auf `core/health/` umgestellt ✅ 2025-10-24
- [x] 3. Imports in `app.py` auf `core/health` aktualisiert ✅ 2025-10-24
- [x] 4. `utils/retry.py` in `utils/safe_fetch.py` integriert ✅ 2025-10-24
- [x] 5. Retry-Logik bereits in SafeFetcher eingebaut ✅ 2025-10-24
- [x] 6. `retry.py` zu Deprecation-Wrapper umgewandelt ✅ 2025-10-24

## Phase 2: Mittlere Refactorings
- [x] 7. `LazyLoader` und `PluginLoader` zu `UnifiedLoader` zusammenführen ✅ 2025-10-24
- [x] 8. `ResourceManager` Klasse in `UnifiedLoader` integriert ✅ 2025-10-24
- [x] 9. `PluginManager` auf `UnifiedLoader` umstellen ✅ 2025-10-24
- [x] 10. Factory-Funktionen (`get_*()`) in zentrale Registry migriert ✅ 2025-10-24
- [x] 11. Neue Datei `core/registry.py` erstellt ✅ 2025-10-24
- [x] 12. Imports in `app.py` auf `get_unified_loader()` aktualisiert ✅ 2025-10-24

## Phase 3: Polishing & Vereinheitlichung
- [x] 13. Validatoren in `utils/validators.py` konsolidieren ✅ 2025-10-24
- [x] 14. `is_safe_url()` aus `domain_blacklist.py` umbenannt → `is_url_not_blacklisted()` ✅ 2025-10-24
- [x] 15. Deprecation-Wrapper für alte `is_safe_url()` Funktion erstellt ✅ 2025-10-24
- [x] 16. Text-Cleaning in `TextCleaner` Klasse gebündelt ✅ 2025-10-24
- [x] 17. `context_manager.truncate()` migriert auf `TextCleaner` ✅ 2025-10-24
- [x] 18. Logger-Setup vereinfacht (`Logger.get()` Klasse erstellt) ✅ 2025-10-24
- [x] 19. Deprecation-Wrappers für `setup_logger()` und `get_logger()` ✅ 2025-10-24

## Tests & Migration
- [x] 20. Tests in `test_multihop_reasoning.py` aktualisiert ✅ 2025-10-24
- [x] 21. Deprecation-Wrappers für alte APIs in `lazy_loader.py` eingebaut ✅ 2025-10-24
- [x] 22. Dokumentation aktualisiert: `docs/UNIFIED_LOADER_MIGRATION.md` ✅ 2025-10-24
- [x] 22b. Tests in `test_tiktoken.py` für TextCleaner-Migration aktualisiert ✅ 2025-10-24
- [x] 22c. Tests in `test_multihop_reasoning.py` für core.health-Migration aktualisiert ✅ 2025-10-24
- [ ] 23. Branch `refactor/function-consolidation` erstellen
- [x] 24. UnifiedLoader-Refactoring abgeschlossen ✅ 2025-10-24
- [x] 25. ResourceMonitor-Refactoring abgeschlossen ✅ 2025-10-24
- [ ] 26. Merge nach erfolgreichem Testlauf

---

## ✅ Abgeschlossene Refactorings

### UnifiedLoader-Migration (2025-10-24)
**Dateien:**
- ✅ NEU: `core/unified_loader.py` (450 Zeilen)
- ✅ REFACTORED: `core/lazy_loader.py` (jetzt Wrapper mit Deprecations)
- ✅ UPDATED: `core/plugin_manager.py` (nutzt `get_unified_loader()`)
- ✅ UPDATED: `app.py` (alle Endpoints aktualisiert)
- ✅ DOCS: `docs/UNIFIED_LOADER_MIGRATION.md`

**Einsparungen:**
- 🎯 -15 Funktionen (~38%)
- 📉 -163 Zeilen Code (~25%)
- ✅ 100% Backwards-Compatible
- 📝 Vollständige Migrations-Dokumentation

**Details:** Siehe `docs/UNIFIED_LOADER_MIGRATION.md`

### ResourceMonitor-Migration (2025-10-24)
**Dateien:**
- ✅ MIGRATED: `app.py` (nutzt jetzt `core.health`)
- ✅ REFACTORED: `utils/resource_monitor.py` (jetzt Deprecation-Wrapper)
- ✅ UPDATED: `tests/test_multihop_reasoning.py` (Tests auf `core.health` umgestellt)

**Änderungen:**
- 🔄 `RAMMonitor` → `SystemMonitor` (from `core.health`)
- 🔄 `PerformanceMonitor` → `PerformanceTracker` (from `core.health`)
- 🔄 `ResourceManager` → `get_system_monitor()` + `get_performance_tracker()`
- 🔄 `@monitor_memory` → `@monitored` decorator
- ✅ 100% Backwards-Compatible durch Deprecation-Wrappers
- 📝 Alle Tests erfolgreich (3/3 passed)

**Migration:**
```python
# ALT
from utils.resource_monitor import get_resource_manager
resource_manager = get_resource_manager()

# NEU
from core.health import get_system_monitor, get_performance_tracker
system_monitor = get_system_monitor()
performance_tracker = get_performance_tracker()
```

---

**Hinweis:**
- Die Reihenfolge ist empfohlen, kann aber je nach Team/Modul angepasst werden.
- Bei jedem Schritt: Tests ausführen und auf Fehler prüfen!

**Letzte Aktualisierung:** 2025-10-24
