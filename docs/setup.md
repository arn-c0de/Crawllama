# Projekt: Lokaler Such- und Antwort-Agent mit Ollama

## Übersicht

Ein vollständig **lokales KI-System**, das im Terminal läuft und Benutzeranfragen intelligent beantwortet. Das System kombiniert:
- **Ollama** (lokales LLM) für Textverstehen und Antwortgenerierung
- **Autonome Web-Recherche** mit strukturierten Tool-Calls
- **RAG (Retrieval-Augmented Generation)** für kontextbasierte Antworten
- **Modulare Architektur** für einfache Erweiterbarkeit

**Kernprinzipien:**
- Keine Cloud-Abhängigkeit
- Datenschutz durch lokale Verarbeitung
- Modular und erweiterbar
- Robuste Fehlerbehandlung

---

## Systemarchitektur

```text
┌─────────────────────────────────────────────────────┐
│                 User (Terminal/CLI)                 │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│            Controller / Agent Script                │
│  ┌──────────────────────────────────────────────┐  │
│  │  Tool Manager (LangChain/LangGraph)          │  │
│  │  - web_search    - wiki_lookup               │  │
│  │  - read_page     - rag_search                │  │
│  └──────────────────────────────────────────────┘  │
│                       ↓                             │
│  ┌──────────────────────────────────────────────┐  │
│  │  Ollama LLM (llama3/mistral/phi-3)           │  │
│  │  - Strukturierte Tool-Calls (JSON)           │  │
│  │  - Streaming Output                          │  │
│  └──────────────────────────────────────────────┘  │
│                       ↓                             │
│  ┌──────────────────────────────────────────────┐  │
│  │  RAG Module (ChromaDB + Embeddings)          │  │
│  │  - Semantische Suche                         │  │
│  │  - Kontext-Ranking                           │  │
│  └──────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  Cache & Storage (JSON/SQLite)                      │
│  - Suchergebnisse  - Webseiteninhalt                │
│  - Chat-History    - Embeddings                     │
└─────────────────────────────────────────────────────┘
```

---

## Projektstruktur (Erweitert)

```
crawllama/
│
├── main.py                    # Haupteinstiegspunkt (CLI)
├── config.json                # Konfiguration (API-Keys, Modell, etc.)
├── requirements.txt           # Python-Abhängigkeiten
├── .env.example               # Beispiel für Umgebungsvariablen
├── setup.md                   # Dieses Dokument
├── README.md                  # Benutzer-Dokumentation
│
├── core/                      # Kernlogik
│   ├── __init__.py
│   ├── agent.py               # Hauptagent (Tool-Orchestrierung)
│   ├── llm_client.py          # Ollama-Client mit Streaming
│   ├── context_manager.py     # Token-Limits, Kontext-Verwaltung
│   └── cache.py               # Cache-Manager (JSON/Shelve)
│
├── tools/                     # Modulare Tools
│   ├── __init__.py
│   ├── web_search.py          # Web-Suche (DuckDuckGo/Brave/Serper)
│   ├── page_reader.py         # HTML → Text Extraktion
│   ├── wiki_lookup.py         # Wikipedia-Spezialsuche
│   ├── rag.py                 # RAG-Modul (ChromaDB)
│   └── tool_registry.py       # Tool-Definition für LangChain
│
├── utils/                     # Hilfsfunktionen
│   ├── __init__.py
│   ├── retry.py               # Retry-Logik für Requests
│   ├── text_cleaner.py        # HTML-Cleaning, Token-Truncation
│   ├── logger.py              # Strukturiertes Logging
│   └── validators.py          # Input-Validierung, Sicherheit
│
├── data/                      # Daten & Cache
│   ├── cache/                 # Web-Cache (JSON-Dateien)
│   ├── embeddings/            # ChromaDB-Persistenz
│   └── history/               # Chat-Verlauf (optional)
│
├── logs/                      # Log-Dateien
│   └── app.log                # Automatisch generiert
│
└── tests/                     # Unit-Tests
    ├── __init__.py
    ├── test_web_search.py
    ├── test_rag.py
    ├── test_llm_client.py
    └── test_integration.py
```

---

## Hauptkomponenten

| Modul | Aufgabe | Implementierung |
|-------|---------|-----------------|
| **LLM-Backend** | Textverstehen, Antwortgenerierung | Ollama (llama3, mistral, phi-3) |
| **Agent Controller** | Tool-Orchestrierung, Dialoglogik | LangChain/LangGraph |
| **Web-Suche** | Suchergebnisse finden | `duckduckgo-search` (Fallback: Brave/Serper API) |
| **HTML-Parser** | Webseiten → Text | BeautifulSoup4 (nur `<p>`, `<h1-h6>`, `<li>`) |
| **RAG-Modul** | Semantische Suche in Dokumenten | ChromaDB + Ollama Embeddings |
| **Cache** | Vermeidung redundanter Requests | JSON/Shelve mit TTL |
| **Context Manager** | Token-Limits (< 4k Tokens) | Internes Modul mit Chunking |
| **CLI** | Terminal-Interface | `argparse` + `rich` für formatierte Ausgabe |
| **Logging** | Fehlerdiagnose | `logging` mit Rotation |

---

## Technische Abhängigkeiten

### requirements.txt

```txt
# Core
requests>=2.31.0
beautifulsoup4>=4.12.0
html5lib>=1.1

# Ollama & LLM
langchain>=0.1.0
langchain-community>=0.0.20
langgraph>=0.0.20

# Web-Suche
duckduckgo-search>=4.0.0

# RAG & Embeddings
chromadb>=0.4.0
sentence-transformers>=2.2.0  # Optional für bessere Embeddings

# Retry & Robustheit
tenacity>=8.2.0

# CLI & UI
rich>=13.0.0
python-dotenv>=1.0.0

# Testing
pytest>=7.4.0
pytest-mock>=3.12.0
pytest-cov>=4.1.0

# Optionale APIs
# brave-search>=0.1.0
# google-serper>=0.1.0
```

### Installation

```bash
# Python 3.10+ erforderlich
pip install -r requirements.txt

# Ollama installieren (falls nicht vorhanden)
# https://ollama.ai/download

# Modell herunterladen
ollama pull llama3:7b
# oder für bessere Logik:
ollama pull mistral:7b
ollama pull phi3:14b
```

---

## Konfiguration

### config.json

```json
{
  "llm": {
    "provider": "ollama",
    "base_url": "http://127.0.0.1:11434",
    "model": "llama3:7b",
    "temperature": 0.7,
    "max_tokens": 4096,
    "stream": true
  },
  "search": {
    "provider": "duckduckgo",
    "max_results": 3,
    "timeout": 10,
    "fallback_providers": ["brave", "serper"]
  },
  "rag": {
    "enabled": true,
    "embedding_model": "nomic-embed-text",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "top_k": 5
  },
  "cache": {
    "enabled": true,
    "ttl_hours": 24,
    "storage": "json"
  },
  "security": {
    "warn_external_requests": true,
    "allowed_domains": [],
    "max_context_length": 8000
  },
  "logging": {
    "level": "INFO",
    "file": "logs/app.log",
    "format": "json"
  }
}
```

### .env.example

```bash
# Optionale API-Keys (falls nicht DuckDuckGo)
BRAVE_API_KEY=your_key_here
SERPER_API_KEY=your_key_here

# Proxy (für Anonymisierung)
HTTP_PROXY=
HTTPS_PROXY=

# Entwicklungsmodus
DEBUG=false
```

---

## Implementierungsdetails

### 1. Fehlerbehandlung & Robustheit

**Datei:** `utils/retry.py`

```python
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def fetch_with_retry(url: str, timeout: int = 10) -> str:
    """HTTP-Request mit automatischer Retry-Logik"""
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logging.error(f"Request failed: {url} - {e}")
        raise
```

**Offline-Modus:**
```bash
python main.py --no-web "Erkläre Quantenverschränkung"
```

**Fehler-Logging:**
- Alle HTTP-Fehler → `logs/app.log`
- Strukturiertes JSON-Format mit Stack-Traces

---

### 2. Web-Suche & -Parsing

**Datei:** `tools/web_search.py`

```python
from duckduckgo_search import DDGS
from typing import List, Dict

def web_search(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """
    Suche mit duckduckgo-search Bibliothek (kein HTML-Scraping)
    Fallback auf Brave/Serper bei Fehler
    """
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r["title"],
                    "url": r["link"],
                    "snippet": r["body"]
                })
        return results
    except Exception as e:
        logging.warning(f"DuckDuckGo failed, trying fallback: {e}")
        return _fallback_search(query, max_results)
```

**Datei:** `tools/page_reader.py`

```python
from bs4 import BeautifulSoup
import re

def extract_text(html: str, max_length: int = 3000) -> str:
    """
    Extrahiere nur relevante Textinhalte (Überschriften, Absätze, Listen)
    Entferne Scripts, Styles, Navigation
    """
    soup = BeautifulSoup(html, "html5lib")

    # Entferne irrelevante Tags
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # Extrahiere nur relevante Elemente
    texts = []
    for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        text = tag.get_text(strip=True)
        if len(text) > 20:  # Mindestlänge
            texts.append(text)

    # Kombiniere und kürze
    combined = "\n".join(texts)
    return combined[:max_length]
```

---

### 3. Prompt-Engineering & Tool-Calls

**Datei:** `core/agent.py`

```python
from langchain.agents import AgentExecutor, create_structured_chat_agent
from langchain.tools import Tool
from langchain_community.llms import Ollama

# Tool-Definitionen
tools = [
    Tool(
        name="web_search",
        func=web_search,
        description="Suche im Web nach aktuellen Informationen. Input: Suchquery als String"
    ),
    Tool(
        name="read_page",
        func=read_page,
        description="Lese Inhalt einer Webseite. Input: URL als String"
    ),
    Tool(
        name="rag_search",
        func=rag_search,
        description="Suche in lokalen Dokumenten mit semantischer Ähnlichkeit"
    )
]

# System-Prompt für strukturierte Tool-Calls
system_prompt = """Du bist ein hilfreicher Assistent mit Zugriff auf Web-Suche.

Verfügbare Tools:
{tools}

Verwende Tools IMMER in diesem JSON-Format:
{{"action": "tool_name", "action_input": "parameter"}}

Beispiel:
Frage: "Was ist die aktuelle Temperatur in Berlin?"
Gedanke: Ich brauche aktuelle Wetterdaten
Aktion: {{"action": "web_search", "action_input": "Temperatur Berlin aktuell"}}
"""

llm = Ollama(model="llama3:7b", base_url="http://127.0.0.1:11434")
agent = create_structured_chat_agent(llm, tools, system_prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
```

---

### 4. Caching

**Datei:** `core/cache.py`

```python
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

class CacheManager:
    def __init__(self, cache_dir: str = "data/cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)

    def _get_key(self, identifier: str) -> str:
        """Erstelle Hash-Key für Cache-Datei"""
        return hashlib.md5(identifier.encode()).hexdigest()

    def get(self, key: str) -> dict | None:
        """Lade aus Cache wenn nicht abgelaufen"""
        cache_file = self.cache_dir / f"{self._get_key(key)}.json"

        if not cache_file.exists():
            return None

        with open(cache_file) as f:
            data = json.load(f)

        # Prüfe TTL
        cached_time = datetime.fromisoformat(data["timestamp"])
        if datetime.now() - cached_time > self.ttl:
            cache_file.unlink()  # Abgelaufen → lösche
            return None

        return data["content"]

    def set(self, key: str, content: dict):
        """Speichere in Cache"""
        cache_file = self.cache_dir / f"{self._get_key(key)}.json"

        with open(cache_file, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "content": content
            }, f)
```

---

### 5. RAG-Modul (Semantische Suche)

**Datei:** `tools/rag.py`

```python
import chromadb
from chromadb.config import Settings
from typing import List

class RAGManager:
    def __init__(self, persist_dir: str = "data/embeddings"):
        self.client = chromadb.Client(Settings(
            persist_directory=persist_dir,
            anonymized_telemetry=False
        ))
        self.collection = self.client.get_or_create_collection("web_documents")

    def add_documents(self, texts: List[str], metadatas: List[dict]):
        """Füge Dokumente mit Embeddings hinzu"""
        ids = [f"doc_{i}" for i in range(len(texts))]
        self.collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """Semantische Suche nach relevanten Dokumenten"""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )

        return [{
            "text": doc,
            "metadata": meta,
            "distance": dist
        } for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )]
```

---

### 6. Sicherheit

**Datei:** `utils/validators.py`

```python
import re
from urllib.parse import urlparse

DANGEROUS_PATTERNS = [
    r"eval\(",
    r"exec\(",
    r"__import__",
    r"<script",
]

def is_safe_url(url: str, allowed_domains: List[str] = []) -> bool:
    """Prüfe URL auf Sicherheit"""
    parsed = urlparse(url)

    # Nur HTTP/HTTPS
    if parsed.scheme not in ["http", "https"]:
        return False

    # Whitelist-Check (wenn konfiguriert)
    if allowed_domains and parsed.netloc not in allowed_domains:
        logging.warning(f"Domain nicht in Whitelist: {parsed.netloc}")
        return False

    return True

def sanitize_llm_output(text: str) -> str:
    """Entferne potenziell gefährliche Muster"""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            raise ValueError(f"Gefährliches Muster erkannt: {pattern}")
    return text
```

**Warnung bei externen Requests:**
```python
if config["security"]["warn_external_requests"]:
    print(f"⚠️  Externer Request: {url}")
    if input("Fortfahren? [y/N]: ").lower() != "y":
        return None
```

---

### 7. Performance & Effizienz

**Token-Limit-Management:**

```python
# core/context_manager.py
import tiktoken

class ContextManager:
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
        self.encoder = tiktoken.get_encoding("cl100k_base")

    def truncate(self, text: str) -> str:
        """Kürze Text auf Token-Limit"""
        tokens = self.encoder.encode(text)
        if len(tokens) > self.max_tokens:
            tokens = tokens[:self.max_tokens]
            text = self.encoder.decode(tokens)
        return text
```

**Streaming-Output:**

```python
# core/llm_client.py
def stream_response(prompt: str):
    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={"model": "llama3:7b", "prompt": prompt, "stream": True},
        stream=True
    )

    for line in response.iter_lines():
        if line:
            chunk = json.loads(line)
            if "response" in chunk:
                print(chunk["response"], end="", flush=True)
```

---

### 8. CLI-Interface

**Datei:** `main.py`

```python
import argparse
from rich.console import Console
from rich.markdown import Markdown

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Lokaler Such- und Antwort-Agent")
    parser.add_argument("query", nargs="*", help="Direkte Frage (optional)")
    parser.add_argument("--no-web", action="store_true", help="Offline-Modus")
    parser.add_argument("--model", default="llama3:7b", help="Ollama-Modell")
    parser.add_argument("--debug", action="store_true", help="Debug-Modus")

    args = parser.parse_args()

    # Initialisierung
    agent = SearchAgent(
        model=args.model,
        enable_web=not args.no_web,
        debug=args.debug
    )

    # Direkte Frage oder interaktiv
    if args.query:
        response = agent.query(" ".join(args.query))
        console.print(Markdown(response))
    else:
        # Interaktiver Modus
        while True:
            query = console.input("[bold cyan]❯[/] ")
            if query.lower() in ["exit", "quit"]:
                break

            response = agent.query(query)
            console.print(Markdown(response))

if __name__ == "__main__":
    main()
```

**Verwendung:**

```bash
# Interaktiv
python main.py

# Direkte Frage
python main.py "Was ist die Hauptstadt von Deutschland?"

# Offline-Modus
python main.py --no-web "Erkläre Photosynthese"

# Anderes Modell
python main.py --model mistral:7b "Wer hat Python erfunden?"
```

---

## Testen & Evaluation

### Unit-Tests

```bash
# Alle Tests
pytest tests/

# Mit Coverage
pytest --cov=core --cov=tools tests/

# Spezifischer Test
pytest tests/test_web_search.py -v
```

**Beispiel-Test:**

```python
# tests/test_web_search.py
import pytest
from tools.web_search import web_search

def test_web_search_returns_results():
    results = web_search("Python programming", max_results=3)
    assert len(results) <= 3
    assert all("url" in r for r in results)
    assert all("title" in r for r in results)

def test_web_search_handles_errors(mocker):
    mocker.patch("duckduckgo_search.DDGS.text", side_effect=Exception("API Error"))
    results = web_search("test")
    # Sollte Fallback nutzen
    assert isinstance(results, list)
```

### Evaluation-Metriken

```python
# tests/test_integration.py
import time

def test_agent_accuracy():
    """Manuelle Evaluation mit Referenzfragen"""
    test_cases = [
        ("Was ist die Hauptstadt von Frankreich?", "Paris"),
        ("Wer hat die Relativitätstheorie entwickelt?", "Einstein"),
    ]

    for question, expected_keyword in test_cases:
        response = agent.query(question)
        assert expected_keyword.lower() in response.lower()

def test_agent_latency():
    """Latenz-Messung"""
    start = time.time()
    agent.query("Was ist Python?")
    duration = time.time() - start

    assert duration < 10.0  # Max 10 Sekunden
```

---

## Rechtliche Hinweise

### Web-Scraping

- **Robots.txt beachten:** Prüfe `requests.get(url + "/robots.txt")`
- **Rate-Limiting:** Max. 1 Request/Sekunde pro Domain
- **User-Agent:** Immer identifizierbaren User-Agent setzen

```python
HEADERS = {
    "User-Agent": "CrawlLama/1.0 (Educational Research Bot; +https://github.com/yourrepo)"
}
```

### API-Alternativen (Legal)

- **Brave Search API:** https://brave.com/search/api/ (2000 Queries/Monat gratis)
- **Serper.dev:** https://serper.dev/ (Google-Proxy, 2500 Queries gratis)
- **SerpAPI:** https://serpapi.com/ (100 Queries/Monat gratis)

---

## Erweiterte Features

### 1. Wikipedia-Tool

```python
# tools/wiki_lookup.py
import wikipedia

def wiki_lookup(query: str, lang: str = "de") -> str:
    """Dedizierte Wikipedia-Suche"""
    wikipedia.set_lang(lang)
    try:
        page = wikipedia.page(query, auto_suggest=True)
        return page.summary[:2000]
    except wikipedia.DisambiguationError as e:
        return f"Mehrdeutig. Möglichkeiten: {', '.join(e.options[:5])}"
```

### 2. Multi-Tool-Orchestrierung mit LangGraph

```python
from langgraph.graph import StateGraph, END

def build_agent_graph():
    workflow = StateGraph()

    workflow.add_node("decide", decide_action)
    workflow.add_node("web_search", web_search_node)
    workflow.add_node("rag_search", rag_search_node)
    workflow.add_node("answer", generate_answer)

    workflow.add_edge("decide", "web_search")
    workflow.add_edge("decide", "rag_search")
    workflow.add_edge("web_search", "answer")
    workflow.add_edge("rag_search", "answer")
    workflow.add_edge("answer", END)

    return workflow.compile()
```

### 3. GUI-Option (Open WebUI)

```bash
# docker-compose.yml
version: '3'
services:
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    ports:
      - "3000:8080"
    environment:
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    volumes:
      - ./data:/app/backend/data
```

Zugriff: `http://localhost:3000`

---

## Deployment & Production

### Docker-Container

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

```bash
docker build -t crawllama .
docker run -it -v $(pwd)/data:/app/data crawllama
```

### Systemd-Service (Linux)

```ini
# /etc/systemd/system/crawllama.service
[Unit]
Description=CrawlLama Agent
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/opt/crawllama
ExecStart=/usr/bin/python3 main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

---

## Roadmap

### Phase 1: Core (✓ Aktuell)
- [x] Ollama-Integration
- [x] Web-Suche
- [x] Basic Tool-Calls
- [x] Caching

### Phase 2: Robustheit
- [ ] Umfassende Fehlerbehandlung
- [ ] Retry-Logik
- [ ] Offline-Modus
- [ ] Unit-Tests (>80% Coverage)

### Phase 3: Intelligence
- [ ] RAG mit ChromaDB
- [ ] Semantische Suche
- [ ] LangGraph-Orchestrierung
- [ ] Multi-Hop-Reasoning

### Phase 4: Produktionsreife
- [ ] API-Endpunkte (FastAPI)
- [ ] Multi-User-Support
- [ ] GUI (Open WebUI)
- [ ] Performance-Optimierung

---

## Lizenz

MIT License - Freie Verwendung für Forschung, Bildung und kommerzielle Projekte.

**Haftungsausschluss:** Dieses Tool dient Bildungszwecken. Nutzer sind selbst verantwortlich für die Einhaltung von Website-TOS und Datenschutzgesetzen.

---

## Support & Beiträge

- **Issues:** https://github.com/yourusername/crawllama/issues
- **Dokumentation:** https://crawllama.readthedocs.io
- **Diskussionen:** https://github.com/yourusername/crawllama/discussions

**Maintainer:** [Your Name]
**Letzte Aktualisierung:** 2025-10-22
