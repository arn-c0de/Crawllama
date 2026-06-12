# Contributing to CrawlLama

Thank you for your interest in contributing to **CrawlLama**! 
We welcome **all types of contributions**—bug fixes, new features, documentation, tests, translations, and design improvements.

---

 **Navigation:** [README](README.md) | [Docs](docs/README.md) | [Security](SECURITY.md) | [Changelog](CHANGELOG.md) | [Code of Conduct](CODE_OF_CONDUCT.md)

---

## Quick Start – How You Can Help

No experience required for some tasks! You can contribute in multiple areas:

### Testing & QA
- Add unit or integration tests (`core/`, `tools/`, `utils/`) 
- Test across platforms: macOS, Linux, Windows 
- Report bugs or performance issues 

### Documentation & Translations
- Translate documentation (German, Spanish, French, Chinese, etc.) 
- Improve guides, tutorials, examples, and docstrings 

### Design & Creative
- Refine logo or GitHub banner 
- Design UI mockups or architecture diagrams 
- Create tutorial graphics 

### Development
- Review PRs 
- Refactor code for clarity 
- Add features or fix bugs ([see open issues](https://github.com/arn-c0de/Crawllama/issues)) 

### Community Support
- Answer questions on GitHub 
- Share your use cases or tutorials 
- Improve examples in documentation 

> **Tip:** You don’t need to code—documentation, design, translations, and bug reports are equally valuable!

---

## Code of Conduct
This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to follow its guidelines.

---

## How to Contribute

### Bug Reports
1. Check if the issue already exists ([Issues](https://github.com/arn-c0de/Crawllama/issues)) 
2. Open a new issue including: 
 - Description, steps to reproduce, expected vs actual behavior 
 - Environment: Python version, OS, CrawlLama version 
 - Logs & code examples if applicable 

### Feature Requests
1. Open an issue describing the feature and use case 
2. Include mockups or implementation ideas 
3. Wait for maintainer approval before starting 

### Code Contributions
1. Fork the repo 
2. Create a branch: `git checkout -b feature/awesome-feature` 
3. Implement changes & write tests 
4. Commit using [Conventional Commits](#commit-guidelines) 
5. Push to your branch & open a Pull Request 

### Documentation
- Improve `README.md`, `docs/`, docstrings, and inline comments 
- Add examples, tutorials, or translation updates 

---

## Development Setup

### Prerequisites
- Python 3.10+ (recommended: 3.12) 
- Git 
- Ollama (for LLM inference) 
- Virtual Environment
Here’s the updated **Quick Start / Setup** section in English, including the alternative `setup.bat` / `setup.sh` option:

## Quick Start

### Virtual Environment Setup

#### Option 1: Manual Setup

```bash
# Clone the repository
git clone https://github.com/arn-c0de/Crawllama.git
cd Crawllama

# Install dependencies with uv (creates the virtual environment)
# Add the testing extra to pull in pytest, pytest-cov, pytest-mock, etc.
uv sync --extra testing

# Ollama setup
ollama pull qwen3:4b

# Copy environment config
cp .env.example .env
# Edit .env with API keys if needed

# Run tests
uv run pytest tests/ -v
```

#### Option 2: Automated Setup

**Windows:**

```cmd
setup.bat
```

**Linux/macOS:**

```bash
./setup.sh
```

> Both scripts automatically create a virtual environment, install dependencies, pull the Ollama model, and copy `.env.example` to `.env`.

---

### 1. Start the API Server

**Windows:**

```cmd
run_api.bat
```

**Linux/macOS:**

```bash
./run_api.sh
```

Or manually:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

### 2. Access the API

* **API Root:** [http://localhost:8000](http://localhost:8000)
* **Interactive Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Pull Request Workflow

### Branch Naming

* `feature/` - New features
* `fix/` - Bug fixes
* `docs/` - Documentation
* `test/` - Test improvements
* `refactor/` - Code refactoring
* `chore/` - Maintenance

### PR Checklist

* Code follows the project's coding standards (PEP8, type hints, docstrings, tests)
* Tests added & passing
* Documentation updated
* No secrets in code

---

## Commit Guidelines

We use **Conventional Commits**:

```
<type>(<scope>): <subject>

<body>
<footer>
```

**Types**

* `feat` - New feature
* `fix` - Bug fix
* `docs` - Documentation
* `style` - Formatting
* `refactor` - Code refactoring
* `test` - Add/modify tests
* `chore` - Maintenance
* `perf` - Performance improvement

**Example:**

```bash
git commit -m "feat(search): add Google search provider

- Implement new search logic
- Add tests
Closes #123"
```

---

## Questions?

* [GitHub Discussions](https://github.com/arn-c0de/Crawllama/discussions)
* [GitHub Issues](https://github.com/arn-c0de/Crawllama/issues)
* Email: [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com)

---

**Thank you for contributing!** Every contribution, no matter how small, helps make CrawlLama better. 

