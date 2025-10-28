# Adaptive Hops - Quick Start Guide

## Was ist Adaptive Hops?

Ein intelligentes Routing-System, das **automatisch** den optimalen Agenten für jede Query auswählt:

- 🟢 **LOW Complexity** → SearchAgent ohne Tools (schnell)
- 🟡 **MID Complexity** → SearchAgent mit Web-Tools
- 🔴 **HIGH Complexity** → MultiHopReasoningAgent (1-5 Hops)

## Installation

Alle Dateien sind bereits im Projekt:

```
core/
  ├── adaptive_hops.py           # Kern-Logik
  └── adaptive_integration.py    # Integration Layer

examples/
  ├── adaptive_demo.py           # Demo-Skript
  └── app_integration_example.py # Integration Code

ADAPTIVE_HOPS.md                 # Vollständige Dokumentation
```

## Quick Start (3 Schritte)

### 1. Import hinzufügen

In `app.py` nach Zeile 23:

```python
from core.adaptive_integration import initialize_adaptive_system
```

### 2. System initialisieren

In `app.py` nach Zeile 295 (nach `multihop_agent` Initialisierung):

```python
# Initialize adaptive system
adaptive_manager = None
adaptive_processor = None

try:
    adaptive_manager, adaptive_processor = initialize_adaptive_system(
        llm=agent.llm,
        agent=agent,
        multihop_agent=multihop_agent,
        system_monitor=system_monitor,
        performance_tracker=performance_tracker
    )
    logger.info("Adaptive system initialized")
except Exception as e:
    logger.error(f"Failed to initialize adaptive system: {e}")
```

### 3. Endpoint hinzufügen

In `app.py` nach Zeile 768 (nach `/query` endpoint):

```python
from typing import Dict, Any

class AdaptiveQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    force_complexity: Optional[str] = None
    enable_escalation: bool = True

    @validator('query')
    def sanitize_query_input(cls, v):
        return sanitize_query(v)

class AdaptiveQueryResponse(BaseModel):
    answer: str
    confidence: Optional[float]
    strategy: Dict[str, Any]
    metadata: Dict[str, Any]
    steps: Optional[int] = None
    search_queries: Optional[List[str]] = None
    reasoning_path: Optional[List[str]] = None

@app.post("/query-adaptive", response_model=AdaptiveQueryResponse, dependencies=[Depends(check_rate_limit)])
async def query_adaptive_endpoint(request: AdaptiveQueryRequest):
    if not adaptive_processor:
        raise HTTPException(status_code=503, detail="Adaptive system not available")

    result = adaptive_processor.process_query(
        query=request.query,
        force_complexity=request.force_complexity,
        enable_escalation=request.enable_escalation
    )
    return AdaptiveQueryResponse(**result)
```

## Testen

### Option A: Demo-Skript ausführen

```bash
python examples/adaptive_demo.py
```

Zeigt alle Features: Komplexitäts-Analyse, Strategie-Entscheidungen, Eskalation, etc.

### Option B: API-Endpoint testen

1. Server starten:
```bash
python app.py
```

2. Request senden:
```bash
curl -X POST "http://localhost:8000/query-adaptive" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare AI in healthcare vs manufacturing",
    "enable_escalation": true
  }'
```

3. Response prüfen:
```json
{
  "answer": "...",
  "confidence": 0.85,
  "strategy": {
    "complexity": "high",
    "agent_type": "MultiHopReasoningAgent",
    "max_hops": 5,
    "reasoning": ["High complexity: MultiHop with 5 hops"]
  },
  "metadata": {
    "attempts": 1,
    "elapsed_time": 12.5,
    "escalation_history": []
  }
}
```

## Verwendungsbeispiele

### Einfache Query (LOW)
```bash
curl ... -d '{"query": "What is Python?"}'
# → SearchAgent, no tools, 0.8s
```

### Web-Search Query (MID)
```bash
curl ... -d '{"query": "Latest AI news 2025"}'
# → SearchAgent, web tools, 2.5s
```

### Komplexe Query (HIGH)
```bash
curl ... -d '{"query": "Compare X and Y, analyze trends, recommend best option"}'
# → MultiHopReasoningAgent, 5 hops, 15s
```

### Force Complexity
```bash
curl ... -d '{"query": "Simple question", "force_complexity": "high"}'
# → Zwingt MultiHopAgent auch für einfache Fragen
```

## Wie es funktioniert

```
Query → Complexity Analysis → Strategy Decision → Agent Execution
           │                        │
           ├─ LLM Classification    ├─ Resource Check
           ├─ Length Heuristic      ├─ Agent Selection
           └─ Keyword Detection     └─ Configuration

                    ↓ (wenn confidence < 0.5)

              Escalation Loop
              LOW → MID → HIGH
```

## Features

✅ **Automatische Komplexitätserkennung**
- LLM-basiert + Heuristiken
- 3 Stufen: LOW, MID, HIGH

✅ **Confidence-basierte Eskalation**
- Automatisches Upgrade bei niedriger Confidence
- Max 2 Eskalations-Versuche

✅ **Ressourcen-basierte Degradation**
- Bei hoher CPU/Memory: Downgrade Complexity
- Reduzierte Hops im Degraded Mode

✅ **Flexibles Configuration**
- Alle Schwellenwerte anpassbar
- Feature Toggles für Monitoring/Escalation

✅ **Detaillierte Metriken**
- Komplexitäts-Analyse
- Strategie-Reasoning
- Eskalations-Historie
- Ressourcen-Status

## Konfiguration anpassen

```python
from core.adaptive_hops import AdaptiveConfig

custom_config = AdaptiveConfig(
    max_hops_high=3,              # Reduziere High-Complexity Hops
    cpu_threshold_high=70.0,      # Strengeres CPU-Limit
    confidence_low=0.6,           # Höherer Eskalations-Schwellenwert
    enable_resource_monitoring=False  # Deaktiviere Monitoring
)

# Übergeben Sie custom_config bei der Initialisierung
```

## Nächste Schritte

1. **Lesen Sie die vollständige Dokumentation**: `ADAPTIVE_HOPS.md`
   - Architektur-Details
   - API-Referenz
   - Best Practices
   - Troubleshooting

2. **Experimentieren Sie mit dem Demo**: `python examples/adaptive_demo.py`

3. **Integrieren Sie in Ihre API**: Folgen Sie `examples/app_integration_example.py`

4. **Überwachen Sie in Produktion**: Logs und `/stats` Endpoint

## Vorteile

| Feature | Vorher | Mit Adaptive Hops |
|---------|--------|-------------------|
| Agent-Auswahl | Manuell (`use_multihop=true/false`) | Automatisch basierend auf Komplexität |
| Performance | Feste Strategie | Optimiert pro Query |
| Ressourcen | Keine Anpassung | Dynamische Degradation |
| Confidence | Nicht überwacht | Automatische Eskalation |
| Transparenz | Schwarz-Box | Detaillierte Strategy + Metadata |

## Support

- 📖 Vollständige Docs: `ADAPTIVE_HOPS.md`
- 💻 Integration Code: `examples/app_integration_example.py`
- 🧪 Demo: `examples/adaptive_demo.py`
- 🐛 Issues: GitHub Issues

---

**Happy Adaptive Hopping! 🚀**
