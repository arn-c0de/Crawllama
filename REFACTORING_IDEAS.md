# CrawlLama – Refactoring-Ideen

> Ergebnis einer codebasisweiten Analyse (≈52k Zeilen Python) durch 6 parallele
> Subagents, aufgeteilt nach Bereichen: Entry-Points, Agent-Core, OSINT, Tools,
> Utils, Core-Services. Erstellt am 2026-07-23.
>
> Format je Idee: **Ort** · **Problem** · **Vorschlag** · **Aufwand** (S/M/L) · **Impact** (low/med/high).
> Es wurde **kein Code geändert** – dies ist reine Analyse.

## Inhalt

- [Top-Prioritäten (Kurzfassung)](#top-prioritäten-kurzfassung)
- [Übergreifende Muster](#übergreifende-muster-cross-cutting) – über mehrere Bereiche hinweg
- [1. Entry-Points (`app.py`, `main.py`)](#1-entry-points)
- [2. Agent-Core](#2-agent-core)
- [3. OSINT-Subsystem](#3-osint-subsystem)
- [4. Tools](#4-tools)
- [5. Utils](#5-utils)
- [6. Core-Services](#6-core-services)

---

## Top-Prioritäten (Kurzfassung)

Die Kandidaten mit dem besten Impact/Aufwand-Verhältnis bzw. echtem Korrektheits-Risiko:

| # | Thema | Ort | Impact | Aufwand |
|---|-------|-----|--------|---------|
| 1 | **God-Module `app.py` (2734 Z.) in Package aufteilen** | app.py | high | L |
| 2 | **Endpoint-Fehler-Boilerplate ~30× deduplizieren** (Decorator) | app.py | high | M |
| 3 | **Zwei parallele Rate-Limiter laufen gleichzeitig** | app.py | high | M |
| 4 | **`SearchAgent` God-Object (~1960 Z., ~50 Methoden) zerlegen** | core/agent/agent.py | high | L |
| 5 | **Retry umschließt Routing mit Seiteneffekten** → doppelte Suchen/Memory-Writes | core/agent/agent.py:591 | high | S |
| 6 | **Toter/verwaister SQLite `SessionManager` + Namenskollision** | core/session_manager.py | high | S |
| 7 | **Gemeinsame `IntelModule`-Basis für die 6 OSINT-Module** | core/osint/*_intel.py | high | L |
| 8 | **Tor-„skip DNS“-Guard zentralisieren** (Leak-Schutz) | core/osint/* | high | M |
| 9 | **Redis-vs-Fallback-Branching in eine `StorageBackend`-Strategie** | api_key_manager, rbac_manager | high | L |
| 10 | **LLM-HTTP/Stream-Logik 4× dupliziert, hart an Ollama gekoppelt** | core/llm_client.py | high | M |
| 11 | **Per-Prozess-Zufallssecret invalidiert API-Keys nach Restart** | core/api_key_manager.py:134 | med | S |
| 12 | **Token-Budget-Berechnung in beiden Agents dupliziert** | agent.py / langgraph_agent.py | high | M |

---

## Übergreifende Muster (Cross-Cutting)

Diese Punkte tauchten in mehreren unabhängigen Bereichen auf – am besten einmal
zentral lösen statt lokal je Modul.

### C1 – Naive `datetime.now()` bei sicherheitsrelevanten Timestamps
- **Ort:** `core/session_manager.py` (137, 212, 254, 423, 448, 519, 579), `core/api_key_manager.py` (104, 197, 449), `core/audit_logger.py:107`, `core/rbac_manager.py:195` — während `core/agent/agent.py` (851, 1004) bereits `datetime.now(UTC)` nutzt.
- **Problem:** Ablauf-/Expiry-Checks, Audit-Timestamps und Last-Used-Tracking nutzen timezone-naive Zeit. Über Hosts/DST hinweg werden Vergleiche und Ordering mehrdeutig; Sessions können falsch ablaufen. Konvention ist codebasisweit inkonsistent.
- **Vorschlag:** Einen `utils.utcnow()`-Helper einführen und **überall** auf `datetime.now(timezone.utc)` + ISO-8601-mit-Offset standardisieren.
- **Aufwand:** S · **Impact:** med (Summe: high)

### C2 – Redis-mit-Fallback-Boilerplate mehrfach handgeschrieben
- **Ort:** `core/api_key_manager.py:138-163, 343-450`, `core/rbac_manager.py:139-168, 170-323`, teilweise `utils/redis_rate_limiter.py`.
- **Problem:** Jeder Accessor rollt `if self.redis_client: try: … except: log; fallback file/memory` selbst aus; ~25 Zeilen `ConnectionPool.from_url(...)`/`ping()`/Init sind ebenfalls dupliziert. Fehlerbehandlung driftet (mal Fall-through zu Datei, mal `return DEFAULT_ROLE`).
- **Vorschlag:** Eine `StorageBackend`-Strategie (`RedisBackend`/`FileBackend`/`MemoryBackend`) bzw. `RedisBackedStore`-Basis, die Init, try/except-Fallback und get/set/delete kapselt. Manager drücken Logik einmal gegen das Interface aus.
- **Aufwand:** L · **Impact:** high

### C3 – Wiederkehrende Try/Except-Fehler-Boilerplate (Handler & Tools)
- **Ort:** `app.py` (~30 Endpoints), `tools/tool_registry.py:46-92`, `tools/rag.py` (fallback-Guards), `tools/osint_tool.py` (Compliance-Prolog).
- **Problem:** Nahezu identische `except Exception as e: logger.error(...); raise/return "... failed"`-Blöcke, dutzendfach kopiert – größte Einzelquelle von Rauschen/Zeilen und Drift-Risiko.
- **Vorschlag:** Pro Kontext ein Decorator/Helper: `@handle_errors("...")` (FastAPI), `_safe_tool(label, fn)` (Registry), `@_requires_chroma(default=[])` (RAG), `@compliance_checked(query_type)` (OSINT-Tool).
- **Aufwand:** M · **Impact:** high

### C4 – Magic Numbers / hartkodierte Config über die gesamte Codebasis
- **Ort:** u.a. `app.py` (CSP-Strings, `RATE_LIMIT`, `MAX_QUERY_LENGTH`), `main.py:158-185` (Token-Defaults), `core/agent/agent.py` (max_length 6000, max_tokens 700/650/550), `core/hallu_detect.py:657-802` (Scoring-Gewichte), Fetch-Größen/Timeouts in `tools/` & `utils/safe_fetch.py`.
- **Problem:** Tuning-Werte, Security-Header und Schwellen sind als Literale in der Logik verstreut; gleiche Defaults driften (z.B. `max_tokens` an mehreren Stellen).
- **Vorschlag:** Pro Domäne in `constants.py`/Config hoisten (`SECURITY_HEADERS`-Dict, `PROVIDER_TOKEN_PROFILES`, Scoring-Konstanten neben `SEVERITY_WEIGHTS`, `mb_to_bytes()`), aus `config` lesen.
- **Aufwand:** M · **Impact:** med

### C5 – Duplizierte Token-Schätzung & Token-Budget-Berechnung
- **Ort:** `core/agent/agent.py:363-405` vs `core/langgraph_agent.py:112-160` (Budget); `core/llm_client.py:104-134` vs `core/health/rich_dashboard.py:411-433` (~4 chars/token).
- **Problem:** Dieselbe `min(configured, max(64, window-512), window)`-Logik bzw. das 4-chars-pro-Token-Heuristik-Snippet mit denselben Magic-Werten mehrfach reimplementiert → Drift bei jeder Änderung.
- **Vorschlag:** `core/token_budget.py` mit `compute_token_budgets(...)` und `estimate_tokens(text)`; von allen Aufrufern nutzen.
- **Aufwand:** M · **Impact:** high

### C6 – Duplizierte Validierungs-Regexes & Domain-Extraktion
- **Ort:** Email-/Phone-/Domain-Regex in `email_intel.py:131`, `query_parser.py:115-116`, `query_enhancer.py:250-258`, `phone_intel.py:198`; `urlparse(...).netloc/.hostname`-Extraktion in `safe_fetch.py`, `rate_limiter.py`, `web_search.py`, `page_reader.py`, `validators.py`.
- **Problem:** Kanonische Patterns/Host-Normalisierung 3+× kopiert und können stumm auseinanderlaufen; teils `netloc` vs `hostname` inkonsistent (Port/Userinfo!).
- **Vorschlag:** `EMAIL_RE/PHONE_RE/DOMAIN_RE` + `classify_entity()` und ein `get_domain(url)` in `utils`/`_common` zentralisieren.
- **Aufwand:** S · **Impact:** med

### C7 – Mehrere handgerollte LRU-Caches & Singleton-Accessoren
- **Ort:** LRU: `core/hallu_detect.py:105-143` (OrderedDict) vs `core/unified_loader.py:299-336` (O(n)-Liste). Singleton: `safe_fetch.py:678`, `text_cleaner.py:267`, `cli_helper.py:449`, `async_utils.py:367`.
- **Problem:** Zwei unterschiedlich gute LRU-Implementierungen; das `global _x; if _x is None: …`-Muster 4× kopiert (inkl. `run_async`-Event-Loop-Fallback, der `osint._common` dupliziert).
- **Vorschlag:** Eine `utils.LRUCache` (OrderedDict-Variante) teilen; optional `lazy_singleton`-Factory / geteilter `run_async`.
- **Aufwand:** S · **Impact:** med

---

## 1. Entry-Points

### `app.py` ist ein God-Module über alle Concerns
- **Ort:** `app.py:1-2734` (gesamt)
- **Problem:** 2734 Zeilen mit Security-Bootstrap, 6 Middlewares, Auth/CSRF/RBAC-Deps, ~15 Pydantic-Modellen, Component-Lifecycle und ~40 Routes; Modelle zwischen Routes verstreut (1270, 2190, 2311, 2533).
- **Vorschlag:** Package `api/`: `middleware.py`, `security.py`, `models.py`, `startup.py` (Factories + Lifespan), `routers/*.py` je Domäne via `APIRouter`. `app.py` wird dünne Montage.
- **Aufwand:** L · **Impact:** high

### Endpoint-Fehler-Boilerplate ~30× dupliziert
- **Ort:** `app.py` – u.a. 1325, 1351, 1377, 1406, 1425, 1476, 1495, 1924, 2021-2187, 2303, 2444
- **Problem:** Fast jeder Handler wiederholt `except Exception as e: logger.error(...); raise HTTPException(500, ...)`. Siehe **C3**.
- **Vorschlag:** `@handle_errors("Failed to …")`-Decorator oder `ServiceError`-Exception-Handler. Zusammen mit Routern entfallen hunderte Zeilen.
- **Aufwand:** M · **Impact:** high

### Zwei überlappende Rate-Limiter laufen gleichzeitig
- **Ort:** `app.py:340-391` (`redis_rate_limit_middleware`) + `app.py:745-970` (`request_counts`, `check_rate_limit`-Dependency an ~20 Routes)
- **Problem:** Jeder geschützte Request wird doppelt limitiert – global via Redis-Middleware und nochmal via In-Memory-Dependency mit anderen Limits/Semantik. Globaler `request_counts`-Dict + Lock + manuelles Pruning ist redundanter Legacy-Pfad.
- **Vorschlag:** Eine Autorität wählen. Wenn Redis (mit Fallback) das Design ist: `check_rate_limit`/`request_counts`/`RATE_LIMIT` löschen und aus allen `dependencies=[...]` entfernen. Entfernt globalen mutablen State.
- **Aufwand:** M · **Impact:** high

### Category→Method-Dispatch-Dicts in Memory-Endpoints dupliziert
- **Ort:** `app.py:2331-2342` (remember), `2384-2397` (recall), `2482-2491` (forget)
- **Problem:** Drei fast identische singular/plural→`memory_store.*`-Maps, je Request neu gebaut; Sets driften (forget fehlen Handler).
- **Vorschlag:** Eine kanonische Kategorie-Registry (plural→singular einmal normalisieren) mit `{remember, get_all, forget}`-Callables; `VALID_MEMORY_CATEGORIES` einfalten.
- **Aufwand:** S · **Impact:** med

### `main.py` Settings-Editor: wucherndes UI/Config-Geflecht
- **Ort:** `main.py:483-980` (`show_settings` + `_edit_*`)
- **Problem:** ~500 Zeilen fast identischer prompt/validate/assign/print-Blöcke; Business-Regeln (Defaults, Ranges, Choices) imperativ statt deklarativ.
- **Vorschlag:** Settings als deklaratives Schema (Feld-Deskriptoren: path, type, label, range/choices, default) modellieren; `show_settings` + `edit_settings` generisch daraus treiben. Nach `cli/settings_editor.py`.
- **Aufwand:** L · **Impact:** high

### Adaptive-System-Initialisierung 4× dupliziert
- **Ort:** `main.py:1927-1971`, `1974-2004`, `2007-2039`, `app.py:615-637`
- **Problem:** Gleiche Sequenz (LLM-Client → Monitor/Tracker try/except → `initialize_adaptive_system`) viermal mit subtilen Unterschieden; `adaptive_manager` wird gebunden aber nie genutzt (tote Bindung).
- **Vorschlag:** Ein `build_adaptive_system(config, agent, multihop_agent)` in gemeinsamem Modul; von CLI & API genutzt. Unbenutzte Bindung droppen.
- **Aufwand:** M · **Impact:** med

### Query-Routing zwischen CLI und API dupliziert
- **Ort:** `main.py:987-1017, 1431-1465, 1515-1561` vs `app.py:1789-1803`
- **Problem:** „OSINT/Result-Reference/`<`-Kontext → SearchAgent, sonst adaptive“ dreifach unabhängig implementiert; hohe Divergenz-Gefahr.
- **Vorschlag:** Zentrales `route_query(agent, adaptive_processor, query)` in `core`, das Antwort + Strategie-Metadaten liefert; von allen drei Callern genutzt.
- **Aufwand:** M · **Impact:** med

### Atomic-Config-Write dupliziert und divergent
- **Ort:** `main.py:190-209` (`save_config`) vs `app.py:2215-2221` (`_update_and_write_config`)
- **Problem:** Zwei unabhängige tmp+`os.replace`-Writer mit unterschiedlichem Encoding/Formatting (`ensure_ascii`/UTF-8 vs Defaults) → `config.json` je nach Pfad inkonsistent geschrieben.
- **Vorschlag:** Ein `write_config_atomic(config, path)` in `core/config.py`, konsistent + mit Lock; von CLI & API genutzt.
- **Aufwand:** S · **Impact:** med

### Provider-Konfig-Prompts doppelt (Setup vs Settings-Editor)
- **Ort:** `main.py:604-630` vs `main.py:1709-1761` + `_suggest_default_model:1680-1706`
- **Problem:** Provider-Liste, „braucht API-Key“-Hinweise und Modell-Vorschläge zweimal mit abweichendem Wording/Verhalten.
- **Vorschlag:** `PROVIDERS`-Registry (name→display, needs_key, model suggestions) + ein `prompt_for_provider_and_model(config)`.
- **Aufwand:** S · **Impact:** med

### Globaler mutabler Component-State via `global`
- **Ort:** `app.py:405-413` + `640-687` (`startup_event`)
- **Problem:** Acht Modul-Singletons via `global` mutiert, direkt von jedem Endpoint gelesen → untestbar, an Import-Zeit gekoppelt; `app.state`-Nutzung inkonsistent.
- **Vorschlag:** Components auf `app.state` / `Services`-Dataclass im Lifespan; Zugriff via `get_services`-Dependency (ermöglicht Override in Tests).
- **Aufwand:** M · **Impact:** med

### Irreführender Name: `hash_api_key_for_logging` ist Identity-Ableitung
- **Ort:** `app.py:755-783` (+ ~13 Call-Sites)
- **Problem:** Trotz Namens die kanonische Ableitung der Principal-/User-Identität für RBAC/CSRF/Audit – sicherheitskritisch, nicht kosmetisch. `_rate_limit_user_id` macht dasselbe HMAC parallel.
- **Vorschlag:** Zu `derive_user_id`/`principal_id` umbenennen (dünner Alias möglich), mit `_rate_limit_user_id`/`_short_id` in `api/identity.py` kolokieren.
- **Aufwand:** S · **Impact:** med

### Tote/Stub-Endpoints
- **`main.py:77-87` `InputValidator.validate_url`** – nie aufgerufen (nur `validate_url_ssrf_safe` genutzt). **Löschen.** (S/low)
- **`app.py:2136-2164` `refresh_session`** – No-Op-Stub, berechnet Identity und verwirft sie, gibt hartkodiert „extended by 24h“ zurück ohne Session-Store zu berühren. **Implementieren oder entfernen.** (S/low)

### In-Function-Imports & Logger-Neuerzeugung
- **Ort:** `main.py:1433, 1524` (`logging.getLogger` in Funktion), diverse deferred Imports (`main.py:1160, 1187, 1224, 1872…`, `app.py:618`)
- **Vorschlag:** Ein Modul-`logger`; deferred Imports auditieren, nur echte Lazy-/Optional-Fälle behalten.
- **Aufwand:** S · **Impact:** low

---

## 2. Agent-Core

### `SearchAgent` ist ein God-Object (~1960 Z., ~50 Methoden)
- **Ort:** `core/agent/agent.py:277-1962`
- **Problem:** ≥7 Verantwortlichkeiten (Init/Config, Injection-Detection, Result-Reference-Parsing, Connection-Analyse, Page-Loading, Kontext-Aufbau, Memory-Formatting, Intel-Extraktion). `ToolsFlow`/`OSINTFlow` greifen über ~15 `self.agent._private`-Methoden zurück (bidirektionale Kopplung).
- **Vorschlag:** Kollaboratoren extrahieren (Muster wie bestehende Flow-Objekte): `InjectionDetector`, `ResultReferenceHandler`, `ConnectionAnalyzer`, `PageLoader`, `MemoryContextFormatter`, `IntelExtractor`. `SearchAgent` wird dünner Orchestrator.
- **Aufwand:** L · **Impact:** high

### Toter/verwaister SQLite `SessionManager` + Namenskollision
- **Ort:** `core/session_manager.py:68-727` (gesamt)
- **Problem:** 726-Zeilen-SQLite-`SessionManager` von keinem Modul importiert (per grep); der Agent nutzt eine **andere** gleichnamige Klasse aus `core.agent.session`. Zwei Klassen gleichen Namens – eine live, eine tot – ist eine Wartungsfalle.
- **Vorschlag:** Erreichbarkeit vom API-Server prüfen. Ungenutzt → löschen. Genutzt → umbenennen (`UserSessionStore`) und via Test importieren.
- **Aufwand:** S · **Impact:** high

### Retry umschließt Routing mit Seiteneffekten
- **Ort:** `core/agent/agent.py:591-631` (`@retry_on_failure(max_retries=2)`)
- **Problem:** Der dekorierte `_query_direct` macht Routing **mit Seiteneffekten** (Injection-Check, OSINT-Handling inkl. Live-Websuche + Memory-Writes, Result-Reference). Bei Exception wird alles bis zu 2× wiederholt → doppelte Suchen/Memory-Writes.
- **Vorschlag:** Retry nur auf `_generate_validated_response` (reine Generierung) verschieben; `_query_direct` bleibt un-retried Routing.
- **Aufwand:** S · **Impact:** high

### Token-Budget-Berechnung in beiden Agents dupliziert
- **Ort:** `agent.py:363-405` vs `langgraph_agent.py:112-160` — siehe **C5**.
- **Vorschlag:** Geteilter `compute_token_budgets(...) -> TokenBudget`.
- **Aufwand:** M · **Impact:** high

### Tote Methode `SearchAgent._is_osint_query`
- **Ort:** `core/agent/agent.py:1714-1727`
- **Problem:** Nie aufgerufen; instanziiert je Call einen neuen `OSINTQueryParser` (dritter unabhängiger Detection-Pfad neben `main.py` und `has_osint_operators`).
- **Vorschlag:** Löschen; auf `has_osint_operators` konsolidieren.
- **Aufwand:** S · **Impact:** med

### Injection-Refusal-Message dupliziert statt Konstante
- **Ort:** `tools_flow.py:28-32` vs `agent.py:132-136` (`INJECTION_REFUSAL_MESSAGE`)
- **Vorschlag:** In `tools_flow` die Konstante importieren/zurückgeben.
- **Aufwand:** S · **Impact:** med

### Search-Result-Compaction + Session-Storage dupliziert
- **Ort:** `tools_flow.py:284-332` vs `osint_flow.py:764-821`
- **Problem:** Beide lesen dieselben Config-Keys, rufen `_compact_search_results`, slicen, setzen `session.last_search_results` und loggen identisch; nur Config-Section (`search` vs `osint`) unterscheidet sich.
- **Vorschlag:** `store_search_results(results, cfg_section)`-Helper, den beide Flows nutzen.
- **Aufwand:** M · **Impact:** med

### Drei fast identische Page-Load-and-Cache-Implementierungen
- **Ort:** `agent.py:817-860`, `954-1022`, `1212-1243`
- **Problem:** Alle rufen `read_page`, behandeln `None` mit „robots/blacklist/network“-Message, sanitizen, normalisieren, schreiben in `loaded_pages_cache` – kopiert mit subtilen Unterschieden (max_tokens 700 vs 650).
- **Vorschlag:** Ein `PageLoader.load(url, title, num, max_tokens) -> LoadedPage` (mit Error-Feld); alle drei Caller nutzen es.
- **Aufwand:** M · **Impact:** med

### `_process_domain_intelligence` / `_process_ip_intelligence` teilen Template
- **Ort:** `osint_flow.py:464-528` & `530-588`
- **Problem:** Gleiche Form (analyze → format/fallback → metadata + remember → `last_search_query`), ~60 duplizierte Zeilen je Methode.
- **Vorschlag:** `_process_entity_intelligence(entity, analyzer, formatter, remember_fn, …)`-Template bzw. `_format_or_fallback` + `_persist_to_memory`.
- **Aufwand:** M · **Impact:** med

### Fragiles 8-Tupel aus `_initialize_osint_components`
- **Ort:** `osint_flow.py:135-166`, entpackt in :27
- **Problem:** Gibt entweder Error-`str` oder 8-Element-Positional-Tupel zurück, positional entpackt → Reihenfolge-Änderung bricht alles still. `success` wird für 6/7 Komponenten verworfen (fehlgeschlagenes email/phone-Init unerkannt).
- **Vorschlag:** `@dataclass OSINTComponents` (oder `None` bei fatalem Fehler); `success` explizit prüfen.
- **Aufwand:** S · **Impact:** med

### `_process_forget_command`: langer Branch-Baum mit Inline-Maps
- **Ort:** `osint_flow.py:656-730`
- **Problem:** 75-Zeilen-Methode mit verschachteltem if/elif, Inline-Alias-Map (669-680), Inline-Label-Dict (687-694), weiterem Typ-Dispatch (702-714).
- **Vorschlag:** Maps auf Modulebene hoisten; in `_forget_all`/`_forget_category`/`_forget_single` splitten, via Tabelle dispatchen.
- **Aufwand:** M · **Impact:** med

### Router-Node macht verschwendeten LLM-Call ohne Effekt
- **Ort:** `langgraph_agent.py:210-211, 247-274`
- **Problem:** `_router_node` klassifiziert SIMPLE/COMPLEX per LLM, Ergebnis wird nur an `reasoning_path` angehängt; beide Kanten führen ohnehin zu `initial_search`. Reine Latenz/Kosten.
- **Vorschlag:** Node entfernen (direkt zu `initial_search`) **oder** Klassifikation echt verzweigen lassen.
- **Aufwand:** S · **Impact:** med

### Inkonsistente Fehlerbehandlung über OSINT-Processing
- **Ort:** `osint_flow.py:208-229` (email/`safe_execute`), `364-382` (phone/ungeschützt), `530-537` (ip/bare try), `590-598` (username/bare try)
- **Problem:** Vier Geschwister-Methoden, vier Fehlerstrategien; `_process_phone_intelligence` greift `phone_result['valid']`/`['input']` ohne KeyError-Guard.
- **Vorschlag:** Auf ein Muster standardisieren (`safe_execute` mit typisiertem Default); Dict-Zugriffe einheitlich absichern.
- **Aufwand:** M · **Impact:** med

### Weitere (S/low–med)
- **Zwei identische LLM-Search-Term-Extractors** `agent.py:891-905` & `1054-1068` → ein parametrisiertes `_extract_search_term(query, examples)`.
- **Große Keyword/Pattern/Prompt-Blöcke** `agent.py:42-274` (~230 Z. Business-Daten im God-Modul); `CONTEXT_PHONE_PATTERNS`/`QUERY_PHONE_PATTERNS` unterscheiden sich nur um `/` → aus einer Basis ableiten. Nach `constants.py`/YAML.
- **Web-Search-Tool je Graph-Node neu aufgelöst** `langgraph_agent.py:290, 395` → einmal in `__init__` cachen.
- **SQLite-Boilerplate** in `session_manager.py` (jede Methode `with _get_connection()`, positionaler `row[0..7]`, kein `row_factory`, kein Rollback) → `_execute`/`_execute_write`-Helper + `sqlite3.Row`.
- **`decide_which_tool`** `tools_flow.py:110-170` mischt Heuristik + 2 LLM-Calls + inline Prompts → splitten.
- **Inkonsistenter Stream-Flag-Zugriff** `tools_flow.py:397` liest Raw-Config statt `agent._stream_enabled()`.

---

## 3. OSINT-Subsystem

### Keine gemeinsame Basis/Protocol für die Intel-Module – inkonsistente Interfaces
- **Ort:** `core/osint/{email,phone,domain,ip,social,company}_intel.py`, konsumiert in `tools/osint_tool.py:128-164`
- **Problem:** Sechs konzeptuell identische Module teilen nichts. Entry-Points inkonsistent: `analyze_email/phone/domain` (sync) vs `lookup_ip`/`analyze_username` (async) vs `analyze_company` (sync). Rendering an drei Orten: Standalone-Funktionen (`formatting.py`), Instanzmethoden `format_results()`, sowie `generate_social_report()`/`format_report()`. Zwingt `osint_tool` zu Per-Modul-Sonderfällen.
- **Vorschlag:** `IntelModule`-ABC/Protocol mit `analyze(target) -> IntelResult` + `format(result) -> str` (async-Variante oder sync `run_async`-Wrapper). Module in Dict per Query-Typ registrieren → `_collect_intelligence`/`_format_intelligence_sections` werden tabellengesteuerte Loops.
- **Aufwand:** L · **Impact:** high

### Tor-„skip local DNS“-Guard kopiert (Leak-Risiko)
- **Ort:** `email_intel.py:176-178`, `ip_intel.py:235-237`, `domain_intel.py:183-185, 224-226, 277-279, 414-417`
- **Problem:** `if is_tor_enabled(): log; return <empty>` in ~6 DNS/Socket-Entry-Points, je leicht anders → eine Stelle vergessen = Target-Leak.
- **Vorschlag:** Zentralisieren – Decorator `@skip_in_tor(return_value)` bzw. `guard_tor(op_label, default)`, der die blockierenden DNS-Calls umschließt. Leak-Policy an einem Ort.
- **Aufwand:** M · **Impact:** high

### Reverse-DNS & Geolocation zwischen ip_intel und domain_intel dupliziert
- **Ort:** Reverse-DNS `ip_intel.py:230-245` vs `domain_intel.py:273-293`; Geo via ip-api.com `domain_intel.py:295-358` vs `ip_intel.py:46-50, 400-413`
- **Problem:** Beide treffen `http://ip-api.com/json/{ip}` und mappen dasselbe Feldset; beide implementieren Tor-geschütztes `gethostbyaddr` (einmal async/aiohttp, einmal sync/requests). `DomainIntelligence` reimplementiert, was `IPIntelligence` schon besitzt.
- **Vorschlag:** Geteiltes `geolocate_ip(ip)` + `reverse_dns(ip)` in `_common`; `DomainIntelligence` delegiert an `IPIntelligence`.
- **Aufwand:** M · **Impact:** high

### `_calculate_confidence` in jedem Modul reimplementiert
- **Ort:** `email_intel.py:438-462`, `phone_intel.py:432-460`, `domain_intel.py:438-462`, `ip_intel.py:459-477`
- **Problem:** Vier Kopien: `score=0.0`, feste Gewichte je Bool-Bedingung, `min(score, 1.0)`. Nur die (Bedingung, Gewicht)-Paare unterscheiden sich.
- **Vorschlag:** `weighted_confidence(pairs: list[tuple[bool, float]])` in `_common.py`; je Modul nur deklarative Gewichtstabelle.
- **Aufwand:** S · **Impact:** med

### Severity-Threshold-Ladders dupliziert
- **Ort:** `email_intel.py:342-364` & `807-828`
- **Problem:** Zwei fast identische count→`{none..critical}`-Ladders mit inline Magic-Thresholds.
- **Vorschlag:** Ein `classify_severity(count, thresholds)` über geordnete Threshold-Tabelle.
- **Aufwand:** S · **Impact:** med

### Company `_extract_*_signals` fast-Duplikat-Loops
- **Ort:** `company_intel.py:443-519`
- **Problem:** Drei Methoden teilen dieselbe Loop (Text bauen → Term-Match → `_text_contains_company` → truncate → dedupe); nur Term-Sets/Trunc-Länge unterscheiden sich.
- **Vorschlag:** Ein parametrisiertes `_extract_signals(sources, terms, max_len, categories=None)`; `_extract_leadership` separat.
- **Aufwand:** S · **Impact:** med

### Wiederholtes Empty-Result-Dict in phone_intel
- **Ort:** `phone_intel.py:71-81, 110-120, 182-192`
- **Problem:** Gleicher 10-Key-Dict dreimal ausgeschrieben.
- **Vorschlag:** `_empty_result(phone, region)`-Factory (Muster existiert bereits in domain/social/ip).
- **Aufwand:** S · **Impact:** med

### Compliance-Prolog in jeder `OSINTTool.analyze_*`
- **Ort:** `tools/osint_tool.py:166-183, 248-266, 342-418`
- **Problem:** Sechs Methoden öffnen identisch mit `check_query(...)` + Early-Return + redacted Log.
- **Vorschlag:** `@compliance_checked(query_type)`-Decorator. Siehe **C3**.
- **Aufwand:** M · **Impact:** med

### Batch-Analyze-Methoden dupliziert
- **Ort:** `osint_tool.py:185-246` & `268-340`
- **Problem:** Gleiches Skelett (init summary → loop → per-item compliance → try/except analyze → append → counters); nur Aggregation unterscheidet sich.
- **Vorschlag:** Generisches `_analyze_batch(items, item_key, analyze_fn, query_type, summary_init, update_summary)`.
- **Aufwand:** M · **Impact:** med

### Report-Builder inkonsistent (String-Concat vs Line-List)
- **Ort:** `email_intel.py:398-436, 874-939`, `social_intel.py:809-889` (concat) vs domain/company (line-list)
- **Problem:** Lange `report += "..."`-Renderer mischen Daten & Präsentation, hartkodierte `'='*70`; Codebasis intern inkonsistent.
- **Vorschlag:** Auf Line-List-Muster vereinheitlichen; `section_header(title, width)`-Helper; idealerweise `format()`-Kontrakt der Basisklasse.
- **Aufwand:** M · **Impact:** med

### Weitere (S/low–med)
- **Magic Values / naive Cloud-Range-Detection** `ip_intel.py:363-366` (`any(r in ip_str)` → `'3.'` matcht `13.3.x`!) → `ipaddress`-Netz-Membership; Phone-Typ-Map via `phonenumbers.PhoneNumberType`; Domain-Listen zentralisieren.
- **`SearchQuery.__repr__`** `query_parser.py:53-83` handgepflegt (30 Z., vergisst Felder) → dataclass-Default oder via `dataclasses.fields()`.
- **Redundante `'@' in email`-Rechecks + tote Placeholder** `query_parser.py:312-313`; Stub-Methoden `search_email_online`, `search_phone_online`, `_get_platform_activity`, `_calculate_overall_sentiment/_activity_level` → implementieren oder quarantänisieren (`NotImplementedError`).

---

## 4. Tools

### Duplizierte Per-Provider-Search-Pipeline
- **Ort:** `tools/web_search.py:472-607, 632-765`
- **Problem:** `web_search`/`web_search_news`/`brave_search`/`serper_search` wiederholen dieselbe Pipeline; Brave (632-697) und Serper (700-765) sind bis auf URL/Header/Body/3 Feldnamen identisch (~65 Z. je neuer Provider).
- **Vorschlag:** `SearchProvider`-Protocol (bzw. Config-Dicts mit endpoint/header-builder/payload-builder/field-mapping) + ein `_run_http_provider(...)`, das request→map→`_filter_safe_results`→`rerank_results` macht. DDGS teilt denselben Tail via `_finalize_results(query, raw, profile)`.
- **Aufwand:** M · **Impact:** high

### `hybrid_search` ist teils toter Code / nicht wirklich hybrid
- **Ort:** `tools/rag.py:287-323`
- **Problem:** `self.search(query, top_k*2)` (307) verwirft Return komplett; `semantic_weight` (291) nie genutzt. Trotz Name/Docstring nur `multi_query_search` über lowercase/first-3-words. Irreführend + verschwendete DB-Query.
- **Vorschlag:** Echtes Hybrid-Scoring mit `semantic_weight` implementieren **oder** No-Op-`search`-Call + Param löschen und umbenennen.
- **Aufwand:** S · **Impact:** med

### Wiederholte `fallback_mode`-Guards + except-Boilerplate (RAG)
- **Ort:** `tools/rag.py:95-97, 124-127, 187-189, 228-231, 332-383`
- **Problem:** Fast jede `RAGManager`-Methode öffnet mit identischem `if self.fallback_mode: return <empty>` und umschließt Body mit try/except das `fallback_mode=True` setzt – ~6× mit divergierenden Messages.
- **Vorschlag:** `@_requires_chroma(default=[])`-Decorator; Methodenkörper halten nur den Chroma-Call.
- **Aufwand:** M · **Impact:** med

### Extra-Felder umgehen Sanitization in News-Search
- **Ort:** `tools/web_search.py:148-156, 589-595`
- **Problem:** `_safe_search_result` sanitized nur title/url/snippet; `**extra` (z.B. `source`, `date`) wird verbatim gemerged (155) und fließt in den LLM-Prompt – laut eigenem Threat-Model attacker-kontrolliert.
- **Vorschlag:** Jeden `extra`-Wert durch `_sanitize_text_fragment` vor `result.update(extra)`.
- **Aufwand:** S · **Impact:** med

### Ranking-Profile pro Fallback-Search doppelt aufgelöst
- **Ort:** `tools/web_search.py:528-529, 830, 843-850`
- **Problem:** `search_with_fallback` löst `effective_profile` (830) auf und übergibt an `web_search`, das (529) `resolve_ranking_profile` erneut auf die schon bereinigte Query anwendet; `resolve_search_preferences` ebenso doppelt.
- **Vorschlag:** Public Entry-Points in dünnen „resolve preferences“-Wrapper + internes `_search_impl(cleaned_query, region, profile, ...)` splitten.
- **Aufwand:** M · **Impact:** med

### `read_page` mischt fetch/parse/sanitize/format + redundanter Re-Fetch
- **Ort:** `tools/page_reader.py:373-431` (+ `search_contact_info:213-274`)
- **Problem:** `read_page` orchestriert alles; `search_contact_info` fetcht die Hauptseite ein **zweites** Mal, obwohl `read_page` `response.text` schon hält.
- **Vorschlag:** Fetch-Layer (HTML) / Parse-Extract-Layer (pure) / Format-Layer trennen; bereits geholtes HTML in Contact-Extraktion durchreichen.
- **Aufwand:** M · **Impact:** med

### Per-Block-Wrapping erzeugt viele External-Content-Marker
- **Ort:** `tools/page_reader.py:409-420`
- **Problem:** `sanitize_crawled_content_for_llm` je Block (body/contact/links) → mehrere `[EXTERNAL_WEB_CONTENT_START/END]`-Paare, Token-Bloat, mehrfacher Decode/Filter.
- **Vorschlag:** Volltext zuerst zusammensetzen, dann **einmal** wrappen; Per-Feld-XSS-Sanitization separat.
- **Aufwand:** S · **Impact:** med

### Weitere (S/low)
- **ToolRegistry-Wrapper-Boilerplate** `tool_registry.py:46-92` → `_safe_tool(label, fn)` (siehe **C3**).
- **Magic Values** (Timeouts 10, max_size 10/20/5 MB, Caps 3/5/10/15) `page_reader.py`, `rag.py:410-411`, `web_search.py:241,369,380` → benannte Konstanten/Config.
- **Deferred `import requests`/`urllib.parse` in Funktionen** `web_search.py:649,717`, `page_reader.py:93` → Modulebene.
- **Host/Domain-URL-Parsing-Helfer** `web_search.py:193-214, 383-392`, `page_reader.py:163,174` → `_normalized_host(url)` (siehe **C6**).
- **`wiki_lookup`** `wiki_lookup.py:31-34` – zwei Netzwerk-Round-Trips (`page` + `summary`) für denselben Artikel → `page.summary` nutzen; globaler `set_lang`-State kapseln.

---

## 5. Utils

### Token-Bucket-Refill-Mathe in RedisRateLimiter konsolidieren
- **Ort:** `utils/redis_rate_limiter.py:224-236, 285-317, 346-401`
- **Problem:** Refill-Formel dreimal reimplementiert (`_refill_bucket`, `_check_rate_limit_memory`, `get_rate_limit_status`); Reset-Time-Berechnung ebenfalls 3×. Drift zwischen Redis- und Memory-Pfad leicht.
- **Vorschlag:** Pure Helfer `_compute_tokens(...)` + `_reset_at(...)`; Memory-Fallback wird dünner Wrapper um denselben Kern.
- **Aufwand:** M · **Impact:** high

### Überladene `SafeFetcher.fetch`-Exception-Leiter
- **Ort:** `utils/safe_fetch.py:541-635`
- **Problem:** ~95 Zeilen mischen Policy, Rate-Limiting, Header, Streaming-Download, Bookkeeping und 7-Branch-`except` + `finally`.
- **Vorschlag:** `_handle_fetch_exception(domain, exc)`-Dispatch + Happy-Path in `_perform_fetch`; `fetch` wird Orchestrator.
- **Aufwand:** M · **Impact:** high

### validators.py nach Verantwortung splitten (640 Z.)
- **Ort:** `utils/validators.py` (gesamt)
- **Problem:** Ein Modul mischt SSRF/DNS (32-353), LLM-Output-Guard (356-374), Query-Validierung (377-447), Filename-Sanitization (450-468), Log-Sanitization (471-639).
- **Vorschlag:** In `ssrf.py`, `sanitizers.py`, `query_validation.py` splitten; aus `validators` re-exportieren (Backwards-Compat).
- **Aufwand:** M · **Impact:** high

### Fragile Content-Length-Behandlung via String-Matching
- **Ort:** `utils/safe_fetch.py:436-452`
- **Problem:** Unterscheidet Oversize- von `int()`-Parse-Fehler über `"exceeds maximum" in str(ve)` – bricht bei Message-Änderung.
- **Vorschlag:** `int(content_length)` in eigenem try/except; dedizierte `ResponseTooLargeError(ValueError)` für Typ-basiertes Catch.
- **Aufwand:** S · **Impact:** med

### Doppelte/inkonsistente „suspicious pattern“-Query-Checks
- **Ort:** `utils/validators.py:377-447` (+ `DANGEROUS_PATTERNS:32-39`)
- **Problem:** `validate_query` und `sanitize_query` pflegen zwei überlappend-verschiedene Pattern-Listen, teils überlappend mit `DANGEROUS_PATTERNS`; eine gibt `bool`, andere raised.
- **Vorschlag:** Ein `SUSPICIOUS_QUERY_PATTERNS` (precompiled) + `_first_matching_pattern(text)`; Listen zu einer autoritativen zusammenführen.
- **Aufwand:** S · **Impact:** med

### Inkonsistente Result-Dict-Form in AsyncFetcher
- **Ort:** `utils/async_utils.py:62, 100-114`
- **Problem:** Success-Pfad liefert `"headers"`, Timeout/Except-Branches nicht → `KeyError` bei Callern. Konstruktion 4× wiederholt.
- **Vorschlag:** `_result(url, content=None, status=None, headers=None, error=None)`-Factory (immer voller Key-Satz).
- **Aufwand:** S · **Impact:** med

### Zu breiter Except maskiert Redis-Fallback-Absicht
- **Ort:** `utils/redis_rate_limiter.py:203`
- **Problem:** `except (redis.RedisError, Exception)` – `RedisError` tot (von `Exception` gefangen); echte Bugs (`TypeError`) werden als „Redis unavailable“ verschluckt.
- **Vorschlag:** Nur `redis.RedisError, ConnectionError, TimeoutError` fangen; Programmierfehler propagieren.
- **Aufwand:** S · **Impact:** med

### Weitere (S/low–med)
- **Duplizierte Wort-Grenzen-Truncation & URL-Regex** `text_cleaner.py:107-115 vs 129-139; 249 vs 262` (+ Variante `validators.py:598`) → gemeinsame Truncation, kompilierte URL-Konstante (siehe **C6**).
- **6 fast identische deprecated-Wrapper** `text_cleaner.py:290-371` → `_deprecated(new_name, fn)`-Factory oder droppen (nach grep).
- **Duplizierte Domain-Extraktion** `safe_fetch.py:116-118`, `rate_limiter.py:49-60,179-211` (`netloc` vs `hostname` inkonsistent!) → geteiltes `get_domain(url)` (siehe **C6**).
- **`max_size_mb*1024*1024` 4×** + unbenannte Schwellen (`PERMANENT_FAILURE_THRESHOLD=3`, `DNS_REBIND_RECHECK_DELAY=0.1`) → `mb_to_bytes()`/Konstanten (siehe **C4**).
- **`Console()` mehrfach instanziiert + KV-Table 3× handgebaut** `cli_helper.py` → Modul-`console` wiederverwenden, `_kv_table(rows, title)`-Helper.
- **Singleton-Accessor-Boilerplate 4×** (siehe **C7**).

---

## 6. Core-Services

### Sechs fast identische `remember_*` in Memory-Operations
- **Ort:** `core/memory/operations.py:58-289` (+ `forget_*:333-381`)
- **Problem:** `remember_email/phone/ip/username/domain` + `add_note` wiederholen ~6× dasselbe Skelett (validate → user/global-Limit → entry-dict → dedupe → append → save → log); `forget_*` nochmal 4× (nur `domain` fehlt forget). Bugfix N-fach nötig.
- **Vorschlag:** Data-driven Category-Spec (max_len, validator, normalizer, log-sanitizer) über `CATEGORIES` + generisches `_remember(category, value, metadata, user_id)`/`_forget(...)`. Public-Methoden werden dünne Wrapper (~230 → ~60 Z.).
- **Aufwand:** M · **Impact:** high

### Redis-vs-Fallback-Branching je Storage-Methode (Key/RBAC)
- **Ort:** `core/api_key_manager.py:343-450`, `core/rbac_manager.py:170-323` — siehe **C2**.
- **Vorschlag:** Geteilte `StorageBackend`-Strategie / `RedisBackedStore`-Basis.
- **Aufwand:** L · **Impact:** high

### LLM-HTTP/Stream-Logik 4× dupliziert, hart an Ollama gekoppelt
- **Ort:** `core/llm_client.py:241-431`
- **Problem:** Payload-Build, `session.post`, `raise_for_status`, Streaming-Loop in `_stream_generate`/`stream_generate` fast verbatim; `chat`/`get_embeddings` wiederholen post-Boilerplate. Alle Endpoints/Keys Ollama-spezifisch inline; kein `LLMClient`-Interface.
- **Vorschlag:** `_post(path, payload, stream)` + ein `_iter_stream(response)`; abstrakte `LLMClient`-Basis, `OllamaClient` als eine Implementierung. URL/Payload/Response-Keys zentralisieren.
- **Aufwand:** M · **Impact:** high

### Retry-Decorators ignorieren konfigurierte Retry-Parameter
- **Ort:** `core/llm_client.py:171-199` vs Konstruktor `36-73`
- **Problem:** `__init__` nimmt `max_retries`/`retry_min_wait`/`retry_max_wait`, aber `@retry` hartkodiert `stop_after_attempt(3)`/`wait_exponential(...)`. Config-Knöpfe sind **tot** (Decorators werden bei Klassendefinition ausgewertet, sehen keine Instanz-Config).
- **Vorschlag:** Params droppen **oder** programmatisches `Retrying(...)` aus `self.*` in den Methoden (bzw. `_with_retry`-Helper).
- **Aufwand:** M · **Impact:** med

### Per-Prozess-Zufallssecret invalidiert API-Keys nach Restart
- **Ort:** `core/api_key_manager.py:134-136`
- **Problem:** `os.getenv("RATE_LIMIT_SECRET", secrets.token_bytes(32))` – ohne Env-Var pro Prozessstart neues Zufalls-Secret → alle bestehenden Key-HMACs matchen nicht mehr, gespeicherte Keys nach Restart unvalidierbar. Latenter Correctness/Security-Footgun.
- **Vorschlag:** In Nicht-Dev fail-fast/laut warnen wenn Secret fehlt, oder generiertes Secret persistieren; Secret-Loading zentralisieren.
- **Aufwand:** S · **Impact:** med

### File-Key-Storage: Full-Rewrite, unindizierte Scans, kein Locking
- **Ort:** `core/api_key_manager.py:366-443`
- **Problem:** `_store_key_file` liest+schreibt bei jedem Store die ganze JSON-Datei (kein atomic temp-rename, anders als `memory/persistence.py`); `_get_key_by_id`/`_get_keys_by_user` linear-scannen; kein Lock → Korruption bei Concurrency.
- **Vorschlag:** Atomic temp+`os.replace`-Muster aus `PersistenceMixin._save` wiederverwenden, Lock + id/user-Index; idealerweise vom `FileBackend` (C2) absorbiert.
- **Aufwand:** M · **Impact:** med

### Audit-Log-Scanning dupliziert + Rotation-Count hartkodiert
- **Ort:** `core/audit_logger.py:346-449`
- **Problem:** `search_logs` & `get_stats` öffnen Dateien und `json.loads(line)` mit kopiertem `except JSONDecodeError`. `search_logs` hartkodiert `range(1, 11)` statt `self.backup_count` (>10 lässt ältere Logs still fallen); `get_stats` scannt nur die aktuelle Datei (inkonsistent).
- **Vorschlag:** `_iter_events(files)`-Generator teilen; Rotated-Range aus `self.backup_count`.
- **Aufwand:** S · **Impact:** med

### Magic Numbers in Hallucination-Scoring
- **Ort:** `core/hallu_detect.py:657-802`
- **Problem:** `/500`, `/10`, `<20`/`<10`, Penalties `0.4/0.2/0.15`, Gates `0.7/0.5`, Risk-Thresholds `0.8/0.5`, `>=2` – alle unbenannt in Methodenkörpern vergraben (anders als die sauberen Top-Konstanten). `alignment_score` kann vor Clamp negativ werden (Z. 422).
- **Vorschlag:** In benannte Konstanten/`DEFAULT_CONFIG` neben `SEVERITY_WEIGHTS` hoisten und aus `self.config` lesen (Detection-Level wirkt dann wirklich).
- **Aufwand:** S · **Impact:** med

### `enable_hallucination_detection` mutiert Caller-Config
- **Ort:** `core/llm_client.py:474-482`
- **Problem:** `config["enabled"] = True` mutiert das übergebene Dict; kombiniert mit `get_detector`-Global-Singleton (`hallu_detect.py:877-882`, das `config` bei existierendem `_detector` ignoriert) → order-abhängig, überraschend.
- **Vorschlag:** Dict kopieren (`{**config, "enabled": True}`); `get_detector` rekonfigurieren/dokumentieren; ggf. Prozess-Global durch injizierte Instanz ersetzen.
- **Aufwand:** S · **Impact:** med

### Weitere (S/low)
- **Drei LRU-Cache-Implementierungen** (siehe **C7**) → geteilte `utils.LRUCache`; `unified_loader._resource_access_order` löschen.
- **`_check_hallucination` baut „disabled result“ erneut** `llm_client.py:445-457` vs `hallu_detect.py:644-655` → `disabled_result()`-Factory teilen; redundanten lokalen Import entfernen.
- **Token-Schätzung 2×** (siehe **C5**).
- **`rich_dashboard.py` Threshold→Color-Ladder 3×** (553-578 + Titel-if/elif) → `threshold_color(value, warn, crit)` + `metric_row(...)`-Builder. *(Anmerkung: Die zwei „Dashboards“ – Tkinter-Test-GUI vs Rich-Monitor – sind KEINE Duplikate; nicht mergen.)*
- **Hartkodierte Tool-Registry + unerreichbarer Branch** `unified_loader.py:44-65, 131-170` → Registry via Konstruktor/`register_tool()`; explizit raisen bei unbekanntem Config-Kind.

---

## Empfohlene Reihenfolge

1. **Quick Wins / Korrektheit zuerst** (S, teils high-Impact): Retry-Scope-Fix (#5), toter `SessionManager` (#6), API-Key-Secret (#11), naive `datetime` (C1), tote Methoden/Endpoints, RAG `hybrid_search`, News-Extra-Sanitization.
2. **Shared Helpers** (S–M, entfernen viel Duplikat): C1 `utcnow`, C5 Token-Utils, C6 Regex/Domain, C7 LRU, `weighted_confidence`/`classify_severity`, Tor-Guard.
3. **Boilerplate-Decorators** (M): C3 (Handler/Tools/RAG/OSINT-Compliance), Rate-Limiter-Mathe.
4. **Struktur-Refactors** (L, planen): `app.py`→Package, `SearchAgent`-Zerlegung, `IntelModule`-Basis, `StorageBackend`, Settings-Schema, `LLMClient`-Abstraktion.

> Vor jedem Löschen (tote Klassen/Methoden/Endpoints) per `grep` erneut die
> Erreichbarkeit vom API-Server bestätigen – einige Module werden dynamisch geladen.
