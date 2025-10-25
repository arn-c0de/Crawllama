# Contributing to CrawlLama

Vielen Dank für dein Interesse, zu CrawlLama beizutragen! 🎉

Wir freuen uns über alle Arten von Beiträgen - ob Bug-Fixes, neue Features, Dokumentationsverbesserungen oder Tests.

---

📚 **Navigation:** [README](README.md) | [Docs](docs/README.md) | [Security](SECURITY.md) | [Changelog](CHANGELOG.md) | [Code of Conduct](CODE_OF_CONDUCT.md)

---

## 📋 Inhaltsverzeichnis

- [Code of Conduct](#code-of-conduct)
- [Wie kann ich beitragen?](#wie-kann-ich-beitragen)
- [Development Setup](#development-setup)
- [Pull Request Workflow](#pull-request-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Dokumentation](#dokumentation)
- [Commit Guidelines](#commit-guidelines)

## 📜 Code of Conduct

Dieses Projekt folgt dem [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). Mit deiner Teilnahme erklärst du dich damit einverstanden, diese Richtlinien einzuhalten.

## 🤝 Wie kann ich beitragen?

### 🐛 Bug Reports

Wenn du einen Bug findest:

1. **Prüfe**, ob das Problem bereits als [Issue](https://github.com/arn-c0de/Crawllama/issues) gemeldet wurde
2. **Erstelle ein neues Issue** mit:
   - Klarer Beschreibung des Problems
   - Schritte zur Reproduktion
   - Erwartetes vs. tatsächliches Verhalten
   - Python-Version, OS, relevante Logs
   - Code-Beispiel (wenn möglich)

**Beispiel für gutes Bug-Reporting:**
```markdown
**Bug:** Agent stürzt bei leerem Cache ab

**Schritte:**
1. Starte Agent mit `python main.py --interactive`
2. Führe `clear-cache` aus
3. Stelle eine Frage

**Erwartet:** Antwort wird generiert
**Tatsächlich:** KeyError in cache.py

**Environment:**
- Python 3.12
- Windows 11
- CrawlLama v1.3

**Logs:**
```
KeyError: 'cache_key' in cache.py:45
```
```

### 💡 Feature Requests

Für neue Features:

1. **Erstelle ein Issue** mit:
   - Klare Beschreibung des gewünschten Features
   - Use Case / Problem, das gelöst wird
   - Beispiel-Code oder Mockups (falls relevant)
   - Mögliche Implementierungsansätze

2. **Warte auf Feedback** vom Maintainer-Team
3. Nach Freigabe kannst du mit der Implementierung beginnen

### 🔧 Code Contributions

1. **Fork** das Repository
2. **Erstelle einen Feature Branch** (`git checkout -b feature/amazing-feature`)
3. **Implementiere** deine Änderungen
4. **Schreibe Tests** für neue Features
5. **Committe** deine Änderungen (siehe [Commit Guidelines](#commit-guidelines))
6. **Push** zum Branch (`git push origin feature/amazing-feature`)
7. **Erstelle einen Pull Request**

### 📖 Dokumentation

Dokumentationsverbesserungen sind immer willkommen:

- **README.md**: Installationsanleitung, Quickstart, Features
- **docs/**: Detaillierte Guides, Tutorials, API-Dokumentation
- **Docstrings**: Python-Code-Dokumentation
- **Code-Kommentare**: Erklärung komplexer Logik

## 🛠️ Development Setup

### Voraussetzungen

- Python 3.10+ (empfohlen: 3.12)
- Git
- Ollama (für LLM-Inferenz)
- Virtual Environment

### Setup-Schritte

```bash
# 1. Fork und Clone
git clone https://github.com/DEIN-USERNAME/Crawllama.git
cd Crawllama

# 2. Virtual Environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Development Dependencies
pip install pytest pytest-cov pytest-mock flake8 black mypy

# 5. Ollama Setup
ollama pull qwen2.5:3b

# 6. Konfiguration
cp .env.example .env
# Bearbeite .env mit deinen API-Keys (optional)

# 7. Test ausführen
pytest tests/ -v
```

### Alternative: Setup-Script

```bash
# Windows
setup.bat

# Linux/macOS
chmod +x setup.sh
./setup.sh
```

## 🔄 Pull Request Workflow

### 1. Branch-Naming

Verwende beschreibende Branch-Namen:

- `feature/` - Neue Features
- `fix/` - Bug-Fixes
- `docs/` - Dokumentation
- `test/` - Test-Verbesserungen
- `refactor/` - Code-Refactoring
- `chore/` - Maintenance-Tasks

**Beispiele:**
```bash
git checkout -b feature/add-google-search
git checkout -b fix/cache-corruption
git checkout -b docs/improve-readme
```

### 2. Pull Request Checklist

Bevor du einen PR erstellst, stelle sicher:

- [ ] **Code folgt den [Coding Standards](#coding-standards)**
- [ ] **Alle Tests laufen grün** (`pytest tests/`)
- [ ] **Neue Features haben Tests** (Coverage ≥ 80%)
- [ ] **Docstrings sind aktualisiert**
- [ ] **README.md ist aktualisiert** (bei neuen Features)
- [ ] **CHANGELOG.md ist aktualisiert**
- [ ] **Keine Secrets/API-Keys im Code**
- [ ] **Pre-commit Checks laufen durch** (falls eingerichtet)

### 3. PR-Template

Verwende folgende Struktur für deine PR-Beschreibung:

```markdown
## Beschreibung
[Kurze Zusammenfassung der Änderungen]

## Art der Änderung
- [ ] Bug-Fix (non-breaking change)
- [ ] New Feature (non-breaking change)
- [ ] Breaking Change (Fix oder Feature mit API-Änderung)
- [ ] Dokumentation

## Motivation und Context
[Warum ist diese Änderung notwendig? Welches Problem löst sie?]

## Wie wurde das getestet?
- [ ] Unit Tests
- [ ] Integration Tests
- [ ] Manuelle Tests

## Screenshots (falls relevant)
[Füge Screenshots hinzu für UI-Änderungen]

## Checklist
- [ ] Code folgt den Projekt-Standards
- [ ] Tests wurden hinzugefügt/aktualisiert
- [ ] Dokumentation wurde aktualisiert
- [ ] Alle Tests laufen grün
```

### 4. Review-Prozess

1. **Automatische Checks**: CI/CD läuft automatisch
2. **Code Review**: Mindestens 1 Approval erforderlich
3. **Diskussion**: Feedback wird im PR diskutiert
4. **Änderungen**: Bei Bedarf Anpassungen vornehmen
5. **Merge**: Nach Approval wird der PR gemerged

## 📝 Coding Standards

### Python Style Guide

Wir folgen **PEP 8** mit einigen Anpassungen:

#### Formatierung

- **Line Length**: Max. 100 Zeichen (Kommentare max. 80)
- **Indentation**: 4 Spaces (keine Tabs)
- **Encoding**: UTF-8
- **String Quotes**: Doppelte Quotes (`"`) bevorzugt

#### Naming Conventions

```python
# Classes: PascalCase
class SearchAgent:
    pass

# Functions/Methods: snake_case
def query_with_tools(query: str) -> str:
    pass

# Variables: snake_case
max_results = 5

# Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3

# Private Members: _leading_underscore
def _internal_function():
    pass
```

#### Type Hints

Verwende Type Hints für alle Funktionen:

```python
from typing import List, Dict, Optional

def search_web(
    query: str,
    max_results: int = 5,
    timeout: Optional[int] = None
) -> List[Dict[str, str]]:
    """
    Search the web for query.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
        timeout: Request timeout in seconds (optional)
    
    Returns:
        List of search results with title, url, snippet
    
    Raises:
        ValueError: If query is empty
        TimeoutError: If request times out
    """
    pass
```

#### Docstrings

Verwende **Google-Style Docstrings**:

```python
def process_results(results: List[Dict]) -> str:
    """
    Process search results into formatted text.
    
    This function takes raw search results and formats them
    into a human-readable string.
    
    Args:
        results: List of result dictionaries with 'title', 'url', 'snippet'
    
    Returns:
        Formatted string with numbered results
    
    Raises:
        ValueError: If results list is empty
    
    Example:
        >>> results = [{"title": "Example", "url": "http://...", "snippet": "..."}]
        >>> process_results(results)
        "1. Example\\nhttp://...\\n..."
    """
    pass
```

#### Imports

Sortiere Imports nach Standard:

```python
# 1. Standard Library
import sys
import os
from typing import List, Dict

# 2. Third-Party
import requests
from fastapi import FastAPI

# 3. Local
from core.agent import SearchAgent
from utils.logger import get_logger
```

#### Error Handling

```python
# Spezifische Exceptions verwenden
try:
    result = search_web(query)
except ValueError as e:
    logger.error(f"Invalid query: {e}")
    raise
except TimeoutError:
    logger.warning("Search timeout - using cache")
    result = get_cached_result(query)
```

### Code-Qualitäts-Tools

Wir empfehlen folgende Tools:

```bash
# Linting
flake8 core/ tools/ utils/ --max-line-length=100

# Type Checking
mypy core/ tools/ utils/ --ignore-missing-imports

# Formatting (optional - nutzen wir noch nicht zwingend)
black core/ tools/ utils/ --line-length=100
```

## 🧪 Testing Guidelines

### Test-Struktur

```
tests/
├── unit/              # Unit Tests (schnell, isoliert)
├── integration/       # Integration Tests (langsamer, mit echten Services)
└── fixtures/          # Shared Test Fixtures
```

### Test-Naming

```python
# test_<module>.py
def test_<function>_<scenario>_<expected_result>():
    pass

# Beispiele:
def test_search_web_with_valid_query_returns_results():
    pass

def test_cache_get_with_expired_key_returns_none():
    pass

def test_agent_query_with_empty_string_raises_value_error():
    pass
```

### Test-Best-Practices

#### 1. Arrange-Act-Assert Pattern

```python
def test_cache_stores_and_retrieves_data():
    # Arrange
    cache = Cache(ttl_hours=24)
    test_key = "test_key"
    test_value = {"data": "test"}
    
    # Act
    cache.set(test_key, test_value)
    result = cache.get(test_key)
    
    # Assert
    assert result == test_value
```

#### 2. Mocking für externe Services

```python
from unittest.mock import Mock, patch

def test_web_search_handles_api_failure():
    # Mock requests.get to simulate failure
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.RequestException("API Error")
        
        # Test that fallback is used
        result = search_web("test query")
        assert result == []  # or fallback result
```

#### 3. Fixtures für Wiederverwendung

```python
import pytest

@pytest.fixture
def sample_config():
    """Provide test configuration."""
    return {
        "llm": {"model": "test-model"},
        "search": {"max_results": 3}
    }

@pytest.fixture
def agent(sample_config):
    """Provide configured agent."""
    return SearchAgent(config=sample_config)

def test_agent_initialization(agent):
    assert agent is not None
    assert agent.config["search"]["max_results"] == 3
```

#### 4. Parametrized Tests

```python
import pytest

@pytest.mark.parametrize("query,expected", [
    ("python tutorial", True),
    ("", False),
    (None, False),
    ("a" * 1000, False),
])
def test_validate_query(query, expected):
    assert validate_query(query) == expected
```

### Test-Coverage

Ziel: **≥ 80% Coverage** für Core-Module

```bash
# Coverage-Report generieren
pytest --cov=core --cov=tools --cov=utils tests/ --cov-report=html

# Report öffnen
# Windows
start htmlcov/index.html

# Linux/macOS
open htmlcov/index.html
```

### Integration Tests

Integration Tests sind langsamer und optional:

```python
import pytest

# Mark als slow test
@pytest.mark.slow
def test_full_query_pipeline():
    """Test complete query pipeline with real LLM."""
    agent = SearchAgent()
    result = agent.query("What is Python?")
    assert len(result) > 0

# Nur slow tests ausführen
# pytest -m slow

# Slow tests überspringen
# pytest -m "not slow"
```

### Test-Ausführung

```bash
# Alle Tests
pytest tests/ -v

# Spezifische Test-Datei
pytest tests/test_cache.py -v

# Spezifischer Test
pytest tests/test_cache.py::test_cache_expiry -v

# Mit Coverage
pytest tests/ --cov=core --cov=tools --cov-report=term-missing

# Parallel (schneller, benötigt pytest-xdist)
pytest tests/ -n auto

# Nur fehlgeschlagene Tests wiederholen
pytest --lf

# Stop bei erstem Fehler
pytest -x
```

## 📚 Dokumentation

### Code-Dokumentation

- **Docstrings** für alle öffentlichen Klassen/Funktionen
- **Inline-Kommentare** für komplexe Logik
- **Type Hints** für Funktionssignaturen

### Externe Dokumentation

Aktualisiere bei Änderungen:

- `README.md` - Hauptdokumentation, Features, Quickstart
- `docs/` - Detaillierte Guides und Tutorials
- `CHANGELOG.md` - Release Notes

### Dokumentations-Richtlinien

- **Klar und präzise** - Vermeide Fachjargon
- **Beispiele** - Code-Beispiele für alle Features
- **Screenshots** - Für UI-relevante Änderungen
- **Deutsch** - Primärsprache (Englisch als Bonus)

## 📝 Commit Guidelines

### Commit-Format

Wir verwenden **Conventional Commits**:

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Types

- `feat` - Neues Feature
- `fix` - Bug-Fix
- `docs` - Dokumentation
- `style` - Formatierung (keine Code-Änderung)
- `refactor` - Code-Refactoring
- `test` - Tests hinzufügen/ändern
- `chore` - Maintenance (Dependencies, Build)
- `perf` - Performance-Verbesserung

#### Scope (Optional)

- `core` - Core-Logik
- `api` - REST API
- `tools` - Tools (search, rag, etc.)
- `utils` - Utilities
- `tests` - Tests
- `docs` - Dokumentation

#### Beispiele

```bash
# Feature
feat(search): add Google search provider

# Bug-Fix
fix(cache): prevent race condition in cache writes

# Dokumentation
docs(readme): update installation instructions

# Refactoring
refactor(agent): split query_with_tools into smaller methods

# Tests
test(cache): add tests for TTL expiry

# Breaking Change
feat(api)!: change query endpoint response format

BREAKING CHANGE: Query endpoint now returns {...} instead of [...]
```

### Commit-Best-Practices

1. **Atomic Commits** - Ein Commit = Eine logische Änderung
2. **Klare Messages** - Beschreibe WAS und WARUM
3. **Imperative Mood** - "add feature" nicht "added feature"
4. **50/72 Rule** - Subject max 50 Zeichen, Body max 72
5. **Reference Issues** - `Fixes #123`, `Closes #456`

**Beispiel:**

```bash
git commit -m "feat(osint): add phone number validation

- Add libphonenumber integration
- Support international formats
- Add validation tests

Closes #234"
```

## 🚀 Release-Prozess

Releases werden vom Maintainer-Team verwaltet:

1. **Version Bump** in `README.md`, `CHANGELOG.md`
2. **Tag erstellen**: `git tag -a v1.4.0 -m "Release v1.4.0"`
3. **Push Tag**: `git push origin v1.4.0`
4. **GitHub Release** mit Release Notes erstellen

### Versionierung

Wir folgen [Semantic Versioning](https://semver.org/):

- `MAJOR` - Breaking Changes
- `MINOR` - Neue Features (backward-compatible)
- `PATCH` - Bug-Fixes

## ❓ Fragen?

- **Issues**: [GitHub Issues](https://github.com/arn-c0de/Crawllama/issues)
- **Discussions**: [GitHub Discussions](https://github.com/arn-c0de/Crawllama/discussions)


---

**Danke für deine Beiträge! 🎉**

Jeder Beitrag, egal wie klein, hilft CrawlLama besser zu werden.
