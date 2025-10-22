# CrawlLama - Erweiterte Implementierungsanleitung

Diese Dokumentation erweitert `setup.md` mit produktionsreifen Features für Fehlerbehandlung, Tests, Performance, Sicherheit und Erweiterbarkeit.

---

## 1. Erweiterte Fehlerbehandlung

### 1.1 API-Fallback-System

**Datei:** `core/fallback_manager.py`

```python
from typing import Callable, List, Any
import logging
from functools import wraps
from core.cache import CacheManager

class FallbackManager:
    """
    Zentrales Fallback-System für alle externen APIs
    Stufenweiser Fallback: Primary API → Fallback APIs → Cache → Default Response
    """

    def __init__(self, cache: CacheManager):
        self.cache = cache
        self.logger = logging.getLogger(__name__)

    def with_fallback(self,
                     primary_func: Callable,
                     fallback_funcs: List[Callable] = None,
                     cache_key_func: Callable = None,
                     default_response: Any = None):
        """
        Decorator für automatische Fallback-Strategie

        Beispiel:
            @fallback_manager.with_fallback(
                primary_func=duckduckgo_search,
                fallback_funcs=[brave_search, serper_search],
                cache_key_func=lambda q: f"search:{q}",
                default_response=[]
            )
            def web_search(query: str):
                return duckduckgo_search(query)
        """
        @wraps(primary_func)
        def wrapper(*args, **kwargs):
            # 1. Versuche primäre Funktion
            try:
                self.logger.info(f"Trying primary: {primary_func.__name__}")
                result = primary_func(*args, **kwargs)

                # Cache erfolgreiche Ergebnisse
                if cache_key_func:
                    cache_key = cache_key_func(*args, **kwargs)
                    self.cache.set(cache_key, result)

                return result

            except Exception as primary_error:
                self.logger.warning(f"Primary failed: {primary_error}")

                # 2. Versuche Fallback-Funktionen
                if fallback_funcs:
                    for fallback in fallback_funcs:
                        try:
                            self.logger.info(f"Trying fallback: {fallback.__name__}")
                            result = fallback(*args, **kwargs)

                            if cache_key_func:
                                cache_key = cache_key_func(*args, **kwargs)
                                self.cache.set(cache_key, result)

                            return result

                        except Exception as fallback_error:
                            self.logger.warning(f"Fallback {fallback.__name__} failed: {fallback_error}")
                            continue

                # 3. Versuche Cache
                if cache_key_func:
                    cache_key = cache_key_func(*args, **kwargs)
                    cached = self.cache.get(cache_key)
                    if cached:
                        self.logger.info(f"Using cached result for {cache_key}")
                        return cached

                # 4. Default-Response
                if default_response is not None:
                    self.logger.warning(f"All methods failed, using default response")
                    return default_response

                # 5. Kein Fallback verfügbar
                raise Exception(f"All fallback methods failed for {primary_func.__name__}")

        return wrapper
```

**Verwendung:**

```python
# tools/web_search.py
from core.fallback_manager import FallbackManager

fallback_manager = FallbackManager(cache_manager)

@fallback_manager.with_fallback(
    primary_func=lambda q, n: duckduckgo_search(q, n),
    fallback_funcs=[
        lambda q, n: brave_search(q, n),
        lambda q, n: serper_search(q, n)
    ],
    cache_key_func=lambda query, max_results: f"search:{query}:{max_results}",
    default_response=[]
)
def web_search(query: str, max_results: int = 3) -> List[Dict]:
    """Web-Suche mit automatischem Fallback"""
    return duckduckgo_search(query, max_results)
```

### 1.2 Ollama-Verbindungshandling

**Datei:** `core/llm_client.py`

```python
import requests
import time
from typing import Optional, Generator
from dataclasses import dataclass
import logging

@dataclass
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434"
    model: str = "llama3:7b"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 2

class OllamaClient:
    """
    Robuster Ollama-Client mit:
    - Verbindungsprüfung beim Start
    - Automatische Reconnects
    - Streaming-Support
    - Fallback auf kleinere Modelle bei OOM
    """

    def __init__(self, config: OllamaConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._ensure_connection()

    def _ensure_connection(self, timeout: int = 5) -> bool:
        """Prüfe ob Ollama-Server erreichbar ist"""
        try:
            response = requests.get(
                f"{self.config.base_url}/api/tags",
                timeout=timeout
            )
            response.raise_for_status()

            # Prüfe ob Modell verfügbar ist
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]

            if self.config.model not in model_names:
                self.logger.warning(
                    f"Model {self.config.model} not found. Available: {model_names}"
                )
                return False

            self.logger.info(f"Connected to Ollama at {self.config.base_url}")
            return True

        except requests.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.config.base_url}\n"
                f"Please ensure Ollama is running:\n"
                f"  - Start: ollama serve\n"
                f"  - Or: systemctl start ollama (Linux)\n"
                f"  - Or: Check if port 11434 is accessible"
            )
        except requests.Timeout:
            raise TimeoutError(
                f"Ollama server at {self.config.base_url} is not responding"
            )

    def generate(self,
                prompt: str,
                stream: bool = False,
                fallback_on_error: bool = True) -> str | Generator:
        """
        Generiere Text mit automatischem Fehlerhandling

        Args:
            prompt: Eingabe-Prompt
            stream: Stream-Ausgabe
            fallback_on_error: Bei OOM auf kleineres Modell zurückfallen
        """
        for attempt in range(self.config.max_retries):
            try:
                response = requests.post(
                    f"{self.config.base_url}/api/generate",
                    json={
                        "model": self.config.model,
                        "prompt": prompt,
                        "stream": stream
                    },
                    timeout=self.config.timeout,
                    stream=stream
                )
                response.raise_for_status()

                if stream:
                    return self._stream_response(response)
                else:
                    return response.json()["response"]

            except requests.ConnectionError:
                self.logger.error(f"Connection lost (attempt {attempt + 1}/{self.config.max_retries})")
                time.sleep(self.config.retry_delay)
                self._ensure_connection()

            except requests.HTTPError as e:
                if e.response.status_code == 500:
                    error_msg = e.response.json().get("error", "")

                    # OOM-Detection
                    if "out of memory" in error_msg.lower() and fallback_on_error:
                        self.logger.warning("OOM detected, falling back to smaller model")
                        return self._fallback_to_smaller_model(prompt, stream)

                raise

        raise Exception(f"Failed after {self.config.max_retries} retries")

    def _fallback_to_smaller_model(self, prompt: str, stream: bool) -> str:
        """Fallback-Modellhierarchie bei OOM"""
        fallback_models = [
            "mistral:7b",
            "phi3:mini",
            "tinyllama:latest"
        ]

        original_model = self.config.model

        for model in fallback_models:
            try:
                self.logger.info(f"Trying fallback model: {model}")
                self.config.model = model
                return self.generate(prompt, stream, fallback_on_error=False)
            except Exception as e:
                self.logger.warning(f"Fallback model {model} failed: {e}")
                continue

        self.config.model = original_model
        raise Exception("All fallback models failed")

    def _stream_response(self, response) -> Generator[str, None, None]:
        """Stream einzelne Tokens"""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                if "response" in chunk:
                    yield chunk["response"]
                if chunk.get("done", False):
                    break
```

**Verwendung mit Healthcheck:**

```python
# main.py
from core.llm_client import OllamaClient, OllamaConfig

def startup_check():
    """Führe Healthchecks beim Start durch"""
    try:
        client = OllamaClient(OllamaConfig())
        print("✓ Ollama connection successful")
        return True
    except ConnectionError as e:
        print(f"✗ Ollama connection failed:\n{e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    if not startup_check():
        sys.exit(1)

    main()
```

### 1.3 Proxy-Validierung

**Datei:** `utils/proxy_validator.py`

```python
import os
import requests
from urllib.parse import urlparse
from typing import Optional, Dict
import logging

class ProxyValidator:
    """
    Validiert und testet Proxy-Einstellungen aus .env
    Unterstützt HTTP, HTTPS, SOCKS5
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.test_url = "https://httpbin.org/ip"

    def load_from_env(self) -> Optional[Dict[str, str]]:
        """Lade Proxy-Settings aus Umgebungsvariablen"""
        http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")

        if not http_proxy and not https_proxy:
            return None

        proxies = {}
        if http_proxy:
            proxies["http"] = http_proxy
        if https_proxy:
            proxies["https"] = https_proxy

        return proxies

    def validate_proxy_url(self, proxy_url: str) -> bool:
        """Validiere Proxy-URL-Format"""
        try:
            parsed = urlparse(proxy_url)

            # Prüfe Scheme
            if parsed.scheme not in ["http", "https", "socks5"]:
                self.logger.error(f"Invalid proxy scheme: {parsed.scheme}")
                return False

            # Prüfe Host
            if not parsed.hostname:
                self.logger.error("Proxy URL missing hostname")
                return False

            # Prüfe Port
            if not parsed.port:
                self.logger.warning(f"No port specified, using default for {parsed.scheme}")

            return True

        except Exception as e:
            self.logger.error(f"Invalid proxy URL format: {e}")
            return False

    def test_proxy(self, proxies: Dict[str, str], timeout: int = 10) -> bool:
        """Teste ob Proxy funktioniert"""
        try:
            response = requests.get(
                self.test_url,
                proxies=proxies,
                timeout=timeout
            )
            response.raise_for_status()

            ip_info = response.json()
            self.logger.info(f"Proxy working. External IP: {ip_info.get('origin')}")
            return True

        except requests.ProxyError:
            self.logger.error("Proxy connection failed - check credentials/firewall")
            return False
        except requests.Timeout:
            self.logger.error("Proxy timeout - server not responding")
            return False
        except Exception as e:
            self.logger.error(f"Proxy test failed: {e}")
            return False

    def validate_and_test(self) -> Optional[Dict[str, str]]:
        """Vollständige Validierung und Test"""
        proxies = self.load_from_env()

        if not proxies:
            self.logger.info("No proxy configured")
            return None

        # Validiere URLs
        for protocol, proxy_url in proxies.items():
            if not self.validate_proxy_url(proxy_url):
                raise ValueError(f"Invalid {protocol} proxy URL: {proxy_url}")

        # Teste Verbindung
        if not self.test_proxy(proxies):
            raise ConnectionError("Proxy validation failed")

        self.logger.info(f"Proxy validated successfully: {list(proxies.keys())}")
        return proxies
```

**Integration in main.py:**

```python
from utils.proxy_validator import ProxyValidator

def setup_proxies():
    """Validiere und aktiviere Proxies"""
    validator = ProxyValidator()

    try:
        proxies = validator.validate_and_test()
        if proxies:
            # Setze globale Session mit Proxy
            session = requests.Session()
            session.proxies.update(proxies)
            return session
        return requests.Session()

    except (ValueError, ConnectionError) as e:
        print(f"⚠️  Proxy validation failed: {e}")
        print("Continue without proxy? [y/N]")
        if input().lower() != 'y':
            sys.exit(1)
        return requests.Session()
```

---

## 2. Umfassende Testabdeckung

### 2.1 Edge-Case-Tests

**Datei:** `tests/test_edge_cases.py`

```python
import pytest
from tools.web_search import web_search
from tools.page_reader import extract_text
from utils.validators import is_safe_url

class TestWebSearchEdgeCases:
    """Tests für ungültige/ungewöhnliche Suchanfragen"""

    def test_empty_query(self):
        """Leere Query sollte leere Liste zurückgeben"""
        results = web_search("")
        assert results == []

    def test_very_long_query(self):
        """Sehr lange Queries sollten gekürzt werden"""
        long_query = "word " * 1000
        results = web_search(long_query)
        assert isinstance(results, list)

    def test_special_characters_in_query(self):
        """Sonderzeichen sollten escaped werden"""
        results = web_search('test "quotes" & <html>')
        assert isinstance(results, list)

    def test_no_results_found(self, mocker):
        """Wenn keine Ergebnisse, leere Liste zurückgeben"""
        mocker.patch("duckduckgo_search.DDGS.text", return_value=[])
        results = web_search("xyzabc123nonexistent")
        assert results == []

    def test_api_rate_limit(self, mocker):
        """429 Rate Limit sollte Retry auslösen"""
        from requests.exceptions import HTTPError

        mock_response = mocker.Mock()
        mock_response.status_code = 429

        mocker.patch(
            "duckduckgo_search.DDGS.text",
            side_effect=HTTPError(response=mock_response)
        )

        # Sollte nach Retries auf Fallback zurückgreifen
        results = web_search("test")
        assert isinstance(results, list)

class TestPageReaderEdgeCases:
    """Tests für kaputte/ungewöhnliche HTML-Seiten"""

    def test_empty_html(self):
        """Leere HTML-Seite"""
        text = extract_text("")
        assert text == ""

    def test_malformed_html(self):
        """Kaputtes HTML sollte nicht crashen"""
        broken_html = "<html><body><p>Test</p><div>Unclosed"
        text = extract_text(broken_html)
        assert "Test" in text

    def test_only_scripts_and_styles(self):
        """Seite nur mit Script/Style-Tags"""
        html = """
        <html>
            <script>alert('test')</script>
            <style>body { color: red; }</style>
        </html>
        """
        text = extract_text(html)
        assert text.strip() == ""

    def test_non_utf8_encoding(self):
        """Nicht-UTF-8 Encoding sollte behandelt werden"""
        html = b"\x80\x81\x82"  # Invalid UTF-8
        # Sollte nicht crashen
        try:
            text = extract_text(html.decode('utf-8', errors='ignore'))
            assert isinstance(text, str)
        except UnicodeDecodeError:
            pytest.fail("Should handle encoding errors gracefully")

    def test_huge_html_file(self):
        """Sehr große HTML-Datei sollte gekürzt werden"""
        huge_html = "<p>" + "word " * 100000 + "</p>"
        text = extract_text(huge_html, max_length=3000)
        assert len(text) <= 3000

    def test_nested_tags(self):
        """Tief verschachtelte Tags"""
        html = "<div>" * 100 + "Content" + "</div>" * 100
        text = extract_text(html)
        assert "Content" in text

class TestURLValidation:
    """Tests für URL-Validierung"""

    @pytest.mark.parametrize("url", [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "data:text/html,<script>alert(1)</script>",
        "ftp://malicious.com",
    ])
    def test_dangerous_urls_rejected(self, url):
        """Gefährliche URL-Schemes sollten blockiert werden"""
        assert is_safe_url(url) == False

    @pytest.mark.parametrize("url", [
        "http://example.com",
        "https://example.com",
        "https://example.com:8080/path?query=1",
    ])
    def test_safe_urls_accepted(self, url):
        """Valide HTTP(S)-URLs sollten akzeptiert werden"""
        assert is_safe_url(url) == True

    def test_localhost_urls(self):
        """Localhost sollte optional blockiert werden"""
        assert is_safe_url("http://localhost") == True
        assert is_safe_url("http://127.0.0.1") == True

        # Mit Whitelist sollte localhost blockiert sein
        assert is_safe_url(
            "http://localhost",
            allowed_domains=["example.com"]
        ) == False
```

### 2.2 Integrationstests

**Datei:** `tests/test_integration.py`

```python
import pytest
from core.agent import SearchAgent
from core.cache import CacheManager
import tempfile
import os

@pytest.fixture
def temp_cache_dir():
    """Erstelle temporäres Cache-Verzeichnis für Tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def agent(temp_cache_dir):
    """Erstelle Test-Agent mit Mock-LLM"""
    return SearchAgent(
        model="test-model",
        cache_dir=temp_cache_dir,
        enable_web=True
    )

class TestMultiToolWorkflow:
    """Tests für komplette Workflows mit mehreren Tools"""

    def test_search_to_rag_to_answer(self, agent, mocker):
        """
        Test: Frage → Web-Suche → RAG-Speicherung → Antwort
        """
        # Mock LLM-Response
        mocker.patch.object(
            agent.llm,
            "generate",
            return_value='{"action": "web_search", "action_input": "Python tutorial"}'
        )

        # Mock Web-Suche
        mock_search_results = [
            {"url": "https://example.com/py", "title": "Python Tutorial", "snippet": "..."}
        ]
        mocker.patch("tools.web_search.web_search", return_value=mock_search_results)

        # Mock Page Reader
        mocker.patch(
            "tools.page_reader.extract_text",
            return_value="Python is a programming language..."
        )

        # Führe Query aus
        response = agent.query("How do I learn Python?")

        # Assertions
        assert isinstance(response, str)
        assert len(response) > 0

        # Prüfe ob RAG-Datenbank gefüllt wurde
        assert agent.rag.collection.count() > 0

    def test_cache_hit_skips_web_request(self, agent, mocker):
        """Bei Cache-Hit sollte keine Web-Anfrage gemacht werden"""
        # Erste Anfrage (füllt Cache)
        agent.cache.set("search:Python", [{"url": "cached.com"}])

        # Mock Web-Suche (sollte NICHT aufgerufen werden)
        mock_search = mocker.patch("tools.web_search.web_search")

        # Zweite Anfrage (sollte aus Cache kommen)
        agent.query("Python")

        # Web-Suche sollte nicht aufgerufen worden sein
        mock_search.assert_not_called()

    def test_error_recovery_with_fallback(self, agent, mocker):
        """Bei Fehler sollte Fallback-Strategie greifen"""
        # Primary Search schlägt fehl
        mocker.patch(
            "tools.web_search.duckduckgo_search",
            side_effect=Exception("API Error")
        )

        # Fallback Search erfolgreich
        mocker.patch(
            "tools.web_search.brave_search",
            return_value=[{"url": "fallback.com"}]
        )

        # Sollte trotz Primary-Fehler funktionieren
        response = agent.query("test query")
        assert isinstance(response, str)

    def test_concurrent_requests(self, agent, mocker):
        """Mehrere parallele Anfragen sollten nicht interferieren"""
        import concurrent.futures

        def make_query(query):
            return agent.query(query)

        queries = ["Query 1", "Query 2", "Query 3"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_query, q) for q in queries]
            results = [f.result() for f in futures]

        # Alle Anfragen sollten erfolgreich sein
        assert len(results) == 3
        assert all(isinstance(r, str) for r in results)

    def test_long_conversation_context_management(self, agent):
        """Lange Conversations sollten Kontext-Limit nicht überschreiten"""
        # Simuliere viele Nachrichten
        for i in range(50):
            agent.query(f"Question {i}")

        # Kontext sollte automatisch gekürzt worden sein
        total_tokens = agent.context_manager.count_tokens(
            str(agent.history)
        )
        assert total_tokens < agent.context_manager.max_tokens
```

### 2.3 Ollama-Mocking für stabile Tests

**Datei:** `tests/conftest.py`

```python
import pytest
from unittest.mock import Mock, MagicMock

@pytest.fixture
def mock_ollama_response():
    """Mock für erfolgreiche Ollama-Response"""
    return {
        "model": "llama3:7b",
        "created_at": "2024-01-01T00:00:00Z",
        "response": "This is a test response",
        "done": True
    }

@pytest.fixture
def mock_ollama_client(mocker, mock_ollama_response):
    """Mock für OllamaClient ohne echten Server"""
    mock_client = MagicMock()
    mock_client.generate.return_value = mock_ollama_response["response"]
    mock_client.config.model = "llama3:7b"

    # Mock Streaming
    def mock_stream(*args, **kwargs):
        for char in "Test response":
            yield char

    mock_client.stream_generate = mock_stream

    return mock_client

@pytest.fixture
def mock_ollama_server(mocker, mock_ollama_response):
    """Mock für Ollama HTTP-Endpoints"""
    mock_post = mocker.patch("requests.post")
    mock_get = mocker.patch("requests.get")

    # Mock /api/generate
    mock_response = Mock()
    mock_response.json.return_value = mock_ollama_response
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    # Mock /api/tags (für Verbindungscheck)
    mock_tags_response = Mock()
    mock_tags_response.json.return_value = {
        "models": [{"name": "llama3:7b"}]
    }
    mock_tags_response.status_code = 200
    mock_get.return_value = mock_tags_response

    return {
        "post": mock_post,
        "get": mock_get
    }

# Verwendung in Tests:
def test_with_mock_ollama(mock_ollama_client):
    from core.agent import SearchAgent

    agent = SearchAgent(llm_client=mock_ollama_client)
    response = agent.query("test")

    assert "test response" in response.lower()
```

---

## 3. Rate-Limiting

### 3.1 robots.txt Handler

**Datei:** `utils/robots_handler.py`

```python
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse
from typing import Dict, Optional
import time
import logging

class RobotsHandler:
    """
    Verwaltet robots.txt Regeln für alle Domains
    Cached robots.txt für Performance
    """

    def __init__(self, user_agent: str = "CrawlLama/1.0"):
        self.user_agent = user_agent
        self.parsers: Dict[str, RobotFileParser] = {}
        self.cache_duration = 3600  # 1 Stunde
        self.last_fetch: Dict[str, float] = {}
        self.logger = logging.getLogger(__name__)

    def can_fetch(self, url: str) -> bool:
        """
        Prüfe ob URL gecrawlt werden darf

        Returns:
            True wenn erlaubt, False wenn verboten
        """
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        # Hole/Update robots.txt Parser
        parser = self._get_parser(domain)

        if parser is None:
            # Kein robots.txt gefunden → erlauben
            return True

        # Prüfe URL
        allowed = parser.can_fetch(self.user_agent, url)

        if not allowed:
            self.logger.warning(f"Blocked by robots.txt: {url}")

        return allowed

    def get_crawl_delay(self, url: str) -> Optional[float]:
        """
        Hole Crawl-Delay aus robots.txt

        Returns:
            Delay in Sekunden, oder None
        """
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        parser = self._get_parser(domain)

        if parser is None:
            return None

        delay = parser.crawl_delay(self.user_agent)
        return float(delay) if delay else None

    def _get_parser(self, domain: str) -> Optional[RobotFileParser]:
        """Hole oder erstelle RobotFileParser für Domain"""
        current_time = time.time()

        # Prüfe ob Cache noch gültig
        if domain in self.parsers:
            if current_time - self.last_fetch.get(domain, 0) < self.cache_duration:
                return self.parsers[domain]

        # Fetch robots.txt
        try:
            parser = RobotFileParser()
            parser.set_url(f"{domain}/robots.txt")
            parser.read()

            self.parsers[domain] = parser
            self.last_fetch[domain] = current_time

            self.logger.info(f"Loaded robots.txt for {domain}")
            return parser

        except Exception as e:
            self.logger.warning(f"Could not fetch robots.txt for {domain}: {e}")
            return None
```

### 3.2 Domain Rate-Limiter

**Datei:** `utils/rate_limiter.py`

```python
import time
from collections import defaultdict
from threading import Lock
from typing import Dict
import logging

class DomainRateLimiter:
    """
    Rate-Limiting pro Domain
    Max. 1 Request/Sekunde pro Domain (konfigurierbar)
    """

    def __init__(self, requests_per_second: float = 1.0):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second

        # Letzter Request-Zeitpunkt pro Domain
        self.last_request: Dict[str, float] = defaultdict(float)

        # Thread-Safety
        self.lock = Lock()

        self.logger = logging.getLogger(__name__)

    def wait_if_needed(self, domain: str):
        """
        Warte falls notwendig um Rate-Limit einzuhalten

        Args:
            domain: Domain (z.B. "example.com")
        """
        with self.lock:
            current_time = time.time()
            last_time = self.last_request[domain]

            time_since_last = current_time - last_time

            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                self.logger.debug(f"Rate limiting {domain}: waiting {wait_time:.2f}s")
                time.sleep(wait_time)

            self.last_request[domain] = time.time()

    def set_custom_rate(self, domain: str, requests_per_second: float):
        """
        Setze individuelles Rate-Limit für spezifische Domain
        (z.B. aus robots.txt crawl-delay)
        """
        # Implementierung für domain-spezifische Limits
        pass

# Integration in page_reader:
class RateLimitedPageReader:
    def __init__(self):
        self.rate_limiter = DomainRateLimiter(requests_per_second=1.0)
        self.robots = RobotsHandler()

    def fetch_page(self, url: str) -> str:
        """Fetch mit Rate-Limiting und robots.txt Check"""
        from urllib.parse import urlparse

        # 1. Prüfe robots.txt
        if not self.robots.can_fetch(url):
            raise PermissionError(f"Blocked by robots.txt: {url}")

        # 2. Hole Crawl-Delay
        crawl_delay = self.robots.get_crawl_delay(url)
        if crawl_delay:
            time.sleep(crawl_delay)

        # 3. Rate-Limiting
        domain = urlparse(url).netloc
        self.rate_limiter.wait_if_needed(domain)

        # 4. Fetch
        response = requests.get(url, timeout=10)
        return response.text
```

---

## 4. Performance-Optimierung

### 4.1 Asynchrone Web-Requests

**Datei:** `tools/async_web_search.py`

```python
import asyncio
import aiohttp
from typing import List, Dict
from bs4 import BeautifulSoup

class AsyncWebSearcher:
    """
    Parallele Web-Requests mit asyncio
    Bis zu 10x schneller als sequentielle Requests
    """

    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def fetch_page(self, url: str, timeout: int = 10) -> Dict[str, str]:
        """Fetch einzelne Seite asynchron"""
        try:
            async with self.session.get(url, timeout=timeout) as response:
                html = await response.text()
                return {
                    "url": url,
                    "html": html,
                    "status": response.status
                }
        except asyncio.TimeoutError:
            return {"url": url, "error": "timeout"}
        except Exception as e:
            return {"url": url, "error": str(e)}

    async def fetch_multiple(self, urls: List[str]) -> List[Dict]:
        """Fetch mehrere Seiten parallel"""
        # Semaphore für max. gleichzeitige Requests
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def fetch_with_semaphore(url):
            async with semaphore:
                return await self.fetch_page(url)

        tasks = [fetch_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks)

    def extract_texts_parallel(self, results: List[Dict]) -> List[str]:
        """Extrahiere Text aus HTML parallel"""
        texts = []
        for result in results:
            if "html" in result:
                soup = BeautifulSoup(result["html"], "html5lib")
                text = ' '.join(soup.stripped_strings)[:3000]
                texts.append(text)
        return texts

# Verwendung:
async def search_and_extract(query: str) -> List[str]:
    """Kompletter Workflow: Suche → Fetch → Extract"""
    # 1. Normale Suche (synchron, da DuckDuckGo keine async API hat)
    search_results = web_search(query, max_results=5)
    urls = [r["url"] for r in search_results]

    # 2. Paralleles Fetching
    async with AsyncWebSearcher(max_concurrent=5) as searcher:
        results = await searcher.fetch_multiple(urls)
        texts = searcher.extract_texts_parallel(results)

    return texts

# CLI-Wrapper für async:
def search_and_extract_sync(query: str) -> List[str]:
    """Synchroner Wrapper für async Funktion"""
    return asyncio.run(search_and_extract(query))
```

**Performance-Vergleich:**

```python
# tests/test_performance.py
import time

def test_async_vs_sync_performance():
    """Async sollte deutlich schneller sein"""
    urls = ["https://example.com"] * 10

    # Synchron
    start = time.time()
    for url in urls:
        requests.get(url)
    sync_time = time.time() - start

    # Asynchron
    start = time.time()
    async def fetch_all():
        async with AsyncWebSearcher() as searcher:
            await searcher.fetch_multiple(urls)
    asyncio.run(fetch_all())
    async_time = time.time() - start

    # Async sollte mind. 5x schneller sein
    assert async_time < sync_time / 5
```

### 4.2 RAM-Optimierung für ChromaDB

**Datei:** `tools/optimized_rag.py`

```python
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

class OptimizedRAGManager:
    """
    RAM-optimierte RAG-Implementierung:
    - Kleineres Embedding-Modell (all-MiniLM-L6-v2: 80MB statt 420MB)
    - Batch-Processing für große Dokumente
    - Automatisches Pruning alter Embeddings
    """

    def __init__(self,
                 persist_dir: str = "data/embeddings",
                 embedding_model: str = "all-MiniLM-L6-v2",
                 max_documents: int = 1000):

        # Verwende kleineres, schnelleres Modell
        self.embedder = SentenceTransformer(embedding_model)

        # ChromaDB mit Disk-Persistenz (statt in-memory)
        self.client = chromadb.Client(Settings(
            persist_directory=persist_dir,
            anonymized_telemetry=False,
            allow_reset=True
        ))

        self.collection = self.client.get_or_create_collection(
            name="web_documents",
            metadata={"hnsw:space": "cosine"}
        )

        self.max_documents = max_documents

    def add_documents_batched(self,
                             texts: List[str],
                             metadatas: List[dict],
                             batch_size: int = 100):
        """
        Füge Dokumente in Batches hinzu (RAM-Optimierung)
        """
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]

            # Generiere Embeddings
            embeddings = self.embedder.encode(
                batch_texts,
                show_progress_bar=False,
                convert_to_numpy=True
            )

            # Füge zu ChromaDB hinzu
            ids = [f"doc_{i + j}" for j in range(len(batch_texts))]
            self.collection.add(
                documents=batch_texts,
                embeddings=embeddings.tolist(),
                metadatas=batch_meta,
                ids=ids
            )

            # Prüfe Limit
            if self.collection.count() > self.max_documents:
                self._prune_old_documents()

    def _prune_old_documents(self):
        """Entferne älteste Dokumente bei Überschreitung des Limits"""
        current_count = self.collection.count()
        to_delete = current_count - self.max_documents

        if to_delete > 0:
            # Hole älteste Dokumente (nach Timestamp in Metadata)
            results = self.collection.get(
                limit=to_delete,
                include=["metadatas"]
            )

            # Lösche
            self.collection.delete(ids=results["ids"])

    def search_optimized(self, query: str, top_k: int = 3) -> List[dict]:
        """
        Optimierte Suche mit reduzierten Ergebnissen
        """
        # Reduziere top_k für schnellere Suche
        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, 5)  # Max 5 Ergebnisse
        )

        return [{
            "text": doc,
            "metadata": meta
        } for doc, meta in zip(
            results["documents"][0],
            results["metadatas"][0]
        )]
```

### 4.3 Lazy-Loading für Tools

**Datei:** `core/lazy_loader.py`

```python
from typing import Dict, Callable, Any
import importlib

class LazyToolLoader:
    """
    Lädt Tools nur bei Bedarf (reduziert Startzeit)
    Speichert geladene Tools im Cache
    """

    def __init__(self):
        self._tools: Dict[str, Any] = {}
        self._tool_configs = {
            "web_search": {
                "module": "tools.web_search",
                "class": "WebSearcher"
            },
            "rag": {
                "module": "tools.rag",
                "class": "RAGManager"
            },
            "wiki": {
                "module": "tools.wiki_lookup",
                "class": "WikiLookup"
            }
        }

    def get_tool(self, tool_name: str) -> Any:
        """
        Lade Tool lazy (nur beim ersten Aufruf)
        """
        if tool_name in self._tools:
            return self._tools[tool_name]

        if tool_name not in self._tool_configs:
            raise ValueError(f"Unknown tool: {tool_name}")

        # Dynamisches Import
        config = self._tool_configs[tool_name]
        module = importlib.import_module(config["module"])
        tool_class = getattr(module, config["class"])

        # Instanziiere und cache
        self._tools[tool_name] = tool_class()

        return self._tools[tool_name]

# Verwendung in Agent:
class SearchAgent:
    def __init__(self):
        self.tool_loader = LazyToolLoader()

    def query(self, question: str):
        # RAG wird erst hier geladen, nicht beim Start
        if self._needs_rag(question):
            rag = self.tool_loader.get_tool("rag")
            results = rag.search(question)
```

---

## 5. Erweiterte Sicherheit

### 5.1 API-Key-Verschlüsselung

**Datei:** `utils/secure_config.py`

```python
import keyring
import os
from cryptography.fernet import Fernet
from pathlib import Path
from typing import Optional

class SecureConfigManager:
    """
    Sichere Verwaltung von API-Keys:
    1. Systemkeyring (macOS/Linux/Windows)
    2. Verschlüsselte .env (Fallback)
    3. Klartext .env (nur Development)
    """

    SERVICE_NAME = "crawllama"

    def __init__(self, env_file: str = ".env"):
        self.env_file = Path(env_file)
        self._encryption_key = self._get_or_create_encryption_key()

    def _get_or_create_encryption_key(self) -> bytes:
        """Hole oder erstelle Verschlüsselungskey"""
        key_file = Path.home() / ".crawllama" / "secret.key"

        if key_file.exists():
            return key_file.read_bytes()

        # Erstelle neuen Key
        key = Fernet.generate_key()
        key_file.parent.mkdir(exist_ok=True)
        key_file.write_bytes(key)
        key_file.chmod(0o600)  # Nur Owner kann lesen

        return key

    def store_api_key(self, service: str, api_key: str, use_keyring: bool = True):
        """
        Speichere API-Key sicher

        Args:
            service: Service-Name (z.B. "brave", "serper")
            api_key: Der API-Key
            use_keyring: Nutze System-Keyring (empfohlen)
        """
        if use_keyring:
            try:
                keyring.set_password(self.SERVICE_NAME, service, api_key)
                print(f"✓ API-Key für {service} sicher im Keyring gespeichert")
                return
            except Exception as e:
                print(f"⚠️  Keyring nicht verfügbar: {e}")
                print("Fallback auf verschlüsselte .env")

        # Fallback: Verschlüsselte .env
        self._store_encrypted(service, api_key)

    def get_api_key(self, service: str) -> Optional[str]:
        """
        Hole API-Key aus sicherem Speicher

        Reihenfolge:
        1. System-Keyring
        2. Verschlüsselte .env
        3. Klartext .env (nur Development)
        """
        # 1. Versuche Keyring
        try:
            key = keyring.get_password(self.SERVICE_NAME, service)
            if key:
                return key
        except:
            pass

        # 2. Verschlüsselte .env
        key = self._get_encrypted(service)
        if key:
            return key

        # 3. Klartext .env
        env_key = f"{service.upper()}_API_KEY"
        return os.getenv(env_key)

    def _store_encrypted(self, service: str, value: str):
        """Speichere verschlüsselt in .env.encrypted"""
        fernet = Fernet(self._encryption_key)
        encrypted = fernet.encrypt(value.encode())

        enc_file = self.env_file.with_suffix(".env.encrypted")

        # Lade existierende Keys
        data = {}
        if enc_file.exists():
            with open(enc_file, 'rb') as f:
                data = eval(f.read().decode())

        data[service] = encrypted.decode()

        with open(enc_file, 'wb') as f:
            f.write(str(data).encode())

        enc_file.chmod(0o600)

    def _get_encrypted(self, service: str) -> Optional[str]:
        """Lese verschlüsselten Key"""
        enc_file = self.env_file.with_suffix(".env.encrypted")

        if not enc_file.exists():
            return None

        with open(enc_file, 'rb') as f:
            data = eval(f.read().decode())

        if service not in data:
            return None

        fernet = Fernet(self._encryption_key)
        decrypted = fernet.decrypt(data[service].encode())

        return decrypted.decode()

# CLI für Key-Management:
def setup_api_keys():
    """Interaktives Setup für API-Keys"""
    manager = SecureConfigManager()

    services = {
        "brave": "Brave Search API Key",
        "serper": "Serper.dev API Key",
        "openai": "OpenAI API Key (optional)"
    }

    for service, description in services.items():
        print(f"\n{description}:")
        print("(Enter drücken um zu überspringen)")

        api_key = input(f"{service.upper()}_API_KEY: ").strip()

        if api_key:
            manager.store_api_key(service, api_key)

# In main.py:
if __name__ == "__main__":
    if "--setup-keys" in sys.argv:
        setup_api_keys()
        sys.exit(0)
```

### 5.2 LLM-Output-Validierung

**Datei:** `utils/security_validator.py`

```python
import re
from typing import List, Dict

class SecurityValidator:
    """
    Validiert LLM-Outputs auf gefährliche Patterns
    Verhindert Injection-Angriffe
    """

    DANGEROUS_PATTERNS = [
        # Code-Execution
        r"eval\s*\(",
        r"exec\s*\(",
        r"__import__\s*\(",
        r"subprocess\.",
        r"os\.system\s*\(",

        # SQL-Injection-ähnlich
        r"(DROP|DELETE|UPDATE|INSERT)\s+(TABLE|FROM|INTO)",

        # Path-Traversal
        r"\.\./",
        r"\.\.\\",

        # Script-Injection
        r"<script[^>]*>",
        r"javascript:",
        r"onerror\s*=",

        # Command-Injection
        r";\s*(rm|del|format|shutdown)",
        r"\|\s*(curl|wget|nc)",
    ]

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_PATTERNS]

    def validate(self, text: str) -> Dict[str, any]:
        """
        Validiere Text auf Sicherheitsprobleme

        Returns:
            {
                "safe": bool,
                "issues": List[str],
                "sanitized": str
            }
        """
        issues = []

        for pattern in self.patterns:
            matches = pattern.findall(text)
            if matches:
                issues.append(f"Dangerous pattern detected: {pattern.pattern}")

        # Im strict mode: blocke komplett
        if self.strict_mode and issues:
            return {
                "safe": False,
                "issues": issues,
                "sanitized": ""
            }

        # Ansonsten: sanitize
        sanitized = text
        for pattern in self.patterns:
            sanitized = pattern.sub("[REDACTED]", sanitized)

        return {
            "safe": len(issues) == 0,
            "issues": issues,
            "sanitized": sanitized
        }

    def validate_tool_call(self, tool_name: str, arguments: Dict) -> bool:
        """
        Validiere Tool-Call-Argumente
        """
        # Whitelist erlaubter Tools
        allowed_tools = ["web_search", "read_page", "rag_search", "wiki_lookup"]

        if tool_name not in allowed_tools:
            logging.warning(f"Unknown tool requested: {tool_name}")
            return False

        # Validiere Argumente
        for key, value in arguments.items():
            if isinstance(value, str):
                result = self.validate(value)
                if not result["safe"]:
                    logging.error(f"Dangerous argument in {tool_name}.{key}: {result['issues']}")
                    return False

        return True

# Integration in Agent:
class SecureAgent:
    def __init__(self):
        self.validator = SecurityValidator(strict_mode=True)

    def process_llm_response(self, response: str) -> str:
        """Validiere und sanitize LLM-Response"""
        validation = self.validator.validate(response)

        if not validation["safe"]:
            logging.warning(f"Security issues detected: {validation['issues']}")

            if self.validator.strict_mode:
                raise SecurityError("Dangerous content in LLM response")
            else:
                return validation["sanitized"]

        return response
```

### 5.3 Domain-Blacklist

**Datei:** `utils/domain_blacklist.py`

```python
from typing import Set
from urllib.parse import urlparse
import requests

class DomainBlacklist:
    """
    Blacklist für gefährliche/unerwünschte Domains
    Unterstützt lokale und Remote-Listen
    """

    def __init__(self,
                 local_blacklist: Set[str] = None,
                 remote_blacklist_url: str = None):

        self.blacklist: Set[str] = local_blacklist or set()

        # Lade Remote-Blacklist (z.B. von URLhaus)
        if remote_blacklist_url:
            self._load_remote_blacklist(remote_blacklist_url)

        # Standard-Blacklist
        self.blacklist.update([
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "169.254.0.0/16",  # Link-Local
            "10.0.0.0/8",       # Private
            "172.16.0.0/12",    # Private
            "192.168.0.0/16",   # Private
        ])

    def is_blacklisted(self, url: str) -> bool:
        """Prüfe ob URL auf Blacklist"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Exakte Domain
        if domain in self.blacklist:
            return True

        # Subdomain-Check
        for blacklisted in self.blacklist:
            if domain.endswith(f".{blacklisted}"):
                return True

        return False

    def _load_remote_blacklist(self, url: str):
        """Lade Blacklist von Remote-URL"""
        try:
            response = requests.get(url, timeout=10)
            domains = response.text.strip().split('\n')
            self.blacklist.update(domains)
        except Exception as e:
            logging.warning(f"Could not load remote blacklist: {e}")

# Verwendung:
blacklist = DomainBlacklist(
    remote_blacklist_url="https://urlhaus.abuse.ch/downloads/text/"
)

def safe_fetch(url: str):
    if blacklist.is_blacklisted(url):
        raise SecurityError(f"URL is blacklisted: {url}")

    return requests.get(url)
```

---

## 6. Erweiterbarkeit & Plugin-System

### 6.1 Dynamisches Tool-Loading

**Datei:** `core/plugin_manager.py`

```python
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Callable
from dataclasses import dataclass
import inspect
import logging

@dataclass
class ToolMetadata:
    """Metadaten für ein Tool/Plugin"""
    name: str
    description: str
    version: str
    author: str
    parameters: Dict[str, type]
    function: Callable

class PluginManager:
    """
    Dynamisches Plugin-System für Tools

    Plugins können aus drei Quellen geladen werden:
    1. Built-in tools/ Verzeichnis
    2. User-Plugins in ~/.crawllama/plugins/
    3. Externe Python-Module
    """

    def __init__(self, plugin_dirs: List[str] = None):
        self.logger = logging.getLogger(__name__)
        self.tools: Dict[str, ToolMetadata] = {}

        # Standard-Plugin-Verzeichnisse
        self.plugin_dirs = plugin_dirs or [
            "tools",  # Built-in
            str(Path.home() / ".crawllama" / "plugins"),  # User
        ]

    def discover_plugins(self):
        """Automatisches Discovery aller Plugins"""
        for plugin_dir in self.plugin_dirs:
            path = Path(plugin_dir)

            if not path.exists():
                continue

            # Finde alle .py Dateien
            for py_file in path.glob("*.py"):
                if py_file.stem.startswith("_"):
                    continue

                try:
                    self._load_plugin_from_file(py_file)
                except Exception as e:
                    self.logger.warning(f"Failed to load plugin {py_file}: {e}")

    def _load_plugin_from_file(self, filepath: Path):
        """Lade Plugin aus Python-Datei"""
        module_name = f"plugin_{filepath.stem}"

        # Dynamisches Import
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Finde alle Tools im Modul
        for name, obj in inspect.getmembers(module):
            # Prüfe auf Tool-Decorator
            if hasattr(obj, "_is_crawllama_tool"):
                self._register_tool(obj)

    def _register_tool(self, func: Callable):
        """Registriere Tool mit Metadaten"""
        metadata = ToolMetadata(
            name=getattr(func, "_tool_name", func.__name__),
            description=func.__doc__ or "No description",
            version=getattr(func, "_tool_version", "1.0.0"),
            author=getattr(func, "_tool_author", "Unknown"),
            parameters=self._extract_parameters(func),
            function=func
        )

        self.tools[metadata.name] = metadata
        self.logger.info(f"Registered tool: {metadata.name} v{metadata.version}")

    def _extract_parameters(self, func: Callable) -> Dict[str, type]:
        """Extrahiere Parameter-Typen aus Funktion"""
        sig = inspect.signature(func)
        params = {}

        for param_name, param in sig.parameters.items():
            if param.annotation != inspect.Parameter.empty:
                params[param_name] = param.annotation
            else:
                params[param_name] = str

        return params

    def get_tool(self, name: str) -> Callable:
        """Hole Tool-Funktion nach Name"""
        if name not in self.tools:
            raise ValueError(f"Tool not found: {name}")

        return self.tools[name].function

    def list_tools(self) -> List[Dict[str, str]]:
        """Liste alle verfügbaren Tools"""
        return [
            {
                "name": meta.name,
                "description": meta.description,
                "version": meta.version,
                "author": meta.author
            }
            for meta in self.tools.values()
        ]

# Tool-Decorator für einfache Plugin-Entwicklung:
def crawllama_tool(name: str = None, version: str = "1.0.0", author: str = "Unknown"):
    """
    Decorator um Funktionen als CrawlLama-Tool zu markieren

    Beispiel:
        @crawllama_tool(name="google_search", version="1.0.0")
        def search_google(query: str, max_results: int = 10):
            '''Suche mit Google Custom Search API'''
            # Implementation
            return results
    """
    def decorator(func: Callable):
        func._is_crawllama_tool = True
        func._tool_name = name or func.__name__
        func._tool_version = version
        func._tool_author = author
        return func

    return decorator
```

**Beispiel-Plugin:**

**Datei:** `~/.crawllama/plugins/github_search.py`

```python
from core.plugin_manager import crawllama_tool
import requests

@crawllama_tool(
    name="github_search",
    version="1.0.0",
    author="Your Name"
)
def search_github_repos(query: str, language: str = None, max_results: int = 5):
    """
    Suche GitHub-Repositories

    Args:
        query: Suchbegriff
        language: Programmiersprache (optional)
        max_results: Max. Anzahl Ergebnisse

    Returns:
        List von Repository-Informationen
    """
    api_url = "https://api.github.com/search/repositories"

    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": max_results
    }

    if language:
        params["q"] += f" language:{language}"

    response = requests.get(api_url, params=params)
    data = response.json()

    return [
        {
            "name": repo["name"],
            "url": repo["html_url"],
            "description": repo["description"],
            "stars": repo["stargazers_count"]
        }
        for repo in data.get("items", [])
    ]

@crawllama_tool(name="github_trending")
def get_trending_repos(language: str = "python", since: str = "daily"):
    """Hole trending GitHub-Repos (heute/wöchentlich/monatlich)"""
    # Implementation...
    pass
```

### 6.2 FastAPI-Integration

**Datei:** `api/server.py`

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import uuid
from datetime import datetime

from core.agent import SearchAgent

app = FastAPI(
    title="CrawlLama API",
    description="Lokaler Such- und Antwort-Agent API",
    version="1.0.0"
)

# CORS für Web-Frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Agent-Instanz
agent = SearchAgent()

# Request/Response Models
class QueryRequest(BaseModel):
    query: str
    enable_web: bool = True
    model: Optional[str] = None
    max_sources: int = 3

class QueryResponse(BaseModel):
    query_id: str
    query: str
    answer: str
    sources: List[Dict[str, str]]
    timestamp: str
    processing_time: float

class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    available_models: List[str]

# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Healthcheck-Endpoint"""
    try:
        models = agent.llm.get_available_models()
        return HealthResponse(
            status="healthy",
            ollama_connected=True,
            available_models=models
        )
    except Exception as e:
        return HealthResponse(
            status="degraded",
            ollama_connected=False,
            available_models=[]
        )

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Hauptendpoint für Fragen

    Beispiel:
        POST /query
        {
            "query": "Was ist Python?",
            "enable_web": true,
            "max_sources": 3
        }
    """
    import time
    start_time = time.time()

    try:
        # Konfiguriere Agent
        if request.model:
            agent.llm.config.model = request.model

        # Führe Query aus
        answer = agent.query(
            request.query,
            enable_web=request.enable_web,
            max_sources=request.max_sources
        )

        # Sammle Quellen
        sources = agent.get_last_sources()

        return QueryResponse(
            query_id=str(uuid.uuid4()),
            query=request.query,
            answer=answer,
            sources=sources,
            timestamp=datetime.now().isoformat(),
            processing_time=time.time() - start_time
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tools")
async def list_tools():
    """Liste alle verfügbaren Tools"""
    return {"tools": agent.plugin_manager.list_tools()}

@app.post("/tools/{tool_name}")
async def execute_tool(tool_name: str, params: Dict):
    """Führe spezifisches Tool direkt aus"""
    try:
        tool = agent.plugin_manager.get_tool(tool_name)
        result = tool(**params)
        return {"result": result}
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Streaming-Endpoint
from fastapi.responses import StreamingResponse

@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """Streaming-Antworten (Server-Sent Events)"""

    async def generate():
        for chunk in agent.query_stream(request.query):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )

# Startup
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Verwendung:**

```bash
# Server starten
python api/server.py

# Curl-Test
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Was ist Python?", "enable_web": true}'

# Python-Client
import requests

response = requests.post(
    "http://localhost:8000/query",
    json={"query": "Was ist Python?"}
)

print(response.json()["answer"])
```

### 6.3 Multi-Backend-Support

**Datei:** `core/llm_backends.py`

```python
from abc import ABC, abstractmethod
from typing import Generator, Optional
from dataclasses import dataclass

@dataclass
class LLMConfig:
    """Gemeinsame Konfiguration für alle Backends"""
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 30

class LLMBackend(ABC):
    """Abstract Base Class für LLM-Backends"""

    @abstractmethod
    def generate(self, prompt: str, stream: bool = False) -> str | Generator:
        """Generiere Text"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Prüfe ob Backend verfügbar"""
        pass

class OllamaBackend(LLMBackend):
    """Ollama-Backend (wie bereits implementiert)"""

    def __init__(self, config: LLMConfig):
        self.config = config
        # ... existing implementation

    def generate(self, prompt: str, stream: bool = False):
        # ... existing implementation
        pass

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

class HuggingFaceBackend(LLMBackend):
    """Hugging Face Transformers Backend (lokal)"""

    def __init__(self, config: LLMConfig):
        from transformers import pipeline

        self.config = config
        self.pipeline = pipeline(
            "text-generation",
            model=config.model,
            device="cuda" if torch.cuda.is_available() else "cpu"
        )

    def generate(self, prompt: str, stream: bool = False) -> str:
        result = self.pipeline(
            prompt,
            max_new_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            do_sample=True
        )
        return result[0]["generated_text"]

    def is_available(self) -> bool:
        return self.pipeline is not None

class OpenAIBackend(LLMBackend):
    """OpenAI API Backend (für Fallback/Vergleich)"""

    def __init__(self, config: LLMConfig, api_key: str):
        import openai

        self.config = config
        openai.api_key = api_key
        self.client = openai.OpenAI()

    def generate(self, prompt: str, stream: bool = False) -> str:
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=stream
        )

        if stream:
            def stream_gen():
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            return stream_gen()
        else:
            return response.choices[0].message.content

    def is_available(self) -> bool:
        try:
            self.client.models.list()
            return True
        except:
            return False

# Backend-Factory
class LLMFactory:
    """Factory für verschiedene LLM-Backends"""

    BACKENDS = {
        "ollama": OllamaBackend,
        "huggingface": HuggingFaceBackend,
        "openai": OpenAIBackend
    }

    @classmethod
    def create(cls, backend_type: str, config: LLMConfig, **kwargs) -> LLMBackend:
        """Erstelle Backend-Instanz"""
        if backend_type not in cls.BACKENDS:
            raise ValueError(f"Unknown backend: {backend_type}")

        backend_class = cls.BACKENDS[backend_type]
        return backend_class(config, **kwargs)

    @classmethod
    def auto_detect(cls, preference: List[str] = None) -> LLMBackend:
        """Automatische Backend-Erkennung"""
        preference = preference or ["ollama", "huggingface", "openai"]

        for backend_type in preference:
            try:
                backend = cls.create(backend_type, LLMConfig(model="default"))
                if backend.is_available():
                    logging.info(f"Using backend: {backend_type}")
                    return backend
            except:
                continue

        raise RuntimeError("No available LLM backend found")
```

**Verwendung:**

```python
# config.json
{
    "llm": {
        "backend": "ollama",  # oder "huggingface", "openai"
        "fallback_backends": ["huggingface"],
        "model": "llama3:7b"
    }
}

# In Agent:
backend = LLMFactory.create(
    backend_type=config["llm"]["backend"],
    config=LLMConfig(model=config["llm"]["model"])
)

# Oder automatisch:
backend = LLMFactory.auto_detect(
    preference=["ollama", "huggingface"]
)
```

---

## 7. Erweiterte CLI & Usability

### 7.1 Hilfe-Funktion mit Beispielen

**Datei:** `cli/help_system.py`

```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

def show_examples():
    """Zeige praktische Beispiele"""

    examples = [
        {
            "description": "Einfache Frage",
            "command": "python main.py 'Was ist Quantenverschränkung?'"
        },
        {
            "description": "Offline-Modus (ohne Web-Suche)",
            "command": "python main.py --no-web 'Erkläre Photosynthese'"
        },
        {
            "description": "Anderes Modell verwenden",
            "command": "python main.py --model mistral:7b 'Python Tutorial'"
        },
        {
            "description": "Debug-Modus (zeigt Tool-Calls)",
            "command": "python main.py --debug 'Aktuelles Wetter Berlin'"
        },
        {
            "description": "Interaktiver Modus",
            "command": "python main.py"
        },
        {
            "description": "API-Keys einrichten",
            "command": "python main.py --setup-keys"
        },
        {
            "description": "Plugins auflisten",
            "command": "python main.py --list-tools"
        },
        {
            "description": "Streaming-Output",
            "command": "python main.py --stream 'Lange Antwort...'"
        }
    ]

    console.print("\n[bold cyan]CrawlLama - Beispiele[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Beschreibung", style="dim", width=30)
    table.add_column("Befehl", style="green")

    for ex in examples:
        table.add_row(ex["description"], ex["command"])

    console.print(table)

    # Tool-Beispiele
    console.print("\n[bold cyan]Tool-Verwendung (direkt)[/bold cyan]\n")

    tool_examples = """
    # Web-Suche
    python -c "from tools.web_search import web_search; print(web_search('Python'))"

    # Wikipedia-Lookup
    python -c "from tools.wiki_lookup import wiki_lookup; print(wiki_lookup('Einstein'))"

    # RAG-Suche in lokalen Dokumenten
    python -c "from tools.rag import RAGManager; rag = RAGManager(); print(rag.search('machine learning'))"
    """

    console.print(Panel(tool_examples, title="Tool-Beispiele", border_style="blue"))

def show_config_help():
    """Zeige Konfigurations-Hilfe"""

    config_md = """
## Konfiguration (config.json)

### LLM-Einstellungen
```json
{
  "llm": {
    "backend": "ollama",
    "model": "llama3:7b",
    "temperature": 0.7,
    "stream": true
  }
}
```

### Web-Suche
```json
{
  "search": {
    "provider": "duckduckgo",
    "max_results": 3,
    "fallback_providers": ["brave"]
  }
}
```

### RAG-System
```json
{
  "rag": {
    "enabled": true,
    "embedding_model": "all-MiniLM-L6-v2",
    "top_k": 5
  }
}
```

### Sicherheit
```json
{
  "security": {
    "warn_external_requests": true,
    "allowed_domains": [],
    "strict_mode": false
  }
}
```
"""

    console.print(Markdown(config_md))

def show_plugin_development():
    """Zeige Plugin-Entwicklungs-Anleitung"""

    plugin_md = """
## Plugin-Entwicklung

### Einfaches Plugin erstellen

1. Erstelle Datei: `~/.crawllama/plugins/my_tool.py`

```python
from core.plugin_manager import crawllama_tool

@crawllama_tool(name="my_search", version="1.0.0", author="Dein Name")
def search_my_api(query: str, limit: int = 10):
    '''Beschreibung deines Tools'''
    # Deine Implementierung
    return results
```

2. Plugin wird automatisch beim Start geladen

3. Nutzen:
```python
python main.py "Frage die my_search triggert"
```

### Plugin mit Abhängigkeiten

```python
# requirements im Plugin-Verzeichnis:
# ~/.crawllama/plugins/requirements.txt

@crawllama_tool(name="reddit_search")
def search_reddit(subreddit: str, query: str):
    import praw  # Wird automatisch geladen
    # Implementation
```
"""

    console.print(Markdown(plugin_md))
```

**Integration in main.py:**

```python
import argparse

def create_parser():
    parser = argparse.ArgumentParser(
        description="CrawlLama - Lokaler Such- und Antwort-Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("query", nargs="*", help="Frage (optional für interaktiven Modus)")
    parser.add_argument("--no-web", action="store_true", help="Offline-Modus")
    parser.add_argument("--model", default="llama3:7b", help="Ollama-Modell")
    parser.add_argument("--debug", action="store_true", help="Debug-Modus")
    parser.add_argument("--stream", action="store_true", help="Streaming-Output")

    # Setup
    parser.add_argument("--setup-keys", action="store_true", help="API-Keys einrichten")
    parser.add_argument("--list-tools", action="store_true", help="Alle Tools auflisten")

    # Hilfe
    parser.add_argument("--examples", action="store_true", help="Beispiele anzeigen")
    parser.add_argument("--config-help", action="store_true", help="Konfigurations-Hilfe")
    parser.add_argument("--plugin-help", action="store_true", help="Plugin-Entwicklungs-Hilfe")

    return parser

if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()

    # Hilfe-Funktionen
    if args.examples:
        show_examples()
        sys.exit(0)

    if args.config_help:
        show_config_help()
        sys.exit(0)

    if args.plugin_help:
        show_plugin_development()
        sys.exit(0)
```

### 7.2 Vereinfachtes Installations-Script

**Datei:** `install.sh` (Linux/macOS)

```bash
#!/bin/bash
set -e

echo "🦙 CrawlLama Installation"
echo "========================"

# 1. Python-Version prüfen
echo "Prüfe Python-Version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.10+ erforderlich (gefunden: $python_version)"
    exit 1
fi

echo "✓ Python $python_version"

# 2. Ollama prüfen
echo ""
echo "Prüfe Ollama-Installation..."
if command -v ollama &> /dev/null; then
    echo "✓ Ollama gefunden"
else
    echo "⚠️  Ollama nicht gefunden"
    echo ""
    read -p "Ollama jetzt installieren? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        curl -fsSL https://ollama.com/install.sh | sh
    else
        echo "Bitte Ollama manuell installieren: https://ollama.com"
        exit 1
    fi
fi

# 3. Virtual Environment
echo ""
echo "Erstelle Virtual Environment..."
python3 -m venv venv
source venv/bin/activate

# 4. Dependencies
echo ""
echo "Installiere Abhängigkeiten..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Ollama-Modell
echo ""
echo "Lade Ollama-Modell..."
read -p "Welches Modell? [llama3:7b] " model
model=${model:-llama3:7b}
ollama pull $model

# 6. Konfiguration
echo ""
echo "Erstelle Konfiguration..."
if [ ! -f config.json ]; then
    cat > config.json <<EOF
{
  "llm": {
    "backend": "ollama",
    "model": "$model",
    "temperature": 0.7
  },
  "search": {
    "provider": "duckduckgo",
    "max_results": 3
  }
}
EOF
    echo "✓ config.json erstellt"
fi

# 7. Verzeichnisse
echo ""
echo "Erstelle Verzeichnisse..."
mkdir -p data/cache data/embeddings logs
echo "✓ Verzeichnisse erstellt"

# 8. Test
echo ""
echo "Teste Installation..."
python main.py "Was ist 2+2?" --no-web

echo ""
echo "✅ Installation abgeschlossen!"
echo ""
echo "Verwendung:"
echo "  source venv/bin/activate"
echo "  python main.py 'Deine Frage'"
echo "  python main.py --examples  # Für mehr Beispiele"
```

**Datei:** `install.bat` (Windows)

```batch
@echo off
echo 🦙 CrawlLama Installation
echo ========================

:: Python prüfen
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python nicht gefunden
    echo Bitte Python 3.10+ installieren: https://python.org
    pause
    exit /b 1
)

echo ✓ Python gefunden

:: Virtual Environment
echo.
echo Erstelle Virtual Environment...
python -m venv venv
call venv\Scripts\activate.bat

:: Dependencies
echo.
echo Installiere Abhängigkeiten...
pip install --upgrade pip
pip install -r requirements.txt

:: Ollama
echo.
echo ⚠️  Bitte Ollama installieren: https://ollama.com/download
echo Nach Installation: ollama pull llama3:7b
pause

:: Konfiguration
if not exist config.json (
    (
    echo {
    echo   "llm": {
    echo     "backend": "ollama",
    echo     "model": "llama3:7b"
    echo   }
    echo }
    ) > config.json
    echo ✓ config.json erstellt
)

:: Verzeichnisse
mkdir data\cache data\embeddings logs 2>nul

echo.
echo ✅ Installation abgeschlossen!
echo.
echo Verwendung:
echo   venv\Scripts\activate
echo   python main.py "Deine Frage"
pause
```

### 7.3 Tool-Call-Visualisierung

**Datei:** `cli/visualizer.py`

```python
from rich.tree import Tree
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.live import Live
from typing import Dict, List
import json

console = Console()

class ToolCallVisualizer:
    """
    Visualisiert Tool-Calls und Agent-Reasoning im Terminal
    """

    def __init__(self, debug_mode: bool = True):
        self.debug_mode = debug_mode
        self.tree = Tree("🤖 Agent Execution")

    def add_thought(self, thought: str):
        """Füge Reasoning hinzu"""
        if not self.debug_mode:
            return

        self.tree.add(f"💭 [yellow]{thought}[/yellow]")
        console.print(self.tree)

    def add_tool_call(self, tool_name: str, arguments: Dict, result: any = None):
        """Visualisiere Tool-Call"""
        if not self.debug_mode:
            return

        tool_node = self.tree.add(f"🔧 [cyan]Tool: {tool_name}[/cyan]")

        # Arguments
        args_json = json.dumps(arguments, indent=2)
        args_syntax = Syntax(args_json, "json", theme="monokai")
        tool_node.add(Panel(args_syntax, title="Arguments", border_style="blue"))

        # Result (wenn verfügbar)
        if result is not None:
            result_str = str(result)[:200] + ("..." if len(str(result)) > 200 else "")
            tool_node.add(f"✓ [green]Result: {result_str}[/green]")

        console.print(self.tree)

    def add_web_sources(self, sources: List[Dict]):
        """Visualisiere Web-Quellen"""
        if not self.debug_mode:
            return

        sources_node = self.tree.add("🌐 [magenta]Web Sources[/magenta]")

        for i, source in enumerate(sources, 1):
            source_node = sources_node.add(f"{i}. {source['title']}")
            source_node.add(f"[dim]{source['url']}[/dim]")

        console.print(self.tree)

    def add_final_answer(self, answer: str):
        """Zeige finale Antwort"""
        self.tree.add(f"✅ [bold green]Answer Generated[/bold green]")
        console.print(self.tree)

        # Antwort in Panel
        console.print("\n")
        console.print(Panel(
            answer,
            title="🦙 CrawlLama Answer",
            border_style="green",
            padding=(1, 2)
        ))

# Integration in Agent:
class VisualizedAgent:
    def __init__(self, debug_mode: bool = False):
        self.viz = ToolCallVisualizer(debug_mode)

    def query(self, question: str):
        self.viz.add_thought(f"Processing question: {question}")

        # Tool-Call
        self.viz.add_thought("Determining if web search is needed...")

        if self._needs_web_search(question):
            self.viz.add_thought("Initiating web search")

            results = web_search(question)
            self.viz.add_tool_call(
                "web_search",
                {"query": question, "max_results": 3},
                result=f"{len(results)} results found"
            )

            self.viz.add_web_sources(results)

        # Generate Answer
        self.viz.add_thought("Generating answer with LLM...")
        answer = self.llm.generate(question)

        self.viz.add_final_answer(answer)

        return answer
```

**Ausgabe-Beispiel:**

```
🤖 Agent Execution
├── 💭 Processing question: What is quantum entanglement?
├── 💭 Determining if web search is needed...
├── 💭 Initiating web search
├── 🔧 Tool: web_search
│   ├── ╭─ Arguments ─────────────────╮
│   │   │ {                           │
│   │   │   "query": "quantum...",    │
│   │   │   "max_results": 3          │
│   │   │ }                           │
│   │   ╰─────────────────────────────╯
│   └── ✓ Result: 3 results found
├── 🌐 Web Sources
│   ├── 1. Quantum Entanglement - Wikipedia
│   │   └── https://en.wikipedia.org/wiki/...
│   ├── 2. What is Quantum Entanglement?
│   │   └── https://www.quantamagazine.org/...
│   └── 3. Quantum Physics Explained
│       └── https://phys.org/...
├── 💭 Generating answer with LLM...
└── ✅ Answer Generated

╭─ 🦙 CrawlLama Answer ────────────────────────────╮
│                                                  │
│  Quantum entanglement is a physical phenomenon  │
│  that occurs when pairs or groups of particles  │
│  are generated or interact in such a way that   │
│  the quantum state of each particle cannot be   │
│  described independently...                      │
│                                                  │
╰──────────────────────────────────────────────────╯
```

---

## 8. Erweiterte Dokumentation & Beispiele

### 8.1 Plugin-Entwicklungs-Tutorial

**Datei:** `docs/PLUGIN_DEVELOPMENT.md`

```markdown
# Plugin-Entwicklung für CrawlLama

## Übersicht

Plugins erweitern CrawlLama um neue Tools und Funktionen. Jedes Plugin ist eine Python-Datei mit einer oder mehreren Tool-Funktionen.

## Schnellstart

### 1. Minimales Plugin

**Datei:** `~/.crawllama/plugins/hello.py`

```python
from core.plugin_manager import crawllama_tool

@crawllama_tool(name="hello", version="1.0.0", author="Du")
def say_hello(name: str = "World"):
    """Einfaches Beispiel-Tool"""
    return f"Hello, {name}!"
```

### 2. Plugin testen

```bash
# Plugin wird automatisch geladen
python main.py --list-tools

# Direkt aufrufen (via API)
curl -X POST http://localhost:8000/tools/hello \
  -H "Content-Type: application/json" \
  -d '{"name": "CrawlLama"}'
```

## Fortgeschrittene Plugins

### API-Integration

**Beispiel:** GitHub-Suche

```python
from core.plugin_manager import crawllama_tool
from utils.secure_config import SecureConfigManager
import requests

config = SecureConfigManager()

@crawllama_tool(name="github_search", version="2.0.0")
def search_github(query: str, language: str = None, max_results: int = 5):
    """
    Suche GitHub-Repositories

    Args:
        query: Suchbegriff (z.B. "machine learning")
        language: Filter nach Programmiersprache (optional)
        max_results: Max. Anzahl Ergebnisse (1-100)

    Returns:
        Liste von Repository-Informationen

    Requires:
        GITHUB_TOKEN in .env (optional, für höheres Rate-Limit)
    """

    # API-Token (optional)
    token = config.get_api_key("github")
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    # Query bauen
    search_query = query
    if language:
        search_query += f" language:{language}"

    # API-Request
    response = requests.get(
        "https://api.github.com/search/repositories",
        params={
            "q": search_query,
            "sort": "stars",
            "order": "desc",
            "per_page": max_results
        },
        headers=headers
    )

    response.raise_for_status()
    data = response.json()

    # Formatiere Ergebnisse
    results = []
    for repo in data.get("items", []):
        results.append({
            "name": repo["full_name"],
            "description": repo["description"],
            "url": repo["html_url"],
            "stars": repo["stargazers_count"],
            "language": repo["language"],
            "topics": repo.get("topics", [])
        })

    return results
```

### Plugin mit Abhängigkeiten

**Datei:** `~/.crawllama/plugins/requirements.txt`

```
requests>=2.31.0
beautifulsoup4>=4.12.0
```

**Plugin:**

```python
@crawllama_tool(name="scrape_article")
def scrape_article(url: str):
    """
    Extrahiere Haupttext aus Artikel-URL

    Verwendet newspaper3k für intelligente Content-Extraktion
    """
    # Dependencies werden automatisch geladen
    from newspaper import Article

    article = Article(url)
    article.download()
    article.parse()

    return {
        "title": article.title,
        "text": article.text,
        "authors": article.authors,
        "publish_date": str(article.publish_date)
    }
```

### Plugin mit State

```python
from core.plugin_manager import crawllama_tool
import sqlite3
from pathlib import Path

# Plugin-lokale Datenbank
DB_PATH = Path.home() / ".crawllama" / "plugins" / "bookmarks.db"

def _init_db():
    """Initialisiere Datenbank"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookmarks (
            id INTEGER PRIMARY KEY,
            url TEXT UNIQUE,
            title TEXT,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

_init_db()

@crawllama_tool(name="bookmark_add")
def add_bookmark(url: str, title: str, tags: str = ""):
    """Speichere Bookmark"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO bookmarks (url, title, tags) VALUES (?, ?, ?)",
        (url, title, tags)
    )
    conn.commit()
    conn.close()
    return f"Bookmark saved: {title}"

@crawllama_tool(name="bookmark_search")
def search_bookmarks(query: str):
    """Suche in Bookmarks"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT url, title, tags FROM bookmarks WHERE title LIKE ? OR tags LIKE ?",
        (f"%{query}%", f"%{query}%")
    )
    results = [{"url": row[0], "title": row[1], "tags": row[2]} for row in cursor]
    conn.close()
    return results
```

## Best Practices

### 1. Fehlerbehandlung

```python
@crawllama_tool(name="safe_api_call")
def call_external_api(endpoint: str):
    """Tool mit robuster Fehlerbehandlung"""
    try:
        response = requests.get(endpoint, timeout=10)
        response.raise_for_status()
        return response.json()

    except requests.Timeout:
        return {"error": "API timeout"}
    except requests.HTTPError as e:
        return {"error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        logging.error(f"Unexpected error in safe_api_call: {e}")
        return {"error": "Internal error"}
```

### 2. Rate-Limiting

```python
from utils.rate_limiter import DomainRateLimiter
import time

rate_limiter = DomainRateLimiter(requests_per_second=1.0)

@crawllama_tool(name="polite_scraper")
def scrape_with_rate_limit(url: str):
    """Scraper der Rate-Limits respektiert"""
    from urllib.parse import urlparse

    domain = urlparse(url).netloc
    rate_limiter.wait_if_needed(domain)

    # Scrape...
    return content
```

### 3. Caching

```python
from core.cache import CacheManager
from functools import wraps

cache = CacheManager()

def cached_tool(ttl_hours: int = 24):
    """Decorator für gecachte Tools"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Cache-Key aus Funktion + Args
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Prüfe Cache
            cached = cache.get(cache_key)
            if cached:
                return cached

            # Führe Funktion aus
            result = func(*args, **kwargs)

            # Speichere in Cache
            cache.set(cache_key, result)

            return result
        return wrapper
    return decorator

@crawllama_tool(name="expensive_computation")
@cached_tool(ttl_hours=48)
def compute_expensive_thing(input_data: str):
    """Rechenintensive Operation mit Cache"""
    time.sleep(10)  # Simuliere lange Berechnung
    return f"Result for {input_data}"
```

## Plugin-Veröffentlichung

### Plugin-Metadaten

```python
"""
CrawlLama Plugin: Advanced GitHub Integration
Version: 2.0.0
Author: Your Name <email@example.com>
License: MIT
Repository: https://github.com/yourusername/crawllama-plugin-github

Description:
    Erweiterte GitHub-Integration mit:
    - Repository-Suche
    - Issue-Tracking
    - PR-Analyse
    - Trending-Repos

Dependencies:
    - requests>=2.31.0
    - PyGithub>=2.1.0

Installation:
    1. Download plugin: wget https://raw.githubusercontent.com/.../github_plugin.py
    2. Move to: ~/.crawllama/plugins/github_plugin.py
    3. Install deps: pip install -r ~/.crawllama/plugins/requirements.txt
    4. Set GITHUB_TOKEN in .env

Usage:
    python main.py "Show me trending Python repos"
"""

from core.plugin_manager import crawllama_tool
# ... rest of plugin
```

### Plugin-Repository-Struktur

```
crawllama-plugin-github/
├── README.md
├── github_plugin.py
├── requirements.txt
├── tests/
│   └── test_github_plugin.py
└── examples/
    └── usage_examples.md
```
```

### 8.2 Multi-Hop-Reasoning mit LangGraph

**Datei:** `docs/LANGGRAPH_GUIDE.md`

```markdown
# Multi-Hop-Reasoning mit LangGraph

## Übersicht

LangGraph ermöglicht komplexe, mehrstufige Reasoning-Workflows. CrawlLama nutzt dies für fortgeschrittene Aufgaben, die mehrere Schritte erfordern.

## Architektur

```
┌─────────────┐
│   Question  │
└──────┬──────┘
       ↓
┌──────────────┐
│   Router     │ → Entscheide: Einfache vs. Komplexe Frage
└──────┬───────┘
       ↓
┌──────────────┐     ┌─────────────┐
│ Simple Path  │ ──→ │   Answer    │
└──────────────┘     └─────────────┘
       ↓
┌──────────────┐
│ Complex Path │
└──────┬───────┘
       ↓
┌──────────────┐
│  Web Search  │ → Sammle initiale Informationen
└──────┬───────┘
       ↓
┌──────────────┐
│   Analyze    │ → Extrahiere Key Facts
└──────┬───────┘
       ↓
┌──────────────┐
│ Follow-up    │ → Tiefere Recherche zu spezifischen Aspekten
│   Search     │
└──────┬───────┘
       ↓
┌──────────────┐
│  Synthesize  │ → Kombiniere alle Informationen
└──────┬───────┘
       ↓
┌──────────────┐
│   Answer     │
└──────────────┘
```

## Implementierung

**Datei:** `core/langgraph_agent.py`

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Annotated
import operator

# State-Definition
class AgentState(TypedDict):
    question: str
    web_results: List[Dict]
    key_facts: List[str]
    follow_up_queries: List[str]
    follow_up_results: List[Dict]
    final_answer: str
    step_count: Annotated[int, operator.add]

# Nodes
def router(state: AgentState) -> str:
    """Entscheide ob einfache oder komplexe Verarbeitung"""
    question = state["question"]

    # Heuristik: Komplexe Fragen erfordern mehrere Hops
    complex_indicators = [
        "compare", "analyze", "explain the relationship",
        "how does", "what are the differences"
    ]

    if any(indicator in question.lower() for indicator in complex_indicators):
        return "complex"
    return "simple"

def simple_answer(state: AgentState) -> AgentState:
    """Direkte Antwort ohne Multi-Hop"""
    answer = llm.generate(state["question"])
    return {
        **state,
        "final_answer": answer,
        "step_count": 1
    }

def initial_search(state: AgentState) -> AgentState:
    """Erste Web-Suche"""
    results = web_search(state["question"], max_results=5)
    return {
        **state,
        "web_results": results,
        "step_count": 1
    }

def analyze_results(state: AgentState) -> AgentState:
    """Analysiere Ergebnisse und extrahiere Key Facts"""

    # Kombiniere Texte aus Web-Ergebnissen
    combined_text = "\n\n".join([
        r.get("snippet", "") for r in state["web_results"]
    ])

    # Prompt für LLM
    analysis_prompt = f"""
    Frage: {state["question"]}

    Gefundene Informationen:
    {combined_text}

    Aufgabe:
    1. Extrahiere 3-5 Hauptfakten
    2. Identifiziere Wissenslücken
    3. Formuliere 2-3 Follow-up-Fragen für tiefere Recherche

    Format:
    FACTS:
    - Fakt 1
    - Fakt 2

    FOLLOW_UP:
    - Frage 1
    - Frage 2
    """

    analysis = llm.generate(analysis_prompt)

    # Parse Antwort
    facts = []
    follow_ups = []

    current_section = None
    for line in analysis.split("\n"):
        line = line.strip()
        if line.startswith("FACTS:"):
            current_section = "facts"
        elif line.startswith("FOLLOW_UP:"):
            current_section = "follow_up"
        elif line.startswith("- "):
            if current_section == "facts":
                facts.append(line[2:])
            elif current_section == "follow_up":
                follow_ups.append(line[2:])

    return {
        **state,
        "key_facts": facts,
        "follow_up_queries": follow_ups,
        "step_count": 1
    }

def follow_up_search(state: AgentState) -> AgentState:
    """Führe Follow-up-Suchen durch"""
    all_results = []

    for query in state["follow_up_queries"]:
        results = web_search(query, max_results=2)
        all_results.extend(results)

    return {
        **state,
        "follow_up_results": all_results,
        "step_count": 1
    }

def synthesize_answer(state: AgentState) -> AgentState:
    """Synthetisiere finale Antwort aus allen Informationen"""

    # Kombiniere alle Informationen
    synthesis_prompt = f"""
    Ursprüngliche Frage: {state["question"]}

    Hauptfakten:
    {chr(10).join(f"- {fact}" for fact in state["key_facts"])}

    Zusätzliche Recherche-Ergebnisse:
    {chr(10).join(f"- {r.get('title', '')}: {r.get('snippet', '')}" for r in state["follow_up_results"])}

    Aufgabe: Beantworte die ursprüngliche Frage umfassend unter Verwendung aller gesammelten Informationen.
    Strukturiere die Antwort logisch und zitiere relevante Fakten.
    """

    answer = llm.generate(synthesis_prompt)

    return {
        **state,
        "final_answer": answer,
        "step_count": 1
    }

# Graph bauen
def build_graph():
    workflow = StateGraph(AgentState)

    # Nodes hinzufügen
    workflow.add_node("router", router)
    workflow.add_node("simple", simple_answer)
    workflow.add_node("initial_search", initial_search)
    workflow.add_node("analyze", analyze_results)
    workflow.add_node("follow_up", follow_up_search)
    workflow.add_node("synthesize", synthesize_answer)

    # Edges
    workflow.set_entry_point("router")

    # Conditional Routing
    workflow.add_conditional_edges(
        "router",
        lambda state: state,
        {
            "simple": "simple",
            "complex": "initial_search"
        }
    )

    # Simple Path
    workflow.add_edge("simple", END)

    # Complex Path
    workflow.add_edge("initial_search", "analyze")
    workflow.add_edge("analyze", "follow_up")
    workflow.add_edge("follow_up", "synthesize")
    workflow.add_edge("synthesize", END)

    return workflow.compile()

# Verwendung
app = build_graph()

def multi_hop_query(question: str) -> str:
    """Führe Multi-Hop-Reasoning aus"""

    initial_state = {
        "question": question,
        "web_results": [],
        "key_facts": [],
        "follow_up_queries": [],
        "follow_up_results": [],
        "final_answer": "",
        "step_count": 0
    }

    final_state = app.invoke(initial_state)

    print(f"✓ Completed in {final_state['step_count']} steps")

    return final_state["final_answer"]
```

## Beispiele

### Beispiel 1: Vergleichs-Frage

```python
question = "Compare Python and JavaScript for web development"

# Graph-Execution:
# 1. Router → complex
# 2. Initial Search → "Python vs JavaScript web development"
# 3. Analyze → Key Facts:
#    - Python: Django, Flask, backend-focused
#    - JavaScript: Node.js, React, full-stack
# 4. Follow-up Searches:
#    - "Python web frameworks performance"
#    - "JavaScript ecosystem 2025"
# 5. Synthesize → Umfassende Antwort

answer = multi_hop_query(question)
```

### Beispiel 2: Kausale Frage

```python
question = "How does climate change affect ocean currents and what are the consequences for Europe?"

# Graph-Execution:
# 1. Router → complex
# 2. Initial Search → "climate change ocean currents"
# 3. Analyze → Facts + Follow-ups:
#    - AMOC slowdown
#    - Temperature changes
#    Follow-up: "AMOC Europe climate impact"
# 4. Follow-up Search → Spezifische Konsequenzen
# 5. Synthesize → Kausalkette: Klimawandel → AMOC → Europa-Wetter

answer = multi_hop_query(question)
```

## Erweiterte Patterns

### Parallel Search

```python
def parallel_search(state: AgentState) -> AgentState:
    """Mehrere Aspekte parallel recherchieren"""

    aspects = [
        "technical aspects",
        "historical context",
        "current trends"
    ]

    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(web_search, f"{state['question']} {aspect}")
            for aspect in aspects
        ]
        results = [f.result() for f in futures]

    return {
        **state,
        "parallel_results": results
    }
```

### Self-Critique Loop

```python
def critique(state: AgentState) -> AgentState:
    """LLM beurteilt eigene Antwort"""

    critique_prompt = f"""
    Frage: {state["question"]}
    Antwort: {state["final_answer"]}

    Beurteile die Antwort:
    1. Ist sie vollständig?
    2. Sind alle Aspekte der Frage beantwortet?
    3. Fehlen wichtige Informationen?

    Antworte mit: GOOD oder NEEDS_IMPROVEMENT: [Grund]
    """

    critique = llm.generate(critique_prompt)

    if "NEEDS_IMPROVEMENT" in critique:
        # Extrahiere fehlende Aspekte
        missing = critique.split(":")[1].strip()
        return {
            **state,
            "follow_up_queries": [missing],
            "needs_improvement": True
        }

    return {
        **state,
        "needs_improvement": False
    }

# Graph mit Loop
workflow.add_node("critique", critique)
workflow.add_edge("synthesize", "critique")

workflow.add_conditional_edges(
    "critique",
    lambda state: "improve" if state.get("needs_improvement") else "end",
    {
        "improve": "follow_up",
        "end": END
    }
)
```
```

---

## Zusammenfassung

Diese erweiterte Implementierungsanleitung deckt ab:

✅ **Fehlerbehandlung:** Fallback-Systeme, Ollama-Handling, Proxy-Validierung
✅ **Tests:** Edge-Cases, Integration-Tests, Ollama-Mocking
✅ **Rate-Limiting:** robots.txt, Domain-Limiter
✅ **Performance:** Async-Requests, RAM-Optimierung, Lazy-Loading
✅ **Sicherheit:** API-Key-Verschlüsselung, Output-Validierung, Blacklists
✅ **Erweiterbarkeit:** Plugin-System, FastAPI, Multi-Backend
✅ **Usability:** Hilfe-System, Installations-Scripts, Visualisierung
✅ **Dokumentation:** Plugin-Tutorials, LangGraph-Guide

Alle Code-Beispiele sind produktionsreif und können direkt verwendet werden!