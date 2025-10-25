# LangGraph Multi-Hop Reasoning Guide

---

📚 **Navigation:** [🏠 Home](../README.md) | [📖 Docs](README.md) | [🚀 Quickstart](QUICKSTART.md) | [🔌 Plugins](PLUGIN_TUTORIAL.md) | [🔍 OSINT](OSINT_USAGE.md)

---

## Überblick

CrawlLama nutzt LangGraph für komplexe, mehrstufige Reasoning-Prozesse. Dieser Guide erklärt, wie das Multi-Hop-Reasoning-System funktioniert und wie man es nutzt.

## Architektur

### Reasoning-Graph

Der Multi-Hop-Agent verwendet einen StateGraph mit folgenden Nodes:

```
┌─────────┐
│ Router  │──┐
└─────────┘  │
             ▼
      ┌──────────────┐
      │Initial Search│
      └──────────────┘
             │
             ▼
        ┌─────────┐
        │ Analyze │◄──┐
        └─────────┘   │
             │        │
        ┌────┴────┐   │
        │         │   │
      Needs     Ready │
       more?      │   │
        │         │   │
        ▼         ▼   │
   ┌────────┐  ┌──────────┐
   │Follow-Up│  │Synthesize│
   └────────┘  └──────────┘
        │              │
        └──────────────┘
                       │
                       ▼
                  ┌─────────┐
                  │Critique │
                  └─────────┘
                       │
                   ┌───┴───┐
                   │       │
                 Good   Improve
                   │       │
                   ▼       │
                  END      └──► (zurück zu Follow-Up)
```

## Node-Beschreibungen

### 1. Router Node
**Zweck:** Klassifiziert Query-Komplexität

**Logik:**
- Analysiert die Eingabefrage
- Klassifiziert als EINFACH oder KOMPLEX
- EINFACH → direkte Beantwortung möglich
- KOMPLEX → benötigt mehrere Schritte

**Beispiele:**
- EINFACH: "Was ist Python?"
- KOMPLEX: "Vergleiche Python und JavaScript für Web-Entwicklung"

### 2. Initial Search Node
**Zweck:** Erste Informationssuche

**Prozess:**
1. Führt Web-Suche mit ursprünglicher Query durch
2. Sammelt initiale Informationen
3. Speichert Ergebnisse im Context

### 3. Analyze Node
**Zweck:** Bewertung der gesammelten Informationen

**Checks:**
1. Sind Informationen vollständig?
2. Welche Informationen fehlen?
3. Confidence-Score (0-100%)

**Entscheidung:**
```python
if vollständig and confidence >= threshold:
    → Synthesize
else if steps < max_hops:
    → Follow-Up
else:
    → Synthesize (mit vorhandenen Infos)
```

### 4. Follow-Up Node
**Zweck:** Gezielte Nachsuchen

**Prozess:**
1. LLM generiert spezifische Follow-Up-Query
2. Führt weitere Suche durch
3. Ergänzt Context
4. Zurück zu Analyze

**Beispiel:**
- Original: "Vergleiche Python und JavaScript"
- Follow-Up 1: "Python performance benchmarks"
- Follow-Up 2: "JavaScript modern features"

### 5. Synthesize Node
**Zweck:** Finale Antwort-Generierung

**Prozess:**
1. Kombiniert alle Context-Informationen
2. Strukturiert umfassende Antwort
3. Zitiert Quellen
4. Generiert kohärente Ausgabe

### 6. Critique Node (Optional)
**Zweck:** Self-Critique der generierten Antwort

**Bewertung:**
- Vollständigkeit
- Korrektheit
- Qualitätsscore

**Entscheidung:**
```python
if quality >= threshold:
    → END
else if steps < max_hops:
    → Follow-Up (für Verbesserung)
else:
    → END
```

## Verwendung

### Basic Usage

```python
from core.langgraph_agent import MultiHopReasoningAgent
import json

# Load config
config = json.load(open("config.json"))

# Initialize agent
agent = MultiHopReasoningAgent(
    config=config,
    max_hops=3,              # Max reasoning steps
    confidence_threshold=0.7, # Min confidence to stop
    enable_critique=True     # Enable self-critique
)

# Query
result = agent.query("Compare Python and JavaScript for web development")

# Result structure
print(result["answer"])           # Final answer
print(result["confidence"])        # Confidence score
print(result["steps"])             # Number of hops taken
print(result["search_queries"])    # Queries performed
print(result["reasoning_path"])    # Step-by-step reasoning
```

### Via CLI

```bash
# Enable multi-hop reasoning
python main.py --multihop "Complex question here"

# Custom max hops
python main.py --multihop --max-hops 5 "Your question"
```

### Via API

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare Python and JavaScript",
    "use_multihop": true,
    "max_hops": 3
  }'
```

## Konfiguration

### config.json

```json
{
  "llm": {
    "model": "qwen2.5:3b",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "multihop": {
    "enabled": true,
    "max_hops": 3,
    "confidence_threshold": 0.7,
    "enable_critique": true
  }
}
```

### Parameter-Tuning

**max_hops:**
- Niedrig (1-2): Schneller, weniger gründlich
- Mittel (3-4): Ausgewogen
- Hoch (5+): Sehr gründlich, langsamer

**confidence_threshold:**
- Niedrig (0.5-0.6): Stoppt früher
- Mittel (0.7-0.8): Empfohlen
- Hoch (0.9+): Sehr strikt, mehr Hops

**enable_critique:**
- `true`: Bessere Qualität, langsamer
- `false`: Schneller, keine Selbst-Prüfung

## Best Practices

### 1. Wann Multi-Hop verwenden?

✅ **Geeignet für:**
- Vergleichsfragen
- Multi-Aspekt-Analysen
- Recherche-intensive Fragen
- "Pros and Cons" Fragen

❌ **Nicht geeignet für:**
- Einfache Faktenfragen
- Definitionen
- Ja/Nein-Fragen

### 2. Performance-Optimierung

```python
# Für schnelle Antworten
agent = MultiHopReasoningAgent(
    config=config,
    max_hops=2,
    confidence_threshold=0.6,
    enable_critique=False
)

# Für maximale Qualität
agent = MultiHopReasoningAgent(
    config=config,
    max_hops=5,
    confidence_threshold=0.8,
    enable_critique=True
)
```

### 3. Monitoring

```python
result = agent.query("Your question")

# Log reasoning path
for i, step in enumerate(result["reasoning_path"], 1):
    print(f"Step {i}: {step}")

# Check if enough information was gathered
if result["steps"] == max_hops:
    print("Warning: Reached max hops, might need more information")
```

## Beispiele

### Beispiel 1: Technologie-Vergleich

```python
query = "Compare React and Vue.js for building SPAs"

result = agent.query(query)

# Reasoning path:
# 1. Router: Complex query detected
# 2. Initial search: "React vs Vue.js SPA"
# 3. Analyze: Need more details on performance
# 4. Follow-up: "React performance benchmarks"
# 5. Follow-up: "Vue.js modern features"
# 6. Synthesize: Comprehensive comparison
# 7. Critique: Quality check passed
```

### Beispiel 2: Pros/Cons-Analyse

```python
query = "What are the pros and cons of electric vehicles?"

result = agent.query(query)

# Expected hops: 2-3
# - Initial: General EV info
# - Follow-up 1: EV advantages
# - Follow-up 2: EV disadvantages
# - Synthesize: Balanced overview
```

## Troubleshooting

### Problem: Zu viele Hops

**Lösung:**
- Erhöhe `confidence_threshold`
- Reduziere `max_hops`
- Verbessere initiale Query-Formulierung

### Problem: Schlechte Antwortqualität

**Lösung:**
- Aktiviere `enable_critique`
- Erhöhe `max_hops`
- Senke `confidence_threshold`
- Verwende größeres LLM-Modell

### Problem: Lange Antwortzeiten

**Lösung:**
- Reduziere `max_hops`
- Deaktiviere `enable_critique`
- Nutze Caching
- Parallele Suchen aktivieren

## Erweiterte Features

### Custom Nodes hinzufügen

```python
# In langgraph_agent.py

def _custom_node(self, state: ReasoningState) -> ReasoningState:
    """Custom processing node."""
    # Your logic here
    return state

# Add to graph
workflow.add_node("custom", self._custom_node)
workflow.add_edge("analyze", "custom")
```

### State erweitern

```python
class CustomReasoningState(ReasoningState):
    """Extended state with custom fields."""
    custom_data: List[str]
    extra_metadata: Dict[str, Any]
```

## Weitere Ressourcen

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [CrawlLama API Docs](API_DOCS.md)
- [Performance Tuning Guide](PERFORMANCE.md)
