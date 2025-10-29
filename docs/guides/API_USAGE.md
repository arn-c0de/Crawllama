# CrawlLama API Usage Guide

Complete guide for using the CrawlLama REST API.

## Table of Contents

- [Quick Start](#quick-start)
- [Authentication](#authentication)
- [Base URL](#base-url)
- [Rate Limiting](#rate-limiting)
- [Endpoints](#endpoints)
  - [Health & Info](#health--info)
  - [Query Endpoints](#query-endpoints)
  - [Memory Store](#memory-store)
  - [Cache Management](#cache-management)
  - [Session Management](#session-management)
  - [Configuration](#configuration)
  - [Plugins & Tools](#plugins--tools)
  - [OSINT](#osint)
- [Error Handling](#error-handling)
- [Examples](#examples)

---

## Quick Start

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

- **API Root:** http://localhost:8000
- **Interactive Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## Authentication

### API Key Authentication

Set your API key in `.env`:
```bash
CRAWLLAMA_API_KEY=your-secret-key-here
```

Include the API key in requests:
```bash
curl -H "X-API-Key: your-secret-key-here" http://localhost:8000/query
```

### Development Mode

For testing without API key:
```bash
CRAWLLAMA_DEV_MODE=true
```

⚠️ **Never use DEV_MODE in production!**

---

## Base URL

```
http://localhost:8000
```

For production, use your deployed URL with HTTPS.

---

## Rate Limiting

- **Default:** 60 requests per minute
- **Configurable:** Set `RATE_LIMIT` in `.env`
- **429 Error:** Rate limit exceeded

---

## Endpoints

### Health & Info

#### `GET /` - API Information
```bash
curl http://localhost:8000/
```

**Response:**
```json
{
  "name": "CrawlLama API",
  "version": "1.4.2",
  "description": "AI-powered web research agent",
  "docs": "/docs",
  "health": "/health"
}
```

#### `GET /health` - Health Check
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-26T15:30:00",
  "version": "1.4.2",
  "components": {
    "agent": "healthy",
    "multihop_agent": "healthy",
    "memory_store": "healthy"
  }
}
```

#### `GET /stats` - System Statistics
```bash
curl -H "X-API-Key: your-key" http://localhost:8000/stats
```

#### `GET /security-info` - Security Configuration
```bash
curl http://localhost:8000/security-info
```

---

### Query Endpoints

#### `POST /query` - Submit Query

**Simple Query:**
```bash
curl -X POST http://localhost:8000/query \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is Python?",
    "use_tools": false
  }'
```

**With Web Search:**
```bash
curl -X POST http://localhost:8000/query \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Latest AI developments 2025",
    "use_tools": true
  }'
```

**Multi-Hop Reasoning:**
```bash
curl -X POST http://localhost:8000/query \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare Python vs JavaScript for web development",
    "use_multihop": true,
    "max_hops": 3
  }'
```

**Request Parameters:**
- `query` (string, required): Search query
- `use_tools` (boolean): Enable web search (default: true)
- `use_multihop` (boolean): Use multi-hop reasoning (default: false)
- `max_hops` (integer): Maximum reasoning hops, 1-5 (default: 3)

**Response:**
```json
{
  "answer": "Python is a high-level programming language...",
  "confidence": 0.92,
  "steps": 3,
  "search_queries": ["python programming", "python features"],
  "reasoning_path": ["Define Python", "List features", "Conclude"],
  "elapsed_time": 2.45,
  "cached": false
}
```

---

### Memory Store

Store and retrieve OSINT findings persistently.

#### `POST /memory/remember` - Store Data
```bash
curl -X POST http://localhost:8000/memory/remember \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "email",
    "value": "contact@example.com"
  }'
```

**Supported Categories:**
- `email` / `emails`
- `phone` / `phones`
- `ip` / `ips`
- `username` / `usernames`
- `domain` / `domains`
- `note` / `notes`

#### `GET /memory/recall/{category}` - Retrieve Data
```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/memory/recall/emails
```

**Response:**
```json
{
  "status": "success",
  "category": "emails",
  "count": 3,
  "results": [
    {
      "value": "contact@example.com",
      "added_at": "2025-10-26T15:30:00",
      "metadata": {}
    }
  ]
}
```

#### `GET /memory/stats` - Memory Statistics
```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/memory/stats
```

#### `DELETE /memory/forget` - Delete Data

**Delete specific value:**
```bash
curl -X DELETE http://localhost:8000/memory/forget \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "email",
    "value": "contact@example.com"
  }'
```

**Clear entire category:**
```bash
curl -X DELETE http://localhost:8000/memory/forget \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "emails"
  }'
```

**Clear all memory:**
```bash
curl -X DELETE http://localhost:8000/memory/forget \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "all"
  }'
```

---

### Cache Management

#### `GET /cache/stats` - Cache Statistics
```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/cache/stats
```

#### `POST /cache/clear` - Clear Cache
```bash
curl -X POST http://localhost:8000/cache/clear \
  -H "X-API-Key: your-key"
```

---

### Session Management

#### `POST /session/save` - Save Session
```bash
curl -X POST http://localhost:8000/session/save \
  -H "X-API-Key: your-key"
```

#### `POST /session/load` - Load Session
```bash
curl -X POST http://localhost:8000/session/load \
  -H "X-API-Key: your-key"
```

#### `POST /session/clear` - Clear Session
```bash
curl -X POST http://localhost:8000/session/clear \
  -H "X-API-Key: your-key"
```

---

### Configuration

#### `GET /config` - Get Configuration
```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/config
```

**Response:** (Sensitive values redacted)
```json
{
  "status": "success",
  "data": {
    "llm": {
      "model": "qwen3:4b",
      "temperature": 0.7
    },
    "search": {
      "brave_api_key": "***REDACTED***"
    }
  },
  "note": "Sensitive values are redacted for security"
}
```

#### `PATCH /config` - Update Configuration
```bash
curl -X PATCH http://localhost:8000/config \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "llm",
    "key": "temperature",
    "value": 0.8
  }'
```

⚠️ **Note:** API restart required for changes to take effect.

#### `GET /context/status` - Context Manager Status
```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/context/status
```

---

### Plugins & Tools

#### `GET /plugins` - List Plugins
```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/plugins
```

**Response:**
```json
{
  "available": ["example_plugin"],
  "loaded": ["example_plugin"],
  "count": {
    "available": 1,
    "loaded": 1
  }
}
```

#### `POST /plugins/{plugin_name}/load` - Load Plugin
```bash
curl -X POST http://localhost:8000/plugins/example_plugin/load \
  -H "X-API-Key: your-key"
```

#### `POST /plugins/{plugin_name}/unload` - Unload Plugin
```bash
curl -X POST http://localhost:8000/plugins/example_plugin/unload \
  -H "X-API-Key: your-key"
```

#### `GET /tools` - List Tools
```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/tools
```

---

### OSINT

#### `POST /osint/query` - OSINT Query with Operators

**Email Search:**
```bash
curl -X POST http://localhost:8000/osint/query \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "email:contact@example.com"
  }'
```

**Phone Search:**
```bash
curl -X POST http://localhost:8000/osint/query \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "phone:+1234567890"
  }'
```

**IP Lookup:**
```bash
curl -X POST http://localhost:8000/osint/query \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "ip:192.168.1.1"
  }'
```

**Supported Operators:**
- `email:` - Email address lookup
- `phone:` - Phone number lookup
- `ip:` - IP address lookup
- `domain:` - Domain information
- `username:` - Username search

---

## Error Handling

### HTTP Status Codes

- **200:** Success
- **400:** Bad Request (invalid input)
- **401:** Unauthorized (missing/invalid API key)
- **422:** Validation Error (invalid parameters)
- **429:** Too Many Requests (rate limit exceeded)
- **500:** Internal Server Error
- **503:** Service Unavailable (component not initialized)

### Error Response Format

```json
{
  "detail": "Invalid or missing API key",
  "type": "HTTPException"
}
```

---

## Examples

### Python Example

```python
import requests

API_URL = "http://localhost:8000"
API_KEY = "your-secret-key"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Simple query
response = requests.post(
    f"{API_URL}/query",
    headers=headers,
    json={
        "query": "What is machine learning?",
        "use_tools": True
    }
)

result = response.json()
print(f"Answer: {result['answer']}")
print(f"Time: {result['elapsed_time']}s")

# Remember email
requests.post(
    f"{API_URL}/memory/remember",
    headers=headers,
    json={
        "category": "email",
        "value": "test@example.com"
    }
)

# Recall emails
response = requests.get(
    f"{API_URL}/memory/recall/emails",
    headers=headers
)
emails = response.json()
print(f"Found {emails['count']} emails")
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

const API_URL = 'http://localhost:8000';
const API_KEY = 'your-secret-key';

const headers = {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
};

// Query with multi-hop reasoning
async function query() {
    const response = await axios.post(`${API_URL}/query`, {
        query: "Compare Python vs JavaScript",
        use_multihop: true,
        max_hops: 3
    }, { headers });

    console.log('Answer:', response.data.answer);
    console.log('Steps:', response.data.steps);
    console.log('Confidence:', response.data.confidence);
}

// Get cache stats
async function getCacheStats() {
    const response = await axios.get(`${API_URL}/cache/stats`, { headers });
    console.log('Cache Stats:', response.data);
}

query();
getCacheStats();
```

### cURL Examples Collection

**Health check (no auth):**
```bash
curl http://localhost:8000/health
```

**Query with web search:**
```bash
curl -X POST http://localhost:8000/query \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "Latest Python news", "use_tools": true}'
```

**Multi-hop reasoning:**
```bash
curl -X POST http://localhost:8000/query \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain quantum computing", "use_multihop": true}'
```

**Store and retrieve memory:**
```bash
# Store
curl -X POST http://localhost:8000/memory/remember \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"category": "email", "value": "contact@example.com"}'

# Retrieve
curl -H "X-API-Key: your-key" \
  http://localhost:8000/memory/recall/emails
```

---

## Security Best Practices

1. **Always use HTTPS in production**
2. **Keep API key secret** - Never commit to git
3. **Set strong API key** - Use `secrets.token_urlsafe(32)`
4. **Configure CORS properly** - Don't use wildcard in production
5. **Set ALLOWED_HOSTS** - Restrict to your domain
6. **Monitor rate limits** - Adjust based on your needs
7. **Disable DEV_MODE** - Only for local testing

---

## Environment Variables

```bash
# Required
CRAWLLAMA_API_KEY=your-secret-key-here

# Optional
RATE_LIMIT=60
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com
CRAWLLAMA_DEV_MODE=false

# Search APIs (optional)
BRAVE_API_KEY=your-brave-key
SERPER_API_KEY=your-serper-key
```

---

## Troubleshooting

### API Won't Start

1. Check if port 8000 is available
2. Verify Python dependencies installed
3. Check `config.json` is valid
4. Review logs for errors

### 503 Service Unavailable

- Component not initialized (agent, memory_store, etc.)
- Check health endpoint for component status
- Review startup logs

### 401 Unauthorized

- Missing or invalid API key
- Set `X-API-Key` header
- Or enable `CRAWLLAMA_DEV_MODE=true` for testing

### 429 Rate Limit

- Exceeded 60 requests/minute (default)
- Wait or increase `RATE_LIMIT` in `.env`

---

## Support

- **Documentation:** [docs/README.md](README.md)
- **Issues:** [GitHub Issues](https://github.com/arn-c0de/Crawllama/issues)
- **Security:** See [SECURITY.md](../SECURITY.md)

---

**Last Updated:** October 26, 2025  
**Version:** 1.4.2
