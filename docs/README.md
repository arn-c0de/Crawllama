# 📚 Dokumentations-Übersicht

Willkommen zur CrawlLama-Dokumentation! Hier findest du alle Guides, Tutorials und Referenzen in übersichtlichen Kategorien organisiert.

---

## 📋 Kategorien-Übersicht

### 🚀 [Getting Started](getting-started/)
Erste Schritte mit CrawlLama
- **[INSTALLATION.md](getting-started/INSTALLATION.md)** - Detaillierte Installationsanleitung
- **[QUICKSTART.md](getting-started/QUICKSTART.md)** - Schnelleinstieg in 5 Minuten

### 📖 [Guides & Tutorials](guides/)
Feature-spezifische Anleitungen
- **[LANGGRAPH_GUIDE.md](guides/LANGGRAPH_GUIDE.md)** - Multi-Hop-Reasoning mit LangGraph
- **[PLUGIN_TUTORIAL.md](guides/PLUGIN_TUTORIAL.md)** - Plugins entwickeln und nutzen
- **[SEARCH_LIMITATIONS.md](guides/SEARCH_LIMITATIONS.md)** - Web-Suche Limitierungen
- **[HALLUCINATION_DETECTION.md](guides/HALLUCINATION_DETECTION.md)** - Hallucination Detection

### 🔍 [OSINT Features](osint/)
Open Source Intelligence Module
- **[OSINT_USAGE.md](osint/OSINT_USAGE.md)** - OSINT-Module nutzen (Email, Phone, Advanced Operators)
- **[OSINT_CONTEXT_USAGE.md](osint/OSINT_CONTEXT_USAGE.md)** - OSINT im Context verwenden
- **[SOCIAL_INTELLIGENCE.md](osint/SOCIAL_INTELLIGENCE.md)** - Social Intelligence Features

### 🏥 [Health Monitoring](health/)
System-Überwachung und Dashboard
- **[HEALTH_MONITORING.md](health/HEALTH_MONITORING.md)** - Health Monitoring System
- **[HEALTH_DASHBOARD.md](health/HEALTH_DASHBOARD.md)** - Dashboard nutzen
- **[HEALTH_FEATURES.md](health/HEALTH_FEATURES.md)** - Verfügbare Features
- **[DASHBOARD_STARTER.md](health/DASHBOARD_STARTER.md)** - Dashboard starten

### 🔧 [Development](development/)
Entwicklung und Release-Management
- **[PROJECT_STRUCTURE.md](development/PROJECT_STRUCTURE.md)** - Detaillierte Verzeichnis-Übersicht
- **[RELEASE_PROCESS.md](development/RELEASE_PROCESS.md)** - Release-Workflow für Maintainer
- **[PRE_RELEASE_CHECK.md](development/PRE_RELEASE_CHECK.md)** - Pre-Release Checklist

### 🔒 [Security](security/)
Sicherheit und Compliance
- **[SECRET_LEAK_RESPONSE.md](security/SECRET_LEAK_RESPONSE.md)** - Notfallplan für Secret-Leaks

---

## 👥 Community & Contributing

- **[README.md](../README.md)** - Hauptdokumentation, Features, Installation
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - Wie du zu CrawlLama beitragen kannst
- **[CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md)** - Community-Verhaltenskodex
- **[SECURITY.md](../SECURITY.md)** - Sicherheitslücken melden
- **[CHANGELOG.md](../CHANGELOG.md)** - Release History und Änderungen

## 🗂️ Verzeichnis-Struktur

### Neue organisierte Struktur
```
docs/
├── README.md                    ← Diese Übersicht
├── getting-started/             ← 🚀 Installation & Erste Schritte
│   ├── INSTALLATION.md          
│   └── QUICKSTART.md           
├── guides/                      ← 📖 Feature-Guides & Tutorials
│   ├── LANGGRAPH_GUIDE.md      
│   ├── PLUGIN_TUTORIAL.md      
│   ├── SEARCH_LIMITATIONS.md   
│   └── HALLUCINATION_DETECTION.md
├── osint/                       ← 🔍 OSINT-spezifische Dokumentation
│   ├── OSINT_USAGE.md          
│   ├── OSINT_CONTEXT_USAGE.md  
│   └── SOCIAL_INTELLIGENCE.md  
├── health/                      ← 🏥 Health Monitoring & Dashboard
│   ├── HEALTH_MONITORING.md    
│   ├── HEALTH_DASHBOARD.md     
│   ├── HEALTH_FEATURES.md      
│   └── DASHBOARD_STARTER.md    
├── development/                 ← 🔧 Entwickler-Dokumentation
│   ├── PROJECT_STRUCTURE.md    
│   ├── RELEASE_PROCESS.md      
│   └── PRE_RELEASE_CHECK.md    
└── security/                    ← 🔒 Sicherheit & Compliance
    └── SECRET_LEAK_RESPONSE.md 
```

### Root-Projekt-Dateien
- **[config.json](../config.json)** - Hauptkonfiguration (LLM, Search, RAG, Cache, OSINT)
- **[.env.example](../.env.example)** - Beispiel für Environment-Variablen
- **[pytest.ini](../pytest.ini)** - Test-Konfiguration

## 🔗 Externe Links

- **GitHub Repository**: [github.com/arn-c0de/Crawllama](https://github.com/arn-c0de/Crawllama)
- **Issues**: [github.com/arn-c0de/Crawllama/issues](https://github.com/arn-c0de/Crawllama/issues)
- **Security Advisories**: [github.com/arn-c0de/Crawllama/security](https://github.com/arn-c0de/Crawllama/security/advisories)

## 📑 Empfohlener Lernpfad

### 1. Erste Schritte 🚀
1. [README.md](../README.md) - Projekt-Überblick
2. [getting-started/INSTALLATION.md](getting-started/INSTALLATION.md) - Detaillierte Installation
3. [getting-started/QUICKSTART.md](getting-started/QUICKSTART.md) - Schnelleinstieg

### 2. Core Features nutzen 📖
1. [guides/LANGGRAPH_GUIDE.md](guides/LANGGRAPH_GUIDE.md) - Multi-Hop-Reasoning
2. [guides/PLUGIN_TUTORIAL.md](guides/PLUGIN_TUTORIAL.md) - Plugin-System
3. [health/HEALTH_MONITORING.md](health/HEALTH_MONITORING.md) - Health Dashboard

### 3. Advanced Features 🔍
1. [osint/OSINT_USAGE.md](osint/OSINT_USAGE.md) - OSINT-Features
2. [guides/HALLUCINATION_DETECTION.md](guides/HALLUCINATION_DETECTION.md) - Qualitätskontrolle
3. [guides/SEARCH_LIMITATIONS.md](guides/SEARCH_LIMITATIONS.md) - Limitierungen verstehen

### 4. Entwicklung & Sicherheit 🔧
1. [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution Guidelines
2. [development/RELEASE_PROCESS.md](development/RELEASE_PROCESS.md) - Release-Workflow
3. [security/SECRET_LEAK_RESPONSE.md](security/SECRET_LEAK_RESPONSE.md) - Incident Response

## 🆘 Hilfe benötigt?

- **Fehler gefunden?** → [Bug Report](https://github.com/arn-c0de/Crawllama/issues/new?template=bug_report.yml)
- **Feature-Wunsch?** → [Feature Request](https://github.com/arn-c0de/Crawllama/issues/new?template=feature_request.yml)
- **Dokumentation unklar?** → [Documentation Issue](https://github.com/arn-c0de/Crawllama/issues/new?template=documentation.yml)

---

**Zurück zur [Hauptseite](../README.md)** | **[License](../LICENSE)** | **[Contributing](../CONTRIBUTING.md)**
