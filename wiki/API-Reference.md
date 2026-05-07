# API Reference

CrawlLama provides a robust REST API powered by FastAPI, allowing for seamless integration into custom applications and automated workflows.

## Authentication

Authentication is handled via an API Key passed in the `X-API-Key` header.

```bash
# Set in .env
CRAWLLAMA_API_KEY=your_secure_api_key
```

For local testing, `CRAWLLAMA_DEV_MODE=true` can be set to bypass authentication.

## Core Endpoints

### Query Operations

#### POST /query
Executes a research query.
- **Body Parameters:**
    - `query` (string): The search query or question.
    - `use_tools` (boolean): Enable web search and other tools.
    - `use_multihop` (boolean): Enable LangGraph-based reasoning.
    - `max_hops` (integer): Maximum reasoning steps (1-5).

#### POST /osint/query
Executes a specialized OSINT query using operators.
- **Examples:** `email:test@example.com`, `ip:8.8.8.8`, `phone:+123456789`.

### Memory Management

#### GET /memory/recall/{category}
Retrieves stored intelligence (emails, phones, IPs, domains, usernames).

#### POST /memory/remember
Stores a new piece of intelligence.
- **Payload:** `{"category": "email", "value": "target@example.com"}`

#### DELETE /memory/forget
Deletes specific entries or entire categories.

### System and Diagnostics

#### GET /health
Returns the status of all system components (LLM, Cache, RAG, Agent).

#### GET /stats
Returns operational statistics, including token usage and performance metrics.

#### GET /config
Retrieves the current active configuration (sensitive values are redacted).

## Cache and Session

- **POST /cache/clear:** Flushes the search and reasoning cache.
- **POST /session/save:** Persists the current session state to the database.
- **POST /session/clear:** Resets the current conversation history.

## Plugin Management

- **GET /plugins:** Lists all available and loaded plugins.
- **POST /plugins/{name}/load:** Dynamically loads a verified plugin.
- **POST /plugins/{name}/unload:** Safely unloads a plugin.

## Error Handling

The API returns standard HTTP status codes:
- `200`: Success.
- `401`: Unauthorized (Invalid or missing API key).
- `429`: Too Many Requests (Rate limit exceeded).
- `500`: Internal Server Error.
- `503`: Service Unavailable (Component initialization failure).

---
[Back to Home](Home.md)
