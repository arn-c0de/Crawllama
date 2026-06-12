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

#### POST /query-adaptive
Executes a query via the Adaptive Hopping System, which selects the best agent automatically based on query complexity.
- **Body Parameters:**
    - `query` (string): The search query or question.
    - `force_complexity` (string, optional): Override automatic complexity detection.
    - `enable_escalation` (boolean, optional): Allow escalation to a stronger agent on low confidence.

#### POST /osint/query
Executes a specialized OSINT query using operators.
- **Examples:** `email:test@example.com`, `ip:8.8.8.8`, `phone:+123456789`.

#### POST /osint/company
Executes a company-focused OSINT query.
- **Payload:** `{"company_name": "Example GmbH", "country": "Germany"}` (`region` and `language` are also supported).

### Memory Management

#### GET /memory
Retrieves all stored entries across every category.

#### GET /memory/recall/{category}
Retrieves stored intelligence (emails, phones, IPs, domains, usernames, notes).

#### GET /memory/stats
Returns memory store statistics.

#### POST /memory/remember
Stores a new piece of intelligence.
- **Payload:** `{"category": "email", "value": "target@example.com"}`

#### DELETE /memory/forget
Deletes specific entries or entire categories.

### System and Diagnostics

#### GET /api
Returns machine-readable API information (name, version, documentation links). `GET /` serves the HTML web interface.

#### GET /health
Returns the status of all system components (LLM, Cache, RAG, Agent).

#### GET /stats
Returns operational statistics, including token usage and performance metrics.

#### GET /config
Retrieves the current active configuration (sensitive values are redacted).

#### PATCH /config
Updates a single configuration value. Requires the **admin** role.
- **Payload:** `{"category": "llm", "key": "temperature", "value": 0.8}`

#### GET /context/status
Returns context manager status (token usage and available capacity).

#### GET /security-info
Returns the active security configuration (rate limits, enabled features).

## Cache and Session

- **GET /cache/stats:** Returns cache statistics.
- **POST /cache/clear:** Flushes the search and reasoning cache.
- **POST /session/save:** Persists the current session state to the database.
- **POST /session/load:** Reloads the persisted session state.
- **POST /session/clear:** Resets the current conversation history.
- **POST /session/refresh:** Extends the session expiration by 24 hours.

## Plugin Management

- **GET /plugins:** Lists all available and loaded plugins.
- **POST /plugins/{name}/load:** Dynamically loads a verified plugin. (Admin only)
- **POST /plugins/{name}/unload:** Safely unloads a plugin. (Admin only)
- **GET /tools:** Lists all available tools.

## Security and Administration

Outside DEV_MODE, state-changing requests (`POST`/`PATCH`/`DELETE`) additionally require a CSRF token in the `X-CSRF-Token` header.

#### POST /csrf-token
Issues a CSRF token bound to your API key (expires after 1 hour by default).

#### Role Management (RBAC)
- **POST /admin/roles/assign:** Assigns a role (`admin`, `user`, `read_only`) to an API key. (Admin only)
- **GET /admin/roles/list:** Lists all role assignments. (Admin only)
- **GET /admin/roles/me:** Returns your own role and permissions.
- **DELETE /admin/roles/revoke:** Resets a key to the default role. (Admin only)
- **GET /admin/roles/stats:** Returns RBAC statistics. (Admin only)

#### Audit Logs
- **GET /admin/audit/logs:** Queries audit logs with optional filters (`event_type`, `user_id`, `status`, `limit`). (Admin only)
- **GET /admin/audit/stats:** Returns audit log statistics. (Admin only)

#### API Key Management
- **POST /admin/api-keys/generate:** Generates a new API key. (Admin only)
- **POST /admin/api-keys/rotate:** Rotates your own key; the old key stays active until revoked.
- **GET /admin/api-keys/list:** Lists your keys (metadata only).
- **DELETE /admin/api-keys/revoke/{key_id}:** Revokes a key by ID (own keys only, unless admin).

#### GET /dev/api-key
Returns the auto-generated temporary API key. Only available in DEV_MODE from a loopback client.

## Error Handling

The API returns standard HTTP status codes:
- `200`: Success.
- `400`: Bad Request (Invalid input or plugin name).
- `401`: Unauthorized (Invalid or missing API key).
- `403`: Forbidden (Missing/invalid CSRF token or insufficient role).
- `429`: Too Many Requests (Rate limit exceeded).
- `500`: Internal Server Error.
- `503`: Service Unavailable (Component initialization failure).

---
[Back to Home](Home.md)
