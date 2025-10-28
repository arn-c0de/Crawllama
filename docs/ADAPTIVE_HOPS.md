# Adaptive Agent Hopping System

## Übersicht

Das **Adaptive Agent Hopping System** ist eine intelligente Routing-Schicht für CrawlLama, die automatisch den optimalen Agenten basierend auf Query-Komplexität, Systemressourcen und Performance-Metriken auswählt.

### Version
**1.0.0** - Initial Release

---

## 🎯 Kernfunktionalität

### Automatische Komplexitätserkennung

Das System analysiert eingehende Queries und klassifiziert sie in drei Komplexitätsstufen:

| Komplexität | Beschreibung | Agent | Tools | Hops |
|-------------|--------------|-------|-------|------|
| **LOW** | Einfache, faktische Fragen<br>"Was ist die Hauptstadt von Frankreich?" | SearchAgent | ❌ Nein | 0 |
| **MID** | Fragen, die Web-Suche erfordern<br>"Neueste Nachrichten über KI" | SearchAgent | ✅ Ja | 1 |
| **HIGH** | Multi-Step-Reasoning, Vergleiche<br>"Vergleiche X und Y, analysiere Trends" | MultiHopReasoningAgent | ✅ Ja | 1-5 |

### Multi-Faktor-Analyse

Die Komplexität wird durch mehrere Faktoren bestimmt:

1. **Query-Länge Heuristik**
   - < 50 Zeichen: Tendenziell einfach
   - 50-150 Zeichen: Mittel
   - \> 150 Zeichen: Komplex

2. **Multi-Part Detection**
   - Keywords: "and", "also", "compare", "versus", "vs"
   - Indikator für komplexe Anfragen

3. **Temporale/Sequentielle Indikatoren**
   - Keywords: "after", "before", "then", "first", "next", "steps"
   - Zeigt mehrstufige Reasoning-Anforderungen

4. **LLM-basierte Klassifikation**
   - Der LLM analysiert die Query semantisch
   - Fallback auf Heuristiken bei LLM-Fehlern

---

## 🔄 Agent-Eskalation

Das System unterstützt **Confidence-basierte Eskalation**:

```
LOW Complexity (SearchAgent ohne Tools)
    ↓ Confidence < 0.5
MID Complexity (SearchAgent mit Tools)
    ↓ Confidence < 0.5
HIGH Complexity (MultiHopReasoningAgent)
```

### Eskalations-Parameter

- **Max Eskalations-Versuche**: 2
- **Confidence-Schwellenwerte**:
  - Low: < 0.5 → Eskalation
  - Medium: 0.5 - 0.7
  - High: > 0.85

---

## 📊 Ressourcen-basierte Anpassung

### Ressourcen-Monitoring

Das System überwacht kontinuierlich:
- **CPU-Auslastung** (Schwellenwert: 80%)
- **Speicher-Auslastung** (Schwellenwert: 85%)

### Degradation-Strategie

Bei hoher Ressourcenbelastung:

```
HIGH Complexity → MID Complexity (Downgrade)
Max Hops: 5 → Max Hops: 2 (Degraded Mode)
```

Dies verhindert System-Überlastung und garantiert Stabilität.

---

## 🏗️ Architektur

### Komponenten-Übersicht

```
┌─────────────────────────────────────────────────────────────┐
│                      CrawlLama API                          │
│                         (app.py)                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
           ┌─────────────────────────────┐
           │  AdaptiveQueryProcessor     │
           │  (adaptive_integration.py)  │
           └──────────┬──────────────────┘
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
┌──────────────────┐      ┌──────────────────────┐
│ AdaptiveHopManager│      │  Query Execution     │
│ (adaptive_hops.py)│      │  • SearchAgent       │
└──────────────────┘      │  • MultiHopAgent     │
         │                └──────────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌─────────┐ ┌──────────────┐
│System   │ │Performance   │
│Monitor  │ │Tracker       │
└─────────┘ └──────────────┘
```

### Klassenstruktur

#### 1. **AdaptiveHopManager** (`core/adaptive_hops.py`)

Hauptklasse für Komplexitätsanalyse und Strategie-Entscheidungen.

```python
class AdaptiveHopManager:
    def __init__(self, llm, config, system_monitor, performance_tracker)

    # Haupt-Methoden
    def analyze_query_complexity(query: str) -> (ComplexityLevel, metadata)
    def check_resource_constraints() -> resource_status
    def decide_agent_strategy(query: str) -> strategy_dict
    def should_escalate(strategy, confidence, attempt) -> (bool, new_strategy)
```

**Rückgabe-Format von `decide_agent_strategy`:**

```python
{
    "complexity": "low" | "mid" | "high",
    "complexity_metadata": {
        "query_length": int,
        "factors": ["length: simple", "multi_part: yes", ...],
        "llm_classification": "LOW" | "MID" | "HIGH"
    },
    "resource_status": {
        "constrained": bool,
        "cpu_percent": float,
        "memory_percent": float,
        "recommendation": str
    },
    "agent_type": "SearchAgent" | "MultiHopReasoningAgent",
    "use_multihop": bool,
    "use_tools": bool,
    "max_hops": int,
    "confidence_threshold": float,
    "reasoning": [list of decision reasons],
    "degraded": bool  # optional, nur wenn downgraded
}
```

#### 2. **AdaptiveQueryProcessor** (`core/adaptive_integration.py`)

Integrationsschicht zwischen AdaptiveHopManager und den Agenten.

```python
class AdaptiveQueryProcessor:
    def __init__(self, agent, multihop_agent, adaptive_manager)

    # Haupt-Methoden
    def process_query(query, force_complexity, enable_escalation) -> response
    def _execute_strategy(query, strategy) -> result
    def _estimate_confidence(answer) -> confidence_score
```

**Rückgabe-Format von `process_query`:**

```python
{
    "answer": str,
    "confidence": float | None,
    "strategy": {
        "complexity": str,
        "agent_type": str,
        "use_multihop": bool,
        "use_tools": bool,
        "max_hops": int,
        "reasoning": [list of reasons]
    },
    "metadata": {
        "complexity_analysis": {...},
        "resource_status": {...},
        "attempts": int,
        "escalation_history": [
            {
                "attempt": int,
                "from_agent": str,
                "to_agent": str,
                "reason": str,
                "confidence": float
            }
        ],
        "elapsed_time": float
    },
    # Optional fields from MultiHopAgent
    "steps": int | None,
    "search_queries": [list] | None,
    "reasoning_path": [list] | None
}
```

#### 3. **ComplexityLevel** (Enum)

```python
class ComplexityLevel(Enum):
    LOW = "low"
    MID = "mid"
    HIGH = "high"
```

#### 4. **AdaptiveConfig** (Dataclass)

Konfigurationsparameter für das adaptive System:

```python
@dataclass
class AdaptiveConfig:
    # Feature Toggles
    enable_resource_monitoring: bool = True
    enable_confidence_escalation: bool = True

    # Resource Thresholds
    cpu_threshold_high: float = 80.0
    memory_threshold_high: float = 85.0

    # Confidence Thresholds
    confidence_low: float = 0.5
    confidence_medium: float = 0.7
    confidence_high: float = 0.85

    # Max Hops per Complexity
    max_hops_low: int = 0
    max_hops_mid: int = 1
    max_hops_high: int = 5

    # Fallback
    fallback_on_resource_constraint: bool = True
    degraded_mode_max_hops: int = 2
```

---

## 🚀 Integration in app.py

### Schritt 1: Imports hinzufügen

```python
# In app.py nach den bestehenden imports hinzufügen:
from core.adaptive_integration import initialize_adaptive_system
```

### Schritt 2: Initialisierung

```python
# Nach der Initialisierung von agent und multihop_agent (ca. Zeile 295)

# Initialize adaptive system
adaptive_manager = None
adaptive_processor = None

try:
    adaptive_manager, adaptive_processor = initialize_adaptive_system(
        llm=agent.llm,  # Reuse LLM from SearchAgent
        agent=agent,
        multihop_agent=multihop_agent,
        system_monitor=system_monitor,
        performance_tracker=performance_tracker
    )
    logger.info("Adaptive system initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize adaptive system: {e}", exc_info=True)
    # Continue without adaptive system
```

### Schritt 3: Pydantic Model erweitern

```python
# Nach dem bestehenden QueryRequest (ca. Zeile 520)

class AdaptiveQueryRequest(BaseModel):
    """Request model for adaptive query endpoint."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUERY_LENGTH,
        description="User query"
    )
    force_complexity: Optional[str] = Field(
        None,
        description="Force specific complexity: 'low', 'mid', or 'high'"
    )
    enable_escalation: bool = Field(
        True,
        description="Enable confidence-based escalation"
    )

    @validator('query')
    def sanitize_query_input(cls, v):
        return sanitize_query(v)

class AdaptiveQueryResponse(BaseModel):
    """Response model for adaptive query endpoint."""
    answer: str
    confidence: Optional[float]
    strategy: Dict[str, Any]
    metadata: Dict[str, Any]
    steps: Optional[int] = None
    search_queries: Optional[List[str]] = None
    reasoning_path: Optional[List[str]] = None
```

### Schritt 4: Endpoint hinzufügen

```python
# Neuer Endpoint nach /query (ca. Zeile 768)

@app.post(
    "/query-adaptive",
    response_model=AdaptiveQueryResponse,
    dependencies=[Depends(check_rate_limit)]
)
async def query_adaptive_endpoint(request: AdaptiveQueryRequest):
    """
    Adaptive query endpoint with automatic agent selection.

    This endpoint automatically selects the optimal agent based on:
    - Query complexity analysis
    - System resource constraints
    - Confidence-based escalation

    Args:
        request: Adaptive query request

    Returns:
        Response with answer, strategy, and detailed metadata
    """
    if not adaptive_processor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Adaptive system not available"
        )

    try:
        result = adaptive_processor.process_query(
            query=request.query,
            force_complexity=request.force_complexity,
            enable_escalation=request.enable_escalation
        )

        return AdaptiveQueryResponse(**result)

    except Exception as e:
        logger.error(f"Adaptive query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Adaptive query processing failed"
        )
```

### Schritt 5: Stats-Endpoint erweitern (Optional)

```python
# Im bestehenden /stats endpoint (ca. Zeile 770)

@app.get("/stats", response_model=StatsResponse, dependencies=[Depends(check_rate_limit)])
async def stats_endpoint():
    """Get system statistics."""
    try:
        agent_stats = agent.get_stats() if agent else {}

        # ... bestehender Code ...

        # Add adaptive system stats
        if adaptive_manager:
            adaptive_stats = adaptive_manager.get_stats()
            # Füge adaptive_stats zur Response hinzu

        # ... rest des codes ...
```

---

## 📝 Verwendungsbeispiele

### Beispiel 1: Einfache Query (LOW Complexity)

**Request:**
```bash
curl -X POST "http://localhost:8000/query-adaptive" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is Python?",
    "enable_escalation": true
  }'
```

**Response:**
```json
{
  "answer": "Python is a high-level programming language...",
  "confidence": 0.85,
  "strategy": {
    "complexity": "low",
    "agent_type": "SearchAgent",
    "use_multihop": false,
    "use_tools": false,
    "max_hops": 0,
    "reasoning": ["Low complexity: SearchAgent without tools"]
  },
  "metadata": {
    "complexity_analysis": {
      "query_length": 15,
      "factors": ["length: simple"],
      "llm_classification": "LOW"
    },
    "resource_status": {
      "constrained": false,
      "cpu_percent": 25.3,
      "memory_percent": 45.2
    },
    "attempts": 1,
    "escalation_history": [],
    "elapsed_time": 1.2
  }
}
```

### Beispiel 2: Mittlere Query (MID Complexity)

**Request:**
```bash
curl -X POST "http://localhost:8000/query-adaptive" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Latest developments in quantum computing 2025",
    "enable_escalation": true
  }'
```

**Response:**
```json
{
  "answer": "Recent quantum computing developments include...",
  "confidence": 0.75,
  "strategy": {
    "complexity": "mid",
    "agent_type": "SearchAgent",
    "use_multihop": false,
    "use_tools": true,
    "max_hops": 1,
    "reasoning": ["Mid complexity: SearchAgent with web tools"]
  },
  "metadata": {
    "complexity_analysis": {
      "query_length": 48,
      "factors": ["length: medium", "multi_part: no"],
      "llm_classification": "MID"
    },
    "attempts": 1,
    "elapsed_time": 2.8
  }
}
```

### Beispiel 3: Komplexe Query mit Eskalation (HIGH Complexity)

**Request:**
```bash
curl -X POST "http://localhost:8000/query-adaptive" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare the economic impact of AI in healthcare vs manufacturing, then analyze which sector shows more growth potential over the next 5 years",
    "enable_escalation": true
  }'
```

**Response:**
```json
{
  "answer": "Comparing AI impact across sectors:\n\n1. Healthcare...\n2. Manufacturing...\n\nAnalysis: Healthcare shows 23% higher growth potential...",
  "confidence": 0.88,
  "strategy": {
    "complexity": "high",
    "agent_type": "MultiHopReasoningAgent",
    "use_multihop": true,
    "use_tools": true,
    "max_hops": 5,
    "reasoning": ["High complexity: MultiHop with 5 hops"]
  },
  "metadata": {
    "complexity_analysis": {
      "query_length": 142,
      "factors": ["length: complex", "multi_part: yes", "temporal: yes"],
      "llm_classification": "HIGH"
    },
    "attempts": 1,
    "elapsed_time": 15.3
  },
  "steps": 4,
  "search_queries": [
    "AI impact healthcare economic 2025",
    "AI manufacturing economic impact",
    "healthcare AI growth forecast 5 years",
    "manufacturing AI adoption trends"
  ],
  "reasoning_path": [
    "Router: Query classified as COMPLEX",
    "Initial search: AI healthcare economics",
    "Follow-up 1: Compare with manufacturing",
    "Follow-up 2: Growth analysis next 5 years",
    "Synthesis: Combined analysis complete"
  ]
}
```

### Beispiel 4: Force Complexity Override

**Request:**
```bash
curl -X POST "http://localhost:8000/query-adaptive" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the weather?",
    "force_complexity": "high",
    "enable_escalation": false
  }'
```

Dies zwingt selbst eine einfache Frage durch den MultiHopReasoningAgent.

### Beispiel 5: Eskalations-Szenario

Wenn eine LOW-Complexity Query niedrige Confidence zurückgibt:

**Initial Response (attempt 1):**
```json
{
  "strategy": {"complexity": "low", "agent_type": "SearchAgent"},
  "confidence": 0.4,
  "metadata": {
    "attempts": 2,
    "escalation_history": [
      {
        "attempt": 1,
        "from_agent": "SearchAgent",
        "to_agent": "SearchAgent",
        "reason": "Low confidence (0.40)",
        "confidence": 0.4
      }
    ]
  }
}
```

System eskaliert automatisch zu MID, dann ggf. HIGH complexity.

---

## 🔧 Konfiguration

### Standard-Konfiguration

Die Default-Werte sind in `AdaptiveConfig` definiert:

```python
config = AdaptiveConfig(
    # Monitoring
    enable_resource_monitoring=True,
    enable_confidence_escalation=True,

    # Ressourcen-Schwellenwerte
    cpu_threshold_high=80.0,
    memory_threshold_high=85.0,

    # Confidence-Schwellenwerte
    confidence_low=0.5,
    confidence_medium=0.7,
    confidence_high=0.85,

    # Hops pro Komplexität
    max_hops_low=0,
    max_hops_mid=1,
    max_hops_high=5,

    # Fallback
    fallback_on_resource_constraint=True,
    degraded_mode_max_hops=2
)
```

### Anpassung

Sie können die Konfiguration in `initialize_adaptive_system()` anpassen:

```python
from core.adaptive_hops import AdaptiveConfig

custom_config = AdaptiveConfig(
    max_hops_high=3,  # Reduziere max hops für HIGH complexity
    cpu_threshold_high=70.0,  # Strengere CPU-Limits
    confidence_low=0.6  # Höherer Eskalations-Schwellenwert
)

adaptive_manager = AdaptiveHopManager(
    llm=llm,
    config=custom_config,
    system_monitor=system_monitor,
    performance_tracker=performance_tracker
)
```

---

## 📊 Metriken & Monitoring

### Verfügbare Statistiken

```python
# Adaptive Manager Stats
GET /stats  # (nach Integration in stats_endpoint)

Response:
{
  "adaptive_manager": {
    "config": {
      "resource_monitoring": true,
      "confidence_escalation": true,
      "max_hops": {
        "low": 0,
        "mid": 1,
        "high": 5
      }
    },
    "current_resources": {
      "cpu_percent": 35.2,
      "memory_percent": 62.1
    }
  }
}
```

### Logging

Das System logged alle wichtigen Entscheidungen:

```
2025-10-28 12:34:56 - INFO - AdaptiveHopManager initialized
2025-10-28 12:35:01 - INFO - Query complexity: high | Factors: ['length: complex', 'multi_part: yes']
2025-10-28 12:35:01 - INFO - Agent strategy: MultiHopReasoningAgent | Reasoning: High complexity: MultiHop with 5 hops
2025-10-28 12:35:15 - INFO - Query processed successfully | Complexity: high | Agent: MultiHopReasoningAgent | Attempts: 1 | Time: 14.23s
```

---

## 🧪 Testing

### Unit Tests

Erstellen Sie Tests für die Kernfunktionalität:

```python
# tests/test_adaptive_hops.py

import pytest
from core.adaptive_hops import AdaptiveHopManager, ComplexityLevel, AdaptiveConfig

def test_complexity_analysis_low():
    # Mock LLM
    class MockLLM:
        def generate(self, prompt, system_prompt=None):
            return "LOW"

    manager = AdaptiveHopManager(llm=MockLLM())
    complexity, metadata = manager.analyze_query_complexity("What is Python?")

    assert complexity == ComplexityLevel.LOW
    assert "llm_classification" in metadata

def test_complexity_analysis_high():
    class MockLLM:
        def generate(self, prompt, system_prompt=None):
            return "HIGH"

    manager = AdaptiveHopManager(llm=MockLLM())
    query = "Compare X and Y, then analyze trends over time"
    complexity, metadata = manager.analyze_query_complexity(query)

    assert complexity == ComplexityLevel.HIGH
    assert "multi_part: yes" in str(metadata["factors"])

def test_resource_constraint_degradation():
    # Mock system monitor with high CPU
    class MockMonitor:
        def get_latest_metrics(self):
            class Metrics:
                cpu_percent = 85.0
                memory_percent = 90.0
            return Metrics()

    config = AdaptiveConfig(
        enable_resource_monitoring=True,
        cpu_threshold_high=80.0
    )

    manager = AdaptiveHopManager(
        llm=MockLLM(),
        config=config,
        system_monitor=MockMonitor()
    )

    resource_status = manager.check_resource_constraints()
    assert resource_status["constrained"] == True

def test_escalation_logic():
    manager = AdaptiveHopManager(llm=MockLLM())

    strategy = {
        "complexity": "low",
        "agent_type": "SearchAgent"
    }

    # Low confidence should trigger escalation
    should_escalate, new_strategy = manager.should_escalate(
        strategy,
        confidence=0.4,
        attempt_count=1
    )

    assert should_escalate == True
    assert new_strategy["complexity"] == "mid"
```

### Integration Tests

```python
# tests/test_adaptive_integration.py

import pytest
from core.adaptive_integration import AdaptiveQueryProcessor

def test_process_query_low_complexity(mock_agents):
    agent, multihop_agent, manager = mock_agents

    processor = AdaptiveQueryProcessor(
        agent=agent,
        multihop_agent=multihop_agent,
        adaptive_manager=manager
    )

    result = processor.process_query("Simple question?")

    assert result["strategy"]["complexity"] == "low"
    assert result["strategy"]["agent_type"] == "SearchAgent"
    assert result["metadata"]["attempts"] == 1

def test_process_query_with_escalation(mock_agents):
    # Setup mocks to return low confidence
    agent, multihop_agent, manager = mock_agents

    processor = AdaptiveQueryProcessor(
        agent=agent,
        multihop_agent=multihop_agent,
        adaptive_manager=manager
    )

    result = processor.process_query("Test query", enable_escalation=True)

    # Should have escalated
    assert result["metadata"]["attempts"] > 1
    assert len(result["metadata"]["escalation_history"]) > 0
```

---

## 🐛 Troubleshooting

### Problem: Adaptive System nicht verfügbar

**Symptom:**
```
503 Service Unavailable: Adaptive system not available
```

**Lösung:**
1. Prüfen Sie die Logs auf Initialisierungs-Fehler
2. Stellen Sie sicher, dass LLM verfügbar ist
3. Prüfen Sie, ob `adaptive_processor` korrekt initialisiert wurde

### Problem: Alle Queries werden als HIGH klassifiziert

**Symptom:**
Selbst einfache Queries verwenden MultiHopReasoningAgent

**Lösung:**
1. Prüfen Sie LLM-Prompts in `analyze_query_complexity()`
2. Adjustieren Sie die Heuristik-Schwellenwerte
3. Setzen Sie `force_complexity="low"` zum Testen

### Problem: Keine Eskalation trotz niedriger Confidence

**Symptom:**
Confidence < 0.5, aber keine Eskalation

**Lösung:**
1. Prüfen Sie `enable_escalation=true` im Request
2. Prüfen Sie `enable_confidence_escalation` in der Config
3. Prüfen Sie `attempt_count` vs `max_escalation_attempts`

### Problem: Ressourcen-Monitoring funktioniert nicht

**Symptom:**
`resource_status.constrained` ist immer `false`

**Lösung:**
1. Stellen Sie sicher, dass `system_monitor` an `AdaptiveHopManager` übergeben wurde
2. Prüfen Sie `enable_resource_monitoring=true` in der Config
3. Prüfen Sie `system_monitor.get_latest_metrics()` gibt Daten zurück

---

## 🎨 Best Practices

### 1. Query-Optimierung

```python
# ❌ Schlecht: Zu vage
"Tell me about AI"

# ✅ Gut: Spezifisch
"What are the latest AI developments in healthcare in 2025?"

# ✅ Gut: Klar strukturiert
"Compare AI adoption rates in healthcare vs manufacturing, then explain which has higher growth potential"
```

### 2. Eskalation nutzen

```python
# Aktivieren Sie Eskalation für unsichere Anfragen
{
  "query": "User-generated question",
  "enable_escalation": true  # ✅
}

# Deaktivieren für bekannt einfache Anfragen
{
  "query": "What is 2+2?",
  "enable_escalation": false  # ⚡ Schneller
}
```

### 3. Force Complexity für spezielle Fälle

```python
# Für kritische Business-Queries: Immer MultiHop
{
  "query": "Analyze our Q4 performance",
  "force_complexity": "high"  # ✅ Garantiert tiefe Analyse
}

# Für Known-Simple-Queries: Überspringe Analyse
{
  "query": "Company address?",
  "force_complexity": "low"  # ⚡ Schnelle Antwort
}
```

### 4. Monitoring in Produktion

```python
# Loggen Sie alle adaptive responses
result = adaptive_processor.process_query(query)

logger.info(f"Adaptive Query | "
           f"Complexity: {result['strategy']['complexity']} | "
           f"Agent: {result['strategy']['agent_type']} | "
           f"Attempts: {result['metadata']['attempts']} | "
           f"Time: {result['metadata']['elapsed_time']:.2f}s")

# Track escalation rates
if result['metadata']['escalation_history']:
    metrics.increment('adaptive.escalations')
```

---

## 🚀 Performance-Optimierungen

### 1. Caching für Komplexitäts-Analyse

Für identische oder ähnliche Queries:

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_complexity_analysis(query_hash):
    return manager.analyze_query_complexity(query)
```

### 2. Async Processing

Für parallele Query-Verarbeitung:

```python
import asyncio

async def process_multiple_queries(queries):
    tasks = [
        asyncio.to_thread(adaptive_processor.process_query, q)
        for q in queries
    ]
    return await asyncio.gather(*tasks)
```

### 3. Ressourcen-basiertes Rate Limiting

```python
def should_accept_query():
    resources = manager.check_resource_constraints()
    if resources["constrained"]:
        return False, "System under high load"
    return True, None
```

---

## 📈 Roadmap

### Version 1.1 (Geplant)

- [ ] Query-Caching für häufige Anfragen
- [ ] Machine Learning-basierte Komplexitätserkennung
- [ ] Performance-basierte Agent-Auswahl (Latenz-Historie)
- [ ] A/B-Testing Framework für Strategien

### Version 1.2 (Geplant)

- [ ] Cost-basierte Optimierung (LLM API Kosten)
- [ ] Multi-Language Support für Complexity-Prompts
- [ ] Custom Complexity-Classifier Training
- [ ] Real-time Dashboard für Monitoring

### Version 2.0 (Vision)

- [ ] Reinforcement Learning für optimale Agent-Auswahl
- [ ] User-spezifische Adaptierung (Learning from history)
- [ ] Distributed Agent Pooling
- [ ] Advanced Circuit Breaker Patterns

---

## 📚 Weiterführende Ressourcen

### Dokumentation
- [CrawlLama Hauptdokumentation](../README.md)
- [SearchAgent API](../core/agent.py)
- [MultiHopReasoningAgent API](../core/langgraph_agent.py)
- [System Monitoring](../core/health.py)

### Verwandte Konzepte
- **Multi-Hop Reasoning**: Iterative Informationssuche über mehrere Schritte
- **LangGraph**: Graph-basierte Agent-Workflows
- **Adaptive Systems**: Selbst-anpassende Software-Systeme
- **Circuit Breaker Pattern**: Resilienz-Muster für verteilte Systeme

---

## 🤝 Beitragen

Verbesserungen am Adaptive Hops System sind willkommen!

### Entwicklungs-Guidelines
1. Alle neuen Features brauchen Unit Tests (>80% Coverage)
2. Dokumentieren Sie alle öffentlichen APIs
3. Folgen Sie PEP 8 Style Guide
4. Fügen Sie Logging für wichtige Entscheidungen hinzu

### Pull Request Prozess
1. Fork das Repository
2. Erstellen Sie einen Feature Branch (`git checkout -b feature/adaptive-improvement`)
3. Committen Sie Ihre Änderungen
4. Push zum Branch (`git push origin feature/adaptive-improvement`)
5. Öffnen Sie einen Pull Request

---

## 📄 Lizenz

Dieses Modul ist Teil von CrawlLama und unterliegt der gleichen Lizenz wie das Hauptprojekt.

---

## 👥 Autoren

**CrawlLama Team**
- Version 1.0.0 - Initial Implementation (2025-10-28)

---

## ❓ FAQ

### Q: Kann ich das System ohne resource_monitoring verwenden?
**A:** Ja, setzen Sie `enable_resource_monitoring=False` in der Config. Das System arbeitet dann nur mit Komplexitäts-Analyse.

### Q: Wie kann ich die LLM-Komplexitäts-Analyse überspringen?
**A:** Verwenden Sie `force_complexity` im Request oder passen Sie die Heuristiken in `analyze_query_complexity()` an.

### Q: Funktioniert Eskalation mit force_complexity?
**A:** Nein, bei `force_complexity` ist die Komplexität fixiert. Eskalation ist nur für automatische Klassifikation aktiv.

### Q: Kann ich eigene Komplexitäts-Level hinzufügen?
**A:** Ja, erweitern Sie das `ComplexityLevel` Enum und passen Sie die Entscheidungslogik in `decide_agent_strategy()` an.

### Q: Wie teste ich das System lokal?
**A:** Verwenden Sie `/query-adaptive` Endpoint mit verschiedenen Queries und prüfen Sie die `strategy` und `metadata` Felder in der Response.

---

**Viel Erfolg mit dem Adaptive Agent Hopping System! 🚀**
