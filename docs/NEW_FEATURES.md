# Neue Features - CrawlLama

## Übersicht

Dieses Dokument beschreibt die neu implementierten Features für CrawlLama im Rahmen der Phase 2 (Robustheit) der Entwicklungs-Roadmap.

---

## 🔐 Sicherheit & Konfiguration

### 1. Sicheres API-Key Management (`utils/secure_config.py`)

**Features:**
- Verschlüsselte Speicherung von API-Keys mit Fernet-Kryptographie
- Interaktives Setup-Tool für API-Keys
- Unterstützung für multiple API-Provider (Serper, Brave, OpenAI)

**Verwendung:**
```bash
# Interaktives Setup
python main.py --setup-keys

# Programmatisch
from utils.secure_config import SecureConfig

config = SecureConfig()
config.set_api_key("SERPER_API_KEY", "your-key", encrypt=True)
api_key = config.get_api_key("SERPER_API_KEY", encrypted=True)
```

**Features:**
- Automatische Verschlüsselungs-Key-Generierung
- Validierung aller konfigurierten Keys
- Sichere .env-Integration

---

## 🌐 Netzwerk & Proxy

### 2. Proxy-Validierung (`utils/proxy_validator.py`)

**Features:**
- Automatische Proxy-Konfiguration aus Umgebungsvariablen
- Validierung der Proxy-Verbindungen beim Start
- NO_PROXY Liste für Ausnahmen
- Integration in startup_check

**Verwendung:**
```bash
# Umgebungsvariablen setzen
export HTTP_PROXY="http://proxy.example.com:8080"
export HTTPS_PROXY="https://proxy.example.com:8443"
export NO_PROXY="localhost,127.0.0.1,.local"

# Automatische Validierung beim Start
python main.py
```

**Programmatisch:**
```python
from utils.proxy_validator import ProxyValidator

validator = ProxyValidator.load_from_env()
results = validator.validate_proxies()
proxies = validator.get_proxies()
```

---

## 🛡️ Rate Limiting & Compliance

### 3. Rate Limiter mit robots.txt Support (`utils/rate_limiter.py`)

**Features:**
- Per-Domain Rate Limiting (Standard: 1 Request/Sekunde)
- Automatische robots.txt Compliance
- Crawl-Delay Unterstützung
- Thread-Safe Implementation

**Komponenten:**

#### RateLimiter
```python
from utils.rate_limiter import RateLimiter

limiter = RateLimiter(requests_per_second=2.0)
limiter.wait("example.com")  # Wartet falls nötig
```

#### RobotsChecker
```python
from utils.rate_limiter import RobotsChecker

checker = RobotsChecker(user_agent="CrawlLama/1.0")
if checker.can_fetch("https://example.com/page"):
    # Fetch erlaubt
    pass
```

#### RequestThrottler (Kombination)
```python
from utils.rate_limiter import RequestThrottler

throttler = RequestThrottler(
    requests_per_second=1.0,
    respect_robots=True
)
response = throttler.throttled_request("https://example.com")
```

---

## 🚫 Domain Blacklist

### 4. URL-Filterung (`utils/domain_blacklist.py`)

**Features:**
- Vordefinierte Blacklist-Kategorien (Malware, Spam, Tracking)
- Regex-basierte Pattern-Matching
- Custom Blacklist-Support
- Laden/Speichern von Blacklist-Dateien

**Kategorien:**
- **Malware**: .tk, .ml, .ga, .cf, .gq Domains
- **Spam**: Casino, Pharma, Viagra, Lottery Sites
- **Tracking**: Doubleclick, Google Analytics, Facebook Tracking

**Verwendung:**
```python
from utils.domain_blacklist import DomainBlacklist, is_safe_url

# Globale Prüfung
if is_safe_url("https://example.com"):
    # URL ist sicher
    pass

# Custom Blacklist
blacklist = DomainBlacklist(
    categories=["malware", "spam"],
    custom_blacklist=[r".*badsite\.com$"]
)

# URLs filtern
safe_urls = blacklist.filter_urls(url_list)
```

---

## 🔄 Fallback-System

### 5. Fallback Manager (`core/fallback_manager.py`)

**Features:**
- Automatisches Fallback bei Tool-Fehlern
- Cache-Integration
- Statistiken über Success/Failure Rates
- Decorator-Support

**Verwendung:**
```python
from core.fallback_manager import FallbackManager

manager = FallbackManager()

# Strategie registrieren
manager.register(
    name="web_search",
    primary_func=duckduckgo_search,
    fallback_funcs=[brave_search, serper_search],
    cache_func=cache_search
)

# Ausführen mit automatischem Fallback
results = manager.execute("web_search", query="test")

# Statistiken
stats = manager.get_stats()
```

**Decorator:**
```python
@manager.with_fallback("web_search")
def search(query: str):
    return query

results = search("test")  # Nutzt automatisch Fallbacks
```

---

## 🔒 Safe Fetch

### 6. Sicherer HTTP Client (`utils/safe_fetch.py`)

**Features:**
- Kombiniert alle Sicherheitsfeatures
- Rate Limiting
- robots.txt Compliance
- Domain Blacklist
- Proxy-Support
- Retry-Logik

**Verwendung:**
```python
from utils.safe_fetch import SafeFetcher, safe_get

# Einfache Verwendung
response = safe_get("https://example.com")

# Erweiterte Konfiguration
fetcher = SafeFetcher(
    use_rate_limiting=True,
    use_blacklist=True,
    use_robots=True,
    use_proxy=True
)

response = fetcher.get("https://example.com")
```

---

## 🔍 Erweiterte Web-Suche

### 7. Multi-Provider Search (`tools/web_search.py`)

**Neue Features:**
- Brave Search API Integration
- Serper API Integration (Google Search)
- Automatisches Fallback zwischen Providern
- URL-Filterung mit Blacklist

**Verwendung:**
```python
from tools.web_search import search_with_fallback

# Automatisches Fallback: DuckDuckGo -> Brave -> Serper
results = search_with_fallback("Python programming", max_results=5)
```

**Provider-Konfiguration:**
```bash
# .env Datei
BRAVE_API_KEY=your_brave_api_key
SERPER_API_KEY=your_serper_api_key
```

---

## 📊 Integration

### Zusammenspiel der Komponenten

```
Benutzer-Anfrage
    ↓
[SearchAgent]
    ↓
[FallbackManager] → [web_search]
    ↓                   ↓
    |              [DuckDuckGo]
    |                   ↓ (bei Fehler)
    |              [Brave Search]
    |                   ↓ (bei Fehler)
    |              [Serper API]
    ↓
[Domain Blacklist] → URLs filtern
    ↓
[SafeFetcher]
    ↓
[Rate Limiter] → Wartet falls nötig
    ↓
[RobotsChecker] → Prüft robots.txt
    ↓
[ProxyValidator] → Nutzt Proxy falls konfiguriert
    ↓
[Retry Logic] → Versucht erneut bei Fehlern
    ↓
Erfolgreiche Response
```

---

## 🧪 Tests

Alle neuen Features sind mit Unit-Tests abgedeckt:

- `tests/test_fallback_manager.py` - FallbackManager Tests
- `tests/test_rate_limiter.py` - RateLimiter & RobotsChecker Tests
- `tests/test_domain_blacklist.py` - Blacklist Tests
- `tests/test_safe_fetch.py` - SafeFetcher Tests

**Tests ausführen:**
```bash
# Alle Tests
pytest tests/

# Spezifische Tests
pytest tests/test_fallback_manager.py -v

# Mit Coverage
pytest --cov=utils --cov=core tests/
```

---

## ⚙️ Konfiguration

### Empfohlene Einstellungen

**Für Entwicklung:**
```python
# config.json
{
  "rate_limiting": {
    "enabled": true,
    "requests_per_second": 2.0
  },
  "security": {
    "respect_robots": true,
    "use_blacklist": true,
    "use_proxy": false
  }
}
```

**Für Produktion:**
```python
{
  "rate_limiting": {
    "enabled": true,
    "requests_per_second": 1.0
  },
  "security": {
    "respect_robots": true,
    "use_blacklist": true,
    "use_proxy": true
  }
}
```

---

## 📝 Checkliste-Status

### Vorbereitung
- ✅ API-Keys sichern
- ✅ Proxy validieren

### Phase 2: Robustheit
- ✅ Fallback-System integrieren
- ✅ Retry-Logik anwenden
- ✅ Proxy & Rate-Limiting
- ✅ Blacklist einrichten
- ✅ Tests erweitern
- ✅ Offline-Modus ausbauen
- ⏳ Fehler simulieren

---

## 🚀 Nächste Schritte

1. **Manuelle Tests durchführen**
   - Test mit verschiedenen Suchmaschinen
   - Rate Limiting überprüfen
   - Fallback-Verhalten testen

2. **Error Simulation**
   - API-Ausfälle simulieren
   - Out-of-Memory Szenarien testen
   - Netzwerk-Timeouts prüfen

3. **Phase 3: Intelligence**
   - RAG optimieren
   - Multi-Hop-Reasoning implementieren
   - Parallelisierung

---

## 📚 Weitere Dokumentation

- [README.md](../README.md) - Hauptdokumentation
- [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) - Technische Details
- [checklist.txt](checklist.txt) - Entwicklungs-Roadmap

---

**Letzte Aktualisierung:** 2025-10-23
