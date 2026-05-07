# Architecture Overview

CrawlLama is designed as a modular, local-first research platform. Its architecture prioritizes privacy, extensibility, and robust error handling.

## Directory Structure

- **core/**: The engine of the application. Contains the agent logic, adaptive hopping system, and LangGraph orchestrator.
- **tools/**: Individual modules for external interactions (Search, Wikipedia, Page Reading, RAG).
- **utils/**: Shared utility functions for logging, validation, rate limiting, and resource monitoring.
- **plugins/**: Directory for user-contributed extensions.
- **data/**: Persistence layer for caching, embeddings, and session history.
- **tests/**: Comprehensive test suite covering unit, integration, and security scenarios.

## Component Stack

### Large Language Model (LLM)
- **Provider:** Ollama (Local).
- **Default Models:** Qwen3, DeepSeek-R1, Llama3.
- **Integration:** Handled via `core/llm_client.py`.

### Agent Orchestration
- **Adaptive Agent:** Dynamically selects agent complexity based on query intent.
- **Multi-Hop Agent:** Uses LangGraph for iterative research and self-critique.
- **Context Manager:** Tracks token usage and manages conversation windows using `tiktoken`.

### Retrieval Augmented Generation (RAG)
- **Vector Database:** ChromaDB.
- **Embeddings:** Sentence Transformers (Local).
- **Functionality:** Provides long-term memory and document-based answering.

### Persistence and Caching
- **Database:** SQLite (Session management).
- **Cache:** TTL-based file system cache for search results and reasoning paths.

## Execution Flow

1. **Input:** User query received via CLI or REST API.
2. **Analysis:** Adaptive complexity detector evaluates the query.
3. **Execution:**
    - Simple queries: Routed to the standard Search Agent.
    - Complex queries: Routed to the LangGraph Multi-Hop Agent.
4. **Tool Use:** Agents utilize the Tool Registry to gather real-time data.
5. **Synthesis:** Findings are processed, critiqued for hallucinations, and synthesized.
6. **Output:** Formatted Markdown response is returned to the user.

## Security Model

- **Local Execution:** No data leaves the machine except for unavoidable web searches.
- **Input Sanitization:** All user inputs are validated before processing.
- **Rate Limiting:** Protects external APIs and local resources.
- **Plugin Sandbox:** Mandatory hash verification for all external code.

---
[Back to Home](Home.md)
