# 📚 Documentation Overview

Welcome to the CrawlLama documentation! Here you'll find all guides, tutorials, and references organized in clear categories.

---

## 📋 Category Overview

### 🚀 [Getting Started](getting-started/)
First steps with CrawlLama
- **[INSTALLATION.md](getting-started/INSTALLATION.md)** - Detailed installation guide
- **[QUICKSTART.md](getting-started/QUICKSTART.md)** - Quick start in 5 minutes

### 📖 [Guides & Tutorials](guides/)
Feature-specific guides
- **[LANGGRAPH_GUIDE.md](guides/LANGGRAPH_GUIDE.md)** - Multi-hop reasoning with LangGraph
- **[PLUGIN_TUTORIAL.md](guides/PLUGIN_TUTORIAL.md)** - Develop and use plugins
- **[SEARCH_LIMITATIONS.md](guides/SEARCH_LIMITATIONS.md)** - Web search limitations
- **[HALLUCINATION_DETECTION.md](guides/HALLUCINATION_DETECTION.md)** - Hallucination detection

### 🔍 [OSINT Features](osint/)
Open Source Intelligence Module
- **[OSINT_USAGE.md](osint/OSINT_USAGE.md)** - Using OSINT modules (Email, Phone, Advanced Operators)
- **[OSINT_CONTEXT_USAGE.md](osint/OSINT_CONTEXT_USAGE.md)** - Using OSINT in context
- **[SOCIAL_INTELLIGENCE.md](osint/SOCIAL_INTELLIGENCE.md)** - Social intelligence features

### 🏥 [Health Monitoring](health/)
System monitoring and dashboard
- **[HEALTH_MONITORING.md](health/HEALTH_MONITORING.md)** - Health monitoring system
- **[HEALTH_DASHBOARD.md](health/HEALTH_DASHBOARD.md)** - Using the dashboard
- **[HEALTH_FEATURES.md](health/HEALTH_FEATURES.md)** - Available features
- **[DASHBOARD_STARTER.md](health/DASHBOARD_STARTER.md)** - Starting the dashboard



### 🤖 [Adaptive Agent Hopping]
Intelligent agent selection and complexity management
- **[ADAPTIVE_HOPS.md](../docs/ADAPTIVE_HOPS.md)** – Complete architecture and functionality
- **[ADAPTIVE_HOPS_QUICKSTART.md](../docs/ADAPTIVE_HOPS_QUICKSTART.md)** – 3-step integration and quick start

### 🔧 [Development](development/)
Development and release management
- **[PROJECT_STRUCTURE.md](development/PROJECT_STRUCTURE.md)** - Detailed directory overview
- **[RELEASE_PROCESS.md](development/RELEASE_PROCESS.md)** - Release workflow for maintainers
- **[PRE_RELEASE_CHECK.md](development/PRE_RELEASE_CHECK.md)** - Pre-release checklist

### 🔒 [Security](security/)
Security and compliance
- **[SECRET_LEAK_RESPONSE.md](security/SECRET_LEAK_RESPONSE.md)** - Emergency plan for secret leaks

---

## 👥 Community & Contributing

- **[README.md](../README.md)** - Main documentation, features, installation
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - How to contribute to CrawlLama
- **[CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md)** - Community code of conduct
- **[SECURITY.md](../SECURITY.md)** - Report security vulnerabilities
- **[CHANGELOG.md](../CHANGELOG.md)** - Release history and changes

## 🗂️ Directory Structure

### New organized structure
```
docs/
├── README.md                    ← This overview
├── getting-started/             ← 🚀 Installation & First Steps
│   ├── INSTALLATION.md
│   └── QUICKSTART.md
├── guides/                      ← 📖 Feature Guides & Tutorials
│   ├── LANGGRAPH_GUIDE.md
│   ├── PLUGIN_TUTORIAL.md
│   ├── SEARCH_LIMITATIONS.md
│   └── HALLUCINATION_DETECTION.md
├── osint/                       ← 🔍 OSINT-specific Documentation
│   ├── OSINT_USAGE.md
│   ├── OSINT_CONTEXT_USAGE.md
│   └── SOCIAL_INTELLIGENCE.md
├── health/                      ← 🏥 Health Monitoring & Dashboard
│   ├── HEALTH_MONITORING.md
│   ├── HEALTH_DASHBOARD.md
│   ├── HEALTH_FEATURES.md
│   └── DASHBOARD_STARTER.md
├── development/                 ← 🔧 Developer Documentation
│   ├── PROJECT_STRUCTURE.md
│   ├── RELEASE_PROCESS.md
│   └── PRE_RELEASE_CHECK.md
└── security/                    ← 🔒 Security & Compliance
    └── SECRET_LEAK_RESPONSE.md
```

### Root project files
- **[config.json](../config.json)** - Main configuration (LLM, Search, RAG, Cache, OSINT)
- **[.env.example](../.env.example)** - Example environment variables
- **[pytest.ini](../pytest.ini)** - Test configuration

## 🔗 External Links

- **GitHub Repository**: [github.com/arn-c0de/Crawllama](https://github.com/arn-c0de/Crawllama)
- **Issues**: [github.com/arn-c0de/Crawllama/issues](https://github.com/arn-c0de/Crawllama/issues)
- **Security Advisories**: [github.com/arn-c0de/Crawllama/security](https://github.com/arn-c0de/Crawllama/security/advisories)

## 📑 Recommended Learning Path

### 1. Getting Started 🚀
1. [README.md](../README.md) - Project overview
2. [getting-started/INSTALLATION.md](getting-started/INSTALLATION.md) - Detailed installation
3. [getting-started/QUICKSTART.md](getting-started/QUICKSTART.md) - Quick start

### 2. Using Core Features 📖
1. [guides/LANGGRAPH_GUIDE.md](guides/LANGGRAPH_GUIDE.md) - Multi-hop reasoning
2. [guides/PLUGIN_TUTORIAL.md](guides/PLUGIN_TUTORIAL.md) - Plugin system
3. [health/HEALTH_MONITORING.md](health/HEALTH_MONITORING.md) - Health dashboard

### 3. Advanced Features 🔍
1. [osint/OSINT_USAGE.md](osint/OSINT_USAGE.md) - OSINT features
2. [guides/HALLUCINATION_DETECTION.md](guides/HALLUCINATION_DETECTION.md) - Quality control
3. [guides/SEARCH_LIMITATIONS.md](guides/SEARCH_LIMITATIONS.md) - Understanding limitations

### 4. Development & Security 🔧
1. [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
2. [development/RELEASE_PROCESS.md](development/RELEASE_PROCESS.md) - Release workflow
3. [security/SECRET_LEAK_RESPONSE.md](security/SECRET_LEAK_RESPONSE.md) - Incident response

## 🆘 Need Help?

- **Found a bug?** → [Bug Report](https://github.com/arn-c0de/Crawllama/issues/new?template=bug_report.yml)
- **Feature request?** → [Feature Request](https://github.com/arn-c0de/Crawllama/issues/new?template=feature_request.yml)
- **Documentation unclear?** → [Documentation Issue](https://github.com/arn-c0de/Crawllama/issues/new?template=documentation.yml)

---

**Back to [Main Page](../README.md)** | **[License](../LICENSE)** | **[Contributing](../CONTRIBUTING.md)**
