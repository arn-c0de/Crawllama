# Contributing to CrawlLama

Thank you for your interest in contributing to CrawlLama! 🎉

We welcome all types of contributions—whether bug fixes, new features, documentation improvements, or tests.

---

📚 **Navigation:** [README](README.md) | [Docs](docs/README.md) | [Security](SECURITY.md) | [Changelog](CHANGELOG.md) | [Code of Conduct](CODE_OF_CONDUCT.md)

---

## 🎯 Quick Start - How You Can Help Right Now!

We're actively looking for help with the following areas. **No experience required for some tasks!**

### 🧪 Testing & Quality Assurance
- **Write more tests** - Increase coverage for `core/`, `tools/`, and `utils/` modules
- **Test on different platforms** - macOS, Linux distributions, Windows versions
- **Report bugs** - Test edge cases and report issues
- **Performance testing** - Help identify bottlenecks

### 🌍 Translations & Documentation
- **Complete German translation** - Some docs are still in English
- **Translate to other languages** - Spanish, French, Chinese, etc.
- **Improve documentation** - Fix typos, add examples, clarify instructions
- **Create tutorials** - Video guides, blog posts, use case examples

### 🎨 Design & Creative
- **GitHub profile banner** - Create a professional banner for the repository
- **Logo improvements** - Refine the current logo or create variations
- **UI mockups** - Design ideas for future dashboard/web interface
- **Documentation graphics** - Diagrams, flowcharts, architecture visuals

### 💻 Development Tasks
- **Code review** - Review open PRs and provide feedback
- **Refactoring** - Improve code structure and readability
- **New features** - Check [open issues](https://github.com/arn-c0de/Crawllama/issues) for feature requests
- **Bug fixes** - Tackle issues labeled `good first issue` or `help wanted`

### 📚 Community Support
- **Answer questions** - Help users in GitHub Issues
- **Share your use cases** - Blog posts, social media, showcase projects
- **Improve examples** - Add real-world usage examples

> **💡 Tip:** Can't commit code? No problem! Documentation improvements, translations, design work, and bug reports are equally valuable contributions!

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Pull Request Workflow](#pull-request-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Commit Guidelines](#commit-guidelines)

## 📜 Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to abide by these guidelines.

## 🤝 How Can I Contribute?

### 🐛 Bug Reports

If you find a bug:

1. **Check** if the issue has already been reported in [Issues](https://github.com/arn-c0de/Crawllama/issues).
2. **Create a new issue** with:
   - Clear description of the problem
   - Steps to reproduce
   - Expected vs. actual behavior
   - Python version, OS, relevant logs
   - Code example (if possible)

**Example of good bug reporting:**
```markdown
**Bug:** Agent crashes with empty cache

**Steps:**
1. Start agent with `python main.py --interactive`
2. Run `clear-cache`
3. Ask a question

**Expected:** Response is generated
**Actual:** KeyError in cache.py

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

For new features:

1. **Create an issue** with:
   - Clear description of the desired feature
   - Use case / problem it solves
   - Example code or mockups (if relevant)
   - Possible implementation approaches

2. **Wait for feedback** from the maintainer team
3. After approval, you can start implementing

### 🔧 Code Contributions

1. **Fork** the repository
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Implement** your changes
4. **Write tests** for new features
5. **Commit** your changes (see [Commit Guidelines](#commit-guidelines))
6. **Push** to the branch (`git push origin feature/amazing-feature`)
7. **Create a Pull Request**

### 📖 Documentation

Documentation improvements are always welcome:

- **README.md**: Installation guide, quickstart, features
- **docs/**: Detailed guides, tutorials, API documentation
- **Docstrings**: Python code documentation
- **Code Comments**: Explanation of complex logic

## 🛠️ Development Setup

### Prerequisites

- Python 3.10+ (recommended: 3.12)
- Git
- Ollama (for LLM inference)
- Virtual Environment

### Setup Steps

```bash
# 1. Fork and Clone
git clone https://github.com/YOUR-USERNAME/Crawllama.git
cd Crawllama

# 2. Virtual Environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

# 3. Install Dependencies
pip install -r requirements.txt

# 4. Development Dependencies
pip install pytest pytest-cov pytest-mock flake8 black mypy

# 5. Ollama Setup
ollama pull qwen3:4b

# 6. Configuration
cp .env.example .env
# Edit .env with your API keys (optional)

# 7. Run Tests
pytest tests/ -v
```

### Alternative: Setup Script

```bash
# Windows
setup.bat

# Linux/macOS
chmod +x setup.sh
./setup.sh
```

## 🔄 Pull Request Workflow

### 1. Branch Naming

Use descriptive branch names:

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation
- `test/` - Test improvements
- `refactor/` - Code refactoring
- `chore/` - Maintenance tasks

**Examples:**
```bash
git checkout -b feature/add-google-search
git checkout -b fix/cache-corruption
git checkout -b docs/improve-readme
```

### 2. Pull Request Checklist

Before creating a PR, ensure:

- [ ] **Code follows [Coding Standards](#coding-standards)**
- [ ] **All tests pass** (`pytest tests/`)
- [ ] **New features have tests** (Coverage ≥ 80%)
- [ ] **Docstrings are updated**
- [ ] **README.md is updated** (for new features)
- [ ] **CHANGELOG.md is updated**
- [ ] **No secrets/API keys in code**
- [ ] **Pre-commit checks pass** (if set up)

### 3. PR Template

Use the following structure for your PR description:

```markdown
## Description
[Brief summary of changes]

## Type of Change
- [ ] Bug Fix (non-breaking change)
- [ ] New Feature (non-breaking change)
- [ ] Breaking Change (fix or feature with API change)
- [ ] Documentation

## Motivation and Context
[Why is this change necessary? What problem does it solve?]

## How Was This Tested?
- [ ] Unit Tests
- [ ] Integration Tests
- [ ] Manual Tests

## Screenshots (if relevant)
[Add screenshots for UI changes]

## Checklist
- [ ] Code follows project standards
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] All tests pass
```

### 4. Review Process

1. **Automated Checks**: CI/CD runs automatically
2. **Code Review**: At least 1 approval required
3. **Discussion**: Feedback discussed in the PR
4. **Changes**: Make adjustments if needed
5. **Merge**: PR is merged after approval

## 📝 Coding Standards

### Python Style Guide

We follow **PEP 8** with some adjustments:

#### Formatting

- **Line Length**: Max 100 characters (comments max 80)
- **Indentation**: 4 spaces (no tabs)
- **Encoding**: UTF-8
- **String Quotes**: Double quotes (`"`) preferred

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

Use type hints for all functions:

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

Use **Google-Style Docstrings**:

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
        "1. Example\nhttp://...\n..."
    """
    pass
```

#### Imports

Sort imports by standard:

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
# Use specific exceptions
try:
    result = search_web(query)
except ValueError as e:
    logger.error(f"Invalid query: {e}")
    raise
except TimeoutError:
    logger.warning("Search timeout - using cache")
    result = get_cached_result(query)
```

### Code Quality Tools

We recommend the following tools:

```bash
# Linting
flake8 core/ tools/ utils/ --max-line-length=100

# Type Checking
mypy core/ tools/ utils/ --ignore-missing-imports

# Formatting (optional - not mandatory yet)
black core/ tools/ utils/ --line-length=100
```

## 🧪 Testing Guidelines

### Test Structure

```
tests/
├── unit/              # Unit Tests (fast, isolated)
├── integration/       # Integration Tests (slower, with real services)
└── fixtures/          # Shared Test Fixtures
```

### Test Naming

```python
# test_<module>.py
def test_<function>_<scenario>_<expected_result>():
    pass

# Examples:
def test_search_web_with_valid_query_returns_results():
    pass

def test_cache_get_with_expired_key_returns_none():
    pass

def test_agent_query_with_empty_string_raises_value_error():
    pass
```

### Test Best Practices

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

#### 2. Mocking for External Services

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

#### 3. Fixtures for Reuse

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

### Test Coverage

Goal: **≥ 80% Coverage** for core modules

```bash
# Generate coverage report
pytest --cov=core --cov=tools --cov=utils tests/ --cov-report=html

# Open report
# Windows
start htmlcov/index.html

# Linux/macOS
open htmlcov/index.html
```

### Integration Tests

Integration tests are slower and optional:

```python
import pytest

# Mark as slow test
@pytest.mark.slow
def test_full_query_pipeline():
    """Test complete query pipeline with real LLM."""
    agent = SearchAgent()
    result = agent.query("What is Python?")
    assert len(result) > 0

# Run only slow tests
# pytest -m slow

# Skip slow tests
# pytest -m "not slow"
```

### Test Execution

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_cache.py -v

# Specific test
pytest tests/test_cache.py::test_cache_expiry -v

# With coverage
pytest tests/ --cov=core --cov=tools --cov-report=term-missing

# Parallel (faster, requires pytest-xdist)
pytest tests/ -n auto

# Rerun only failed tests
pytest --lf

# Stop on first failure
pytest -x
```

## 📚 Documentation

### Code Documentation

- **Docstrings** for all public classes/functions
- **Inline Comments** for complex logic
- **Type Hints** for function signatures

### External Documentation

Update when making changes:

- `README.md` - Main documentation, features, quickstart
- `docs/` - Detailed guides and tutorials
- `CHANGELOG.md` - Release notes

### Documentation Guidelines

- **Clear and concise** - Avoid jargon
- **Examples** - Code examples for all features
- **Screenshots** - For UI-related changes
- **English** - Primary language (German as a bonus)

## 📝 Commit Guidelines

### Commit Format

We use **Conventional Commits**:

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Types

- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `style` - Formatting (no code change)
- `refactor` - Code refactoring
- `test` - Add/modify tests
- `chore` - Maintenance (dependencies, build)
- `perf` - Performance improvement

#### Scope (Optional)

- `core` - Core logic
- `api` - REST API
- `tools` - Tools (search, rag, etc.)
- `utils` - Utilities
- `tests` - Tests
- `docs` - Documentation

#### Examples

```bash
# Feature
feat(search): add Google search provider

# Bug Fix
fix(cache): prevent race condition in cache writes

# Documentation
docs(readme): update installation instructions

# Refactoring
refactor(agent): split query_with_tools into smaller methods

# Tests
test(cache): add tests for TTL expiry

# Breaking Change
feat(api)!: change query endpoint response format

BREAKING CHANGE: Query endpoint now returns {...} instead of [...]
```

### Commit Best Practices

1. **Atomic Commits** - One commit = One logical change
2. **Clear Messages** - Describe WHAT and WHY
3. **Imperative Mood** - "add feature" not "added feature"
4. **50/72 Rule** - Subject max 50 characters, body max 72
5. **Reference Issues** - `Fixes #123`, `Closes #456`

**Example:**

```bash
git commit -m "feat(osint): add phone number validation

- Add libphonenumber integration
- Support international formats
- Add validation tests

Closes #234"
```

## 🚀 Release Process

Releases are managed by the maintainer team:

1. **Version Bump** in `README.md`, `CHANGELOG.md`
2. **Create Tag**: `git tag -a v1.4.0 -m "Release v1.4.0"`
3. **Push Tag**: `git push origin v1.4.0`
4. **GitHub Release** with release notes

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- `MAJOR` - Breaking changes
- `MINOR` - New features (backward-compatible)
- `PATCH` - Bug fixes

## ❓ Questions?

- **Issues**: [GitHub Issues](https://github.com/arn-c0de/Crawllama/issues)
- **Support**: [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com)
- **Contributions/Hire**: [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com)

---

**Thank you for your contributions! 🎉**

Every contribution, no matter how small, helps make CrawlLama better.
