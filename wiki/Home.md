# CrawlLama Wiki

CrawlLama is a high-performance, local AI Research Agent engineered for advanced Open Source Intelligence (OSINT) and complex multi-hop reasoning. It utilizes local Large Language Models (LLMs) via Ollama to provide a secure, private, and highly extensible research environment.

---

## Table of Contents
1. [Introduction](#introduction)
2. [Architecture](#architecture)
3. [Key Features](#key-features)
    - [Adaptive Intelligence](#adaptive-intelligence)
    - [Multi-Hop Reasoning](#multi-hop-reasoning)
    - [OSINT Intelligence Suite](#osint-intelligence-suite)
    - [RAG and Search](#rag-and-search)
4. [Interfaces and Tooling](#interfaces-and-tooling)
    - [Interactive CLI](#interactive-cli)
    - [FastAPI REST API](#fastapi-rest-api)
    - [Health Monitoring Dashboard](#health-monitoring-dashboard)
5. [Getting Started](#getting-started)
6. [Developer Resources](#developer-resources)

---

## Introduction

CrawlLama is designed for researchers, developers, and security professionals who require a local-first agent capable of executing deep-dive queries. Unlike standard conversational AI, CrawlLama is built to:
- **Execute Multi-Step Reasoning:** Deconstruct complex tasks into sequential research phases.
- **Perform Specialized OSINT:** Utilize dedicated modules for email, phone, IP, and social media analysis.
- **Maintain Privacy:** Process all LLM logic locally (when using a local backend such as Ollama) while maintaining high performance.
- **Scale Effort Dynamically:** Adjust reasoning depth based on task complexity.
- **Operate Anonymously:** Optional Tor mode routes all outbound web traffic (crawling, search, OSINT lookups, cloud LLM calls) through a Tor SOCKS5 proxy with DNS-leak prevention.

## Architecture

The system utilizes a modular, tool-centric architecture:
- **Core Engine:** Manages state, session persistence, and LLM communication.
- **Tool Registry:** Orchestrates external integrations including web search providers (DuckDuckGo, Brave, Serper), Wikipedia, and OSINT modules.
- **Agent Orchestrator:** Powered by LangGraph, managing the iterative flow of Search, Analysis, Critique, and Synthesis.
- **Plugin System:** Supports dynamic loading of custom functionality without core modification.

## Key Features

### Adaptive Intelligence
CrawlLama features an Adaptive Agent Hopping system. It automatically analyzes query intent to select the optimal agent level (Low, Mid, or High complexity). This ensures resource efficiency for simple tasks while providing maximum depth for complex investigations.

### Multi-Hop Reasoning
Utilizing LangGraph, the agent performs iterative research cycles:
1. **Router:** Path determination and initial strategy.
2. **Search:** Data acquisition from multiple sources.
3. **Analyze:** Interpretation of findings and entity extraction.
4. **Follow-Up:** Gap identification and secondary research cycles.
5. **Critique:** Self-evaluation for factual accuracy and hallucination prevention.

### OSINT Intelligence Suite
CrawlLama provides a robust suite of tools for Open Source Intelligence:
- **Email Intelligence:** Validation, MX record analysis, and breach detection.
- **Phone Intelligence:** Carrier identification, normalization, and country detection.
- **IP Intelligence:** Geolocation, ISP verification, and reputation scoring.
- **Social Intelligence:** Automated profile discovery across 12 platforms.
- **Advanced Operators:** Support for `site:`, `inurl:`, `filetype:`, and other advanced search parameters.

### RAG and Search
- **Hybrid Search:** Combines semantic vector search with traditional keyword matching.
- **Intelligent Caching:** Implements TTL-based caching to optimize performance and reduce API latency.
- **Extended Context:** Support for 16k+ tokens (hardware dependent) for deep history maintenance.

## Interfaces and Tooling

### Interactive CLI
A professional terminal interface featuring Markdown rendering, real-time token monitoring, and a comprehensive interactive settings menu.

### FastAPI REST API
Integrate CrawlLama into existing workflows via a robust RESTful interface.
- **Key Endpoints:** `/query`, `/osint/query`, `/memory`, and `/health`.
- **Security:** Integrated API key authentication, CSRF protection, role-based access control, and configurable rate limiting.

### Health Monitoring Dashboard
A live monitoring interface for system-wide visibility:
- **System Metrics:** Real-time tracking of CPU, RAM, and Disk utilization.
- **Component Status:** Health checks for Ollama, RAG, Cache, and Tools.
- **Performance Logs:** Response latency tracking and error diagnostics.

## Getting Started

1. **Install Ollama:** [ollama.com](https://ollama.com)
2. **Clone and Setup:**
   ```bash
   git clone https://github.com/arn-c0de/Crawllama.git
   cd Crawllama
   ./setup.sh  # or setup.bat on Windows
   ```
3. **Run:**
   ```bash
   ./run.sh    # or run.bat
   ```

## Developer Resources

Comprehensive guides for extending and integrating CrawlLama:
- **[Plugin Development](Plugin-Development.md):** Learn how to create custom plugins.
- **[API Reference](API-Reference.md):** Detailed documentation for REST API endpoints.
- **[Architecture Overview](Architecture-Overview.md):** Deep dive into the project structure and code organization.

## Maintenance

### Cloning this Wiki locally
You can clone this wiki to your local machine for offline editing or version control:
```bash
git clone https://github.com/arn-c0de/Crawllama.wiki.git
```

---
*For comprehensive documentation, refer to the [Documentation Overview](https://github.com/arn-c0de/Crawllama/blob/main/docs/README.md).*

