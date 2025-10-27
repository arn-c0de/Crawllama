# Search Engine Limitations

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🚀 Quickstart](../getting-started/QUICKSTART.md) | [🧠 LangGraph](LANGGRAPH_GUIDE.md) | [🔌 Plugins](PLUGIN_TUTORIAL.md)

---

## DuckDuckGo Result Limit

### Problem
DuckDuckGo often limits the number of search results to **10 results**, regardless of how many results are requested. This is a known limitation of the DuckDuckGo API/DDGS library.

### Configuration
In `config.json`, you can configure the maximum number of results:

```json
{
  "search": {
    "max_results": 25,  // For normal web searches
    ...
  },
  "osint": {
    "max_results": 25,  // For OSINT/site: searches
    ...
  }
}
```

**Note:** Even if you set `max_results: 25`, DuckDuckGo may still only return 10 results.

### Solutions

#### 1. Fallback to Other Search Engines
If more results are needed, you can use alternative search providers:

```json
{
  "search": {
    "provider": "brave",  // or "serper"
    "fallback_providers": ["duckduckgo"]
  }
}
```

**Brave Search** and **Serper** support more results:
- Brave: up to 20+ results
- Serper: up to 100+ results (with API key)

#### 2. Multiple Searches with Different Keywords
Instead of a single search, you can perform multiple searches with more specific keywords:

```
site:example.com product
site:example.com service
site:example.com contact
```

#### 3. Pagination (Not Supported)
DuckDuckGo does not support true pagination via the DDGS API.

### Current Implementation
CrawlLama automatically logs a warning when fewer results are returned than requested:

```
⚠️ DuckDuckGo returned only 10 results (requested: 25). This is a known limitation.
```

### Recommendation
For OSINT analyses with many results:
1. Set `"provider": "brave"` in config.json
2. Or use Serper with an API key
3. Or perform multiple specific searches

### Setting Up API Keys

#### Serper (Recommended for Many Results)
1. Register at https://serper.dev/
2. Get a free API key (2500 requests/month)
3. Set the environment variable: `SERPER_API_KEY=your_key_here`

#### Brave Search
1. Register at https://brave.com/search/api/
2. Get a free API key (2000 requests/month)
3. Set the environment variable: `BRAVE_API_KEY=your_key_here`

### Status
- ✅ DuckDuckGo: Free, no API keys, but only ~10 results
- ✅ Brave: Free (with API key), up to 20+ results
- ✅ Serper: Free (with API key), up to 100+ results

---

**Last Updated:** October 24, 2025
