# Hallucination Detection & Quality Control

## Überblick

Das Hallucination Detection Modul (`core/hallu_detect.py`) bietet umfassende Qualitätskontrolle für LLM-generierte Inhalte durch automatische Erkennung von Halluzinationen, Faktenprüfung und Kontext-Alignment-Analyse.

---

## Features

### 1. **Multi-Level Hallucination Detection**
- **Pattern-basierte Erkennung**: Erkennt typische Halluzinations-Muster wie erfundene Zitate, widersprüchliche Aussagen
- **Kontext-Alignment**: Prüft, ob die Antwort mit dem gegebenen Kontext übereinstimmt
- **Faktenprüfung**: Externe Validierung gegen Wikipedia und optionale Web-Suche
- **Quality Scoring**: Bewertung von Antwortqualität basierend auf verschiedenen Metriken

### 2. **Konfigurierbare Sensitivität**
- **Detection Level**: `low`, `medium`, `high` für verschiedene Anwendungsfälle
- **Anpassbare Schwellwerte**: Feinabstimmung für spezifische Anforderungen
- **Selektive Features**: Ein-/Ausschalten einzelner Prüfungen

### 3. **Integration in LLM Client**
- **Automatische Prüfung**: Jede LLM-Antwort wird optional geprüft
- **Warning Modes**: `silent`, `log`, `flag_response`, `block`
- **Performance-optimiert**: Konfigurierbare Timeouts und Caching

---

## Konfiguration

### Config.json Einstellungen

```json
{
  "hallucination_detection": {
    "enabled": false,
    "detection_level": "medium",
    "hallucination_threshold": 0.7,
    "context_alignment_threshold": 0.4,
    "fact_confidence_threshold": 0.6,
    "fact_checking_enabled": true,
    "context_analysis_enabled": true,
    "max_processing_time": 10.0,
    "cache_enabled": true,
    "batch_size": 5,
    "warning_mode": "flag_response",
    "fact_checker": {
      "wikipedia_check": true,
      "web_search_check": false,
      "min_claim_length": 10
    },
    "context_analyzer": {
      "min_context_overlap": 0.3,
      "contradiction_threshold": 0.7
    }
  }
}
```

### Parameter-Erklärung

| Parameter | Beschreibung | Werte | Standard |
|-----------|-------------|-------|----------|
| `enabled` | Aktiviert/deaktiviert die Erkennung | `true`/`false` | `false` |
| `detection_level` | Sensitivitätslevel | `low`/`medium`/`high` | `medium` |
| `hallucination_threshold` | Schwellwert für Halluzination (0-1) | `0.0-1.0` | `0.7` |
| `context_alignment_threshold` | Min. Kontext-Übereinstimmung | `0.0-1.0` | `0.4` |
| `fact_confidence_threshold` | Min. Fakten-Vertrauen | `0.0-1.0` | `0.6` |
| `warning_mode` | Wie Warnungen angezeigt werden | siehe unten | `flag_response` |
| `max_processing_time` | Max. Verarbeitungszeit (Sekunden) | Zahl | `10.0` |

### Warning Modes

- **`silent`**: Keine Benutzer-Warnungen, nur Logging
- **`log`**: Warnungen in Logs, keine Antwort-Modifikation
- **`flag_response`**: Warnung wird an Antwort angehängt
- **`block`**: Antwort wird bei hohem Risiko blockiert

---

## Verwendung

### 1. **Direkte API-Nutzung**

```python
from core.hallu_detect import detect_hallucination

# Einfache Prüfung
result = detect_hallucination(
    response="Paris is the capital of Germany.",
    context="What is the capital of France?"
)

print(f"Hallucination: {result.is_hallucination}")
print(f"Confidence: {result.confidence_score:.2f}")
print(f"Risk Level: {result.risk_level}")
```

### 2. **LLM Client Integration**

```python
from core.llm_client import OllamaClient

# Hallucination Detection aktivieren
hallu_config = {
    "enabled": True,
    "detection_level": "medium",
    "warning_mode": "flag_response"
}

client = OllamaClient(hallu_config=hallu_config)

# Normale Generierung mit automatischer Prüfung
response = client.generate("Tell me about quantum computing")
# Response enthält automatisch Qualitätswarnung bei Problemen
```

### 3. **Erweiterte Konfiguration**

```python
from core.hallu_detect import create_detector

# Custom Detector erstellen
config = {
    "enabled": True,
    "detection_level": "high",
    "hallucination_threshold": 0.5,  # Sensitiver
    "fact_checking_enabled": True,
    "context_analysis_enabled": True,
    "fact_checker": {
        "wikipedia_check": True,
        "web_search_check": True  # Web-Suche aktivieren
    }
}

detector = create_detector(config)
result = detector.detect(response, context)

# Detaillierte Analyse
for violation in result.violations:
    print(f"Violation: {violation['type']} ({violation['severity']})")

for fact_check in result.fact_check_results:
    print(f"Fact: {fact_check['claim']} - Verified: {fact_check['verified']}")
```

---

## Detection-Mechanismen

### 1. **Pattern-basierte Erkennung**

**Erfundene Zitate/Referenzen:**
```
✗ "According to a 2023 study by..."
✗ "Research shows that..."
✗ "[Citation needed]"
```

**Interne Widersprüche:**
```
✗ "X is always true" + "X is never true"
✗ "This can be done" + "This cannot be done"
```

**Ungestützte spezifische Informationen:**
```
✗ Exakte Zahlen/Zeiten ohne Kontext-Support
✗ Spezifische Preise, Prozentsätze, Daten
```

### 2. **Kontext-Alignment**

- **Coverage**: Wie viele Kontext-Konzepte werden adressiert?
- **Relevanz**: Bleibt die Antwort beim Thema?
- **Widersprüche**: Widerspricht die Antwort dem Kontext?

### 3. **Faktenprüfung**

**Wikipedia Integration:**
- Automatische Suche nach Schlüsselbegriffen
- Similarity-Matching gegen Wikipedia-Inhalte
- Konfidenz-Bewertung basierend auf Übereinstimmung

**Zukünftige Erweiterungen:**
- Google Fact Check API
- Snopes Integration
- Custom Knowledge Bases

---

## Qualitäts-Metriken

### Result-Objekt

```python
@dataclass
class HallucinationResult:
    is_hallucination: bool          # Hauptergebnis
    confidence_score: float         # 0.0-1.0
    risk_level: str                 # "low"/"medium"/"high"
    violations: List[Dict]          # Gefundene Probleme
    context_alignment: float        # Kontext-Übereinstimmung
    fact_check_results: List[Dict]  # Faktenprüfung-Ergebnisse
    quality_metrics: Dict           # Zusätzliche Metriken
    processing_time: float          # Verarbeitungszeit
```

### Quality Metrics

- **`response_length`**: Antwortlänge
- **`repetition_score`**: Wiederholungsrate (0-1)
- **`vague_language_score`**: Anteil vager Sprache
- **`sentence_count`**: Anzahl Sätze
- **`context_alignment`**: Kontext-Übereinstimmung

---

## Performance & Limits

### **Geschwindigkeits-Optimierung**

- **Caching**: Wikipedia-Abfragen werden gecacht
- **Timeouts**: Konfigurierbare Max-Verarbeitungszeit
- **Batch Processing**: Effiziente Verarbeitung mehrerer Claims
- **Lazy Loading**: Components werden nur bei Bedarf geladen

### **Rate Limiting**

- **Wikipedia**: ~10 Abfragen/Sekunde (respektiert API-Limits)
- **Web Search**: Konfigurierbar je nach Anbieter
- **Lokale Checks**: Keine Limits

### **Speicherverbrauch**

- **Cache**: ~50MB für Wikipedia-Cache (konfigurierbar)
- **Models**: Keine zusätzlichen ML-Modelle erforderlich
- **Memory**: <100MB zusätzlicher RAM-Verbrauch

---

## Testing & Validierung

### Unit Tests

```bash
# Hallucination Detection Tests
python tests/test_hallucination_detection.py

# Integration in Test Suite
pytest tests/test_hallucination_detection.py -v

# Performance Tests
python -m pytest tests/ -k hallucination --benchmark
```

### Test Cases

Das Modul wird mit verschiedenen Test-Szenarien validiert:

1. **Normal Responses**: Korrekte Antworten ohne Probleme
2. **Fabricated Citations**: Erfundene Quellen und Studien
3. **Context Misalignment**: Antworten ohne Bezug zum Kontext
4. **Internal Contradictions**: Widersprüchliche Aussagen
5. **Unsupported Specifics**: Nicht belegbare spezifische Angaben

### Monitoring

```python
# Statistiken abrufen
detector = get_detector()
stats = detector.get_statistics()

print(f"Total checks: {stats['total_checks']}")
print(f"Hallucinations detected: {stats['hallucinations_detected']}")
print(f"Detection rate: {stats['hallucinations_detected']/stats['total_checks']*100:.1f}%")
print(f"Avg processing time: {stats['avg_processing_time']:.3f}s")
```

---

## Troubleshooting

### Häufige Probleme

1. **Zu viele False Positives**
   - Lösung: `detection_level` auf `low` setzen
   - Schwellwerte erhöhen: `hallucination_threshold: 0.8+`

2. **Zu langsame Performance**
   - `fact_checking_enabled: false` für lokale Tests
   - `max_processing_time` reduzieren
   - `wikipedia_check: false` bei Netzwerkproblemen

3. **Wikipedia API Errors**
   - Rate Limiting: Automatische Delays
   - Fallback: Lokale Pattern-Erkennung funktioniert weiter

4. **Memory Issues**
   - `cache_enabled: false` deaktiviert Caching
   - `batch_size` reduzieren für weniger RAM-Verbrauch

### Debug-Modus

```python
import logging
logging.getLogger("crawllama").setLevel(logging.DEBUG)

# Detaillierte Logs für Hallucination Detection
result = detector.detect(response, context)
```

---

## Roadmap & Erweiterungen

### Geplante Features (v1.5+)

- **ML-basierte Detection**: Training eigener Hallucinations-Classifier
- **Multi-Language Support**: Unterstützung für andere Sprachen
- **Custom Knowledge Bases**: Integration eigener Fact-Check-Quellen
- **Real-time Monitoring**: Live-Dashboard für Qualitäts-Metriken
- **A/B Testing**: Vergleich verschiedener Detection-Strategien

### API-Erweiterungen

- **Batch Processing**: Effiziente Verarbeitung vieler Antworten
- **Webhook Integration**: Automatische Benachrichtigungen
- **Export Funktionen**: Reports als PDF/Excel
- **Fine-tuning Interface**: GUI für Schwellwert-Anpassungen

---

## Best Practices

### Produktionsumgebung

1. **Gradueller Rollout**: Starte mit `detection_level: "low"`
2. **Monitoring**: Überwache Detection-Rate und Performance
3. **Feedback Loop**: Sammle User-Feedback für False Positives
4. **Thresholds anpassen**: Optimiere Schwellwerte basierend auf Use Case

### Development

1. **Testing**: Verwende diverse Test Cases
2. **Logging**: Aktiviere Debug-Logs während Entwicklung
3. **Caching**: Nutze lokalen Cache für schnellere Tests
4. **Profiling**: Messe Performance-Impact

### Compliance

1. **Privacy**: Wikipedia-Abfragen enthalten keine User-Daten
2. **Rate Limits**: Respektiere API-Limits aller Services
3. **Logging**: Alle Prüfungen werden für Audit protokolliert
4. **Konfigurierbar**: Features können vollständig deaktiviert werden

---

Das Hallucination Detection Modul bietet eine robuste, konfigurierbare Lösung für LLM-Quality-Control mit minimaler Performance-Impact und maximaler Flexibilität! 🛡️✨