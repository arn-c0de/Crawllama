# CrawlLama Documentation Overview

Welcome to the CrawlLama documentation! This guide organizes all tutorials, references, and guides into clear categories for easier navigation.

---

## Categories

### [Getting Started](getting-started/)
First steps with CrawlLama:
- **[INSTALLATION.md](getting-started/INSTALLATION.md)** – Detailed installation guide
- **[QUICKSTART.md](getting-started/QUICKSTART.md)** – Quick start in 5 minutes
- **[CONFIG_SETUP.md](getting-started/CONFIG_SETUP.md)** – Configuration file setup and usage
- **[ADAPTIVE_HOPS_QUICKSTART.md](getting-started/ADAPTIVE_HOPS_QUICKSTART.md)** – Adaptive Hops quick start

### [Guides & Tutorials](guides/)
Feature-specific guides:
- **[LANGGRAPH_GUIDE.md](guides/LANGGRAPH_GUIDE.md)** – Multi-hop reasoning with LangGraph
- **[PLUGIN_TUTORIAL.md](guides/PLUGIN_TUTORIAL.md)** – Developing and using plugins
- **[SEARCH_LIMITATIONS.md](guides/SEARCH_LIMITATIONS.md)** – Web search limitations
- **[HALLUCINATION_DETECTION.md](guides/HALLUCINATION_DETECTION.md)** – Hallucination detection
- **[RAG_ANALYSIS.md](guides/RAG_ANALYSIS.md)** – RAG implementation and architecture
- **[API_USAGE.md](guides/API_USAGE.md)** – API usage guide
- **[EXPORT_REPORT.md](guides/EXPORT_REPORT.md)** – Export generated reports as Markdown or plain text

### [OSINT Features](osint/)
Open Source Intelligence Module:
- **[OSINT_USAGE.md](osint/OSINT_USAGE.md)** – OSINT modules (Email, Phone, Advanced Operators)
- **[PHONE_INTELLIGENCE.md](osint/PHONE_INTELLIGENCE.md)** – Phone intelligence developer documentation (parsing, normalization, auto-detection)
- **[OSINT_CONTEXT_USAGE.md](osint/OSINT_CONTEXT_USAGE.md)** – OSINT in context
- **[SOCIAL_INTELLIGENCE.md](osint/SOCIAL_INTELLIGENCE.md)** – Social intelligence features

### [Health Monitoring](health/)
System monitoring and dashboard:
- **[HEALTH_MONITORING.md](health/HEALTH_MONITORING.md)** – Health monitoring
- **[HEALTH_DASHBOARD.md](health/HEALTH_DASHBOARD.md)** – Dashboard usage
- **[HEALTH_FEATURES.md](health/HEALTH_FEATURES.md)** – Available features
- **[DASHBOARD_STARTER.md](health/DASHBOARD_STARTER.md)** – Starting the dashboard

### Adaptive Agent Hopping
- **[ADAPTIVE_HOPS.md](guides/ADAPTIVE_HOPS.md)** – Intelligent agent selection and complexity management

### [Development](development/)
- **[PROJECT_STRUCTURE.md](development/PROJECT_STRUCTURE.md)** – Project structure overview
- **[1.4.11-doc-audit-code-findings.md](development/1.4.11-doc-audit-code-findings.md)** – Open code findings from the v1.4.11 documentation audit
- **[bugs/delete_null_file.md](development/bugs/delete_null_file.md)** – Bug examples

### [Security](security/)
- **[SECRET_LEAK_RESPONSE.md](security/SECRET_LEAK_RESPONSE.md)** – Secret leak response and incident plan

---

## Community & Contributing

- **[README.md](../README.md)** – Main project documentation
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** – How to contribute
- **[CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md)** – Community code of conduct
- **[SECURITY.md](../SECURITY.md)** – Report vulnerabilities
- **[CHANGELOG.md](../CHANGELOG.md)** – Release history

---

## Directory Structure

```

docs/
├── README.md
├── getting-started/
│ ├── INSTALLATION.md
│ ├── QUICKSTART.md
│ ├── CONFIG_SETUP.md
│ └── ADAPTIVE_HOPS_QUICKSTART.md
├── guides/
│ ├── LANGGRAPH_GUIDE.md
│ ├── PLUGIN_TUTORIAL.md
│ ├── SEARCH_LIMITATIONS.md
│ ├── SEARCH_IMPROVEMENTS.md
│ ├── HALLUCINATION_DETECTION.md
│ ├── RAG_ANALYSIS.md
│ ├── API_USAGE.md
│ ├── ADAPTIVE_HOPS.md
│ ├── CLI_PROVIDER_SELECTION.md
│ ├── CLOUD_LLM_INTEGRATION.md
│ └── EXPORT_REPORT.md
├── osint/
│ ├── OSINT_USAGE.md
│ ├── PHONE_INTELLIGENCE.md
│ ├── OSINT_CONTEXT_USAGE.md
│ ├── SOCIAL_INTELLIGENCE.md
│ └── COMPANY_INTELLIGENCE.md
├── health/
│ ├── HEALTH_MONITORING.md
│ ├── HEALTH_DASHBOARD.md
│ ├── HEALTH_FEATURES.md
│ └── DASHBOARD_STARTER.md
├── development/
│ ├── PROJECT_STRUCTURE.md
│ ├── 1.4.7-Breachdata-update-plan.md
│ ├── 1.4.11-doc-audit-code-findings.md
│ └── bugs/
│ └── delete_null_file.md
└── security/
├── SECRET_LEAK_RESPONSE.md
├── api-security-guide.md
├── 1.4.7-security_analysis_report.md
└── CODEQL_Sec-Volun-test.txt

```

### Root Project Files
- **[config.json](../config.json)** – Main configuration
- **[.env.example](../.env.example)** – Environment variables template
- **[pytest.ini](../pytest.ini)** – Test configuration

---

## External Links

- **GitHub Repository**: [github.com/arn-c0de/Crawllama](https://github.com/arn-c0de/Crawllama)
- **Issues**: [github.com/arn-c0de/Crawllama/issues](https://github.com/arn-c0de/Crawllama/issues)
- **Security Advisories**: [github.com/arn-c0de/Crawllama/security](https://github.com/arn-c0de/Crawllama/security/advisories)

---

## Recommended Learning Path

### 1. Getting Started 
1. [README.md](../README.md) – Project overview
2. [INSTALLATION.md](getting-started/INSTALLATION.md) – Detailed installation
3. [QUICKSTART.md](getting-started/QUICKSTART.md) – Quick start

### 2. Using Core Features 
1. [LANGGRAPH_GUIDE.md](guides/LANGGRAPH_GUIDE.md) – Multi-hop reasoning
2. [PLUGIN_TUTORIAL.md](guides/PLUGIN_TUTORIAL.md) – Plugin system
3. [EXPORT_REPORT.md](guides/EXPORT_REPORT.md) – Export reports to file
4. [HEALTH_MONITORING.md](health/HEALTH_MONITORING.md) – Health dashboard

### 3. Advanced Features 
1. [OSINT_USAGE.md](osint/OSINT_USAGE.md) – OSINT features
2. [PHONE_INTELLIGENCE.md](osint/PHONE_INTELLIGENCE.md) – Phone intelligence internals
3. [HALLUCINATION_DETECTION.md](guides/HALLUCINATION_DETECTION.md) – Quality control
4. [SEARCH_LIMITATIONS.md](guides/SEARCH_LIMITATIONS.md) – Search limitations

### 4. Development & Security 
1. [CONTRIBUTING.md](../CONTRIBUTING.md) – Contribution guidelines
2. [SECRET_LEAK_RESPONSE.md](security/SECRET_LEAK_RESPONSE.md) – Incident response

---

## Need Help?

- **Found a bug?** → [Bug Report](https://github.com/arn-c0de/Crawllama/issues/new?template=bug_report.yml)
- **Feature request?** → [Feature Request](https://github.com/arn-c0de/Crawllama/issues/new?template=feature_request.yml)
- **Documentation issue?** → [Documentation Issue](https://github.com/arn-c0de/Crawllama/issues/new?template=documentation.yml)

---

**Back to [Main Page](../README.md)** | **[License](../LICENSE)** | **[Contributing](../CONTRIBUTING.md)** | **[RAG Analysis](guides/RAG_ANALYSIS.md)**

