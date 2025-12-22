# RAG Implementation - Complete Analysis

[Zurück zur Übersicht](../README.md)

---

# RAG Implementation - Complete Analysis
## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Vector Store (ChromaDB)](#vector-store-chromadb)
4. [Memory Systems](#memory-systems)
5. [Document Processing](#document-processing)
6. [Retrieval Mechanisms](#retrieval-mechanisms)
7. [Complete Workflow](#complete-workflow)
8. [Configuration](#configuration)
9. [Code References](#code-references)
---
## Overview
The CrawlLama system implements RAG (Retrieval Augmented Generation) using **ChromaDB** as the vector store. RAG enables semantic searches over crawled web content and uses it as context for LLM responses.
### Core Components
| Component | File | Function |
|-----------|------|----------|
| RAGManager | `tools/rag.py` | Main class for RAG operations |
| ChromaDB | Vector Store | Semantic document search |
| ContextManager | `core/context_manager.py` | Chunking & Prompt Building |
| ToolRegistry | `tools/tool_registry.py` | Integration into Agent Workflow |
---
## Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                      USER QUERY                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   AGENT (SearchAgent)                       │
│  - Analyzes query complexity                                │
│  - Selects tool: web_search, wiki_lookup, or rag_search    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   RAG SEARCH TOOL                           │
│  RAGManager.search(query, top_k=5)                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   CHROMADB QUERY                            │
│  - Query embedding with "nomic-embed-text"                  │
│  - Cosine Similarity Search                                 │
│  - Returns: Top-K most similar documents                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               FORMAT RAG RESULTS                            │
│  - Truncate text (max 300 characters)                       │
│  - Add source & relevance score                             │
│  Format: "[Source: url] (Relevance: 0.85)"                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              CONTEXT BUILDING                               │
│  ContextManager.build_prompt()                              │
│  - Combines: system_prompt + rag_results + user_query       │
│  - Truncate to max_context_tokens (4000-16000)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│             LLM GENERATION (Ollama)                         │
│  - Sends prompt to local LLM                                │
│  - Optional: Hallucination Detection                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   RESPONSE                                  │
│  Formatted response with source attribution                 │
└─────────────────────────────────────────────────────────────┘
```
---
## Vector Store (ChromaDB)
### Initialization
**File:** `tools/rag.py:49-63`
```python
# ChromaDB Settings
Settings(
    persist_directory="data/embeddings",
    anonymized_telemetry=False
)
# Client Creation
self.client = chromadb.PersistentClient(
    path="data/embeddings"
)
# Collection Setup
self.collection = self.client.get_or_create_collection(
    name="web_documents",
    metadata={"hnsw:space": "cosine"}  # Cosine Similarity
)
```
### Embedding Model
- **Model:** `nomic-embed-text`
- **Automatically managed by ChromaDB**
- **Download Path:** `data/models/`
- **Configuration:** `config.json:26`
### Storage
- **Persistence Directory:** `data/embeddings/`
- **Automatic saving** on every `.add()` or `.upsert()`
- **Collection Name:** `web_documents` (configurable)
### Fallback Mode
**File:** `tools/rag.py:46-76, 94-96`
If ChromaDB is unavailable:
```python
except Exception as e:
    logger.warning(f"RAG system initialization failed: {e}")
    logger.warning("RAG functionality will be disabled")
    self.client = None
    self.collection = None
```
→ System continues without RAG capability
---
## Memory Systems
### Two Separate Systems!
#### 1. RAG Document Store (ChromaDB)
**Purpose:** Semantic search over web content
| Property | Value |
|----------|-------|
| Storage | `data/embeddings/` |
| Persistence | Automatic via ChromaDB |
| Content | Crawled web pages, search results |
| Access | Semantic similarity search |
#### 2. Memory Store (JSON)
**Purpose:** OSINT data (emails, phones, IPs, usernames)
| Property | Value |
|----------|-------|
| File | `core/memory_store.py` |
| Storage | `data/memory.json` |
| Content | Structured intelligence data with metadata |
| Access | Direct JSON access |
**IMPORTANT:** Memory Store is NOT used for RAG!
---
## Document Processing
### 1. Chunking Strategy
**File:** `core/context_manager.py:56-101`
```python
def split_into_chunks(text: str,
                      chunk_size: int = 500,  # Tokens
                      overlap: int = 50) -> List[str]:
```
**Algorithm:**
1. **Character Estimation:** 4 characters = 1 token
2. **Max Chunk Size:** `chunk_size * 4` characters
3. **Overlap:** `overlap * 4` characters between chunks
4. **Smart Splitting:**
   - Breaks at sentence boundaries (`.`, `?`, `!`)
   - Prevents truncation mid-sentence
   - Maintains context continuity via overlap
**Example:**
```
Chunk 1: "This is the first sentence. And the second sentence."
         ↓ (Overlap 50 tokens)
Chunk 2: "And the second sentence. Here comes the third."
```
### 2. Adding Documents
**File:** `tools/rag.py:78-127`
```python
def add_documents(texts: List[str],
                  metadatas: Optional[List[dict]] = None,
                  ids: Optional[List[str]] = None,
                  use_batch: bool = True) -> None
```
**Pipeline:**
```
INPUT: texts, metadatas, ids
      ↓
1. ID GENERATION (if not provided)
   - MD5 hash of text (first 16 characters)
   - Prevents duplicates
      ↓
2. METADATA PREPARATION
   - Default: {"source": "unknown"}
   - Customizable per document
      ↓
3. BATCH PROCESSING
   - Threshold: 100 documents
   - Processes in batches
   - Progress logging
      ↓
4. CHROMADB INDEXING
   - collection.add(documents=texts, metadatas=metadatas, ids=ids)
   - Automatic embedding with nomic-embed-text
   - Persistence to disk
      ↓
OUTPUT: Documents indexed & searchable
```
**Important Note:**
- **No automatic indexing** of web search results!
- **Manual indexing required:**
  ```python
  agent.add_to_knowledge_base(
      texts=["Document 1", "Document 2"],
      metadatas=[{"source": "url1"}, {"source": "url2"}]
  )
  ```
### 3. Deduplication
**File:** `tools/rag.py:103-104`
```python
# Generate MD5 hash as ID
doc_id = hashlib.sha256(text.encode()).hexdigest()
```
→ Same text = same ID → Automatic deduplication by ChromaDB
---
## Retrieval Mechanisms
### 1. Standard Search
**File:** `tools/rag.py:167-226`
```python
def search(query: str,
           top_k: int = 5,
           filter_metadata: Optional[dict] = None,
           min_relevance: float = 0.0) -> List[Dict]
```
**Process:**
1. Query embedding with `nomic-embed-text`
2. ChromaDB `.query()` with cosine similarity
3. Conversion: `relevance = 1.0 - distance`
4. Filtering: Only results >= `min_relevance`
**Return Format:**
```python
{
    "text": "Document content...",
    "metadata": {"source": "https://example.com"},
    "distance": 0.15,        # Cosine distance
    "relevance": 0.85,       # 1.0 - distance
    "id": "abc123def456"
}
```
### 2. Multi-Query Search
**File:** `tools/rag.py:227-279`
```python
def multi_query_search(queries: List[str],
                       top_k: int = 5,
                       deduplicate: bool = True) -> List[Dict]
```
**Use Case:** Query expansion / reformulation
**Process:**
1. **Parallel execution** with `ThreadPoolExecutor` (max 4 workers)
2. Each query searched separately
3. **Deduplication** (if enabled):
   - Groups results by document ID
   - Keeps best relevance score per document
4. **Sorting** by relevance (highest first)
**Example:**
```python
queries = [
    "AI in healthcare",
    "medical AI systems",
    "artificial intelligence diagnosis"
]
results = rag.multi_query_search(queries, top_k=10)
```
### 3. Hybrid Search
**File:** `tools/rag.py:281-318`
```python
def hybrid_search(query: str,
                  top_k: int = 5,
                  semantic_weight: float = 0.7) -> List[Dict]
```
**Combination:** Semantic + keyword search
**Process:**
1. Generate query variants:
   - Original query
   - Lowercase version
   - First 3 words
2. Multi-query search with all variants
3. Weighting: `semantic_weight` (0.0 - 1.0)
---
## Complete Workflow
### Scenario: User asks "What is RAG in AI?"
#### Step 1: Query Analysis
**File:** `core/agent.py:138-143`
```python
# Agent receives query
query = "What is RAG in AI?"
# Agent decides tool usage
# Options: web_search, wiki_lookup, rag_search
```
#### Step 2: RAG Search (if selected)
**File:** `tools/rag.py:167-226`
```python
results = rag_manager.search(
    query="What is RAG in AI?",
    top_k=5,
    min_relevance=0.5
)
```
**Internal ChromaDB Operations:**
```python
# 1. Query Embedding
query_embedding = embed_model.encode("What is RAG in AI?")
# 2. Similarity Search
db_results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5
)
# 3. Relevance Calculation
for i, distance in enumerate(db_results['distances'][0]):
    relevance = 1.0 - distance
```
#### Step 3: Result Formatting
**File:** `tools/rag.py:380-413`
```python
formatted = format_rag_results(results, max_length=300)
```
**Output:**
```
1. [Source: https://example.com/rag] (Relevance: 0.92)
   RAG (Retrieval Augmented Generation) is a technique that...
2. [Source: https://ai-docs.org/rag-guide] (Relevance: 0.87)
   In RAG, relevant documents are retrieved from a database...
```
#### Step 4: Context Building
**File:** `core/context_manager.py:119-155`
```python
prompt = build_prompt(
    system_prompt="You are a helpful AI assistant.",
    user_query="What is RAG in AI?",
    context=formatted_rag_results,
    max_context_tokens=4000
)
```
**Final Prompt:**
```
You are a helpful AI assistant.
**Context:**
1. [Source: https://example.com/rag] (Relevance: 0.92)
   RAG (Retrieval Augmented Generation) is a technique that...
2. [Source: https://ai-docs.org/rag-guide] (Relevance: 0.87)
   In RAG, relevant documents are retrieved from a database...
**Question:** What is RAG in AI?
```
#### Step 5: Token Management
**File:** `core/context_manager.py:133-145`
```python
# Token Counting
system_tokens = count_tokens(system_prompt)
query_tokens = count_tokens(user_query)
context_tokens = count_tokens(context)
# Truncation if needed
if context_tokens > max_context_tokens:
    context = truncate_text(context, max_context_tokens)
```
#### Step 6: LLM Generation
**File:** `core/agent.py` + `core/ollama_client.py`
```python
response = ollama_client.generate(
    prompt=final_prompt,
    model="llama2",  # or configured model
    temperature=0.7
)
```
#### Step 7: Response to User
```
RAG (Retrieval Augmented Generation) combines information
retrieval with LLM generation. Relevant documents are retrieved
from a knowledge base and used as context for the LLM response.
This reduces hallucinations and enables up-to-date, fact-based answers.
Sources:
- https://example.com/rag (Relevance: 0.92)
- https://ai-docs.org/rag-guide (Relevance: 0.87)
```
---
## Configuration
### config.json RAG Settings
**File:** `config.json:24-30`
```json
{
  "rag": {
    "enabled": true,
    "embedding_model": "nomic-embed-text",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "top_k": 10
  }
}
```
### Path Configuration
```json
{
  "paths": {
    "embeddings_dir": "data/embeddings"
  }
}
```
### Context Limits
```json
{
  "context_limits": {
    "small": 4000,
    "medium": 6000,
    "large": 8000,
    "xlarge": 12000,
    "max_storage": 8000
  }
}
```
**Optimized for RTX 3080:**
- Max Context Window: 16000 Tokens
- Default: 4000 Tokens for RAG Context
### Runtime Parameters
| Parameter | Value | Description |
|-----------|-------|-------------|
| batch_size | 100 | Documents per batch |
| max_workers | 4 | Threads for parallel search |
| similarity_metric | cosine | Distance metric |
| min_relevance | 0.0 | Minimum relevance score |
---
## Code References
### Main Implementations
| File | Lines | Description |
|------|-------|-------------|
| `tools/rag.py` | 1-413 | **Complete RAG Implementation** |
| | 49-63 | ChromaDB Initialization |
| | 78-127 | `add_documents()` - Document Indexing |
| | 167-226 | `search()` - Standard Search |
| | 227-279 | `multi_query_search()` - Parallel Multi-Query |
| | 281-318 | `hybrid_search()` - Hybrid Semantic+Keyword |
| | 380-413 | `format_rag_results()` - Result Formatting |
### Integration
| File | Lines | Description |
|------|-------|-------------|
| `tools/tool_registry.py` | 8, 34-42 | RAG Import & Lazy Loading |
| | 79-89 | RAG Tool Definition |
| | 144-178 | `add_documents_to_rag()` API |
| `core/agent.py` | 138-143 | RAG Tool Initialization |
| | 1490-1501 | `add_to_knowledge_base()` Public API |
### Context Management
| File | Lines | Description |
|------|-------|-------------|
| `core/context_manager.py` | 56-101 | `split_into_chunks()` - Chunking |
| | 119-155 | `build_prompt()` - Prompt Construction |
| | 103-117 | `truncate_text()` - Smart Truncation |
### Configuration
| File | Lines | Description |
|------|-------|-------------|
| `config.json` | 24-30 | RAG Settings |
| `core/unified_loader.py` | 54-58 | Lazy-Loading Config |
---
## Key Insights
### ✅ Strengths
1. **Graceful Degradation:** Fallback if ChromaDB unavailable
2. **Parallel Processing:** ThreadPoolExecutor for multi-query
3. **Smart Chunking:** Sentence-based splitting with overlap
4. **Flexible Search:** Standard, multi-query, hybrid modes
5. **Lazy Loading:** RAG as "heavy" tool loaded on-demand
6. **Deduplication:** MD5 hashing prevents duplicates
### ⚠️ Limitations
1. **No Auto-Indexing:** Web search results NOT automatically added to RAG
2. **Manual Population:** User must explicitly index documents
3. **Single Collection:** All documents in one collection
4. **No Update Mechanism:** No built-in method to update existing docs
5. **Simple Metadata:** Only source-based metadata structure
### 🎯 Use Cases
#### Currently Implemented:
- Manual indexing of documents
- Semantic search over indexed content
- Multi-query expansion for better recall
#### Not Implemented:
- Automatic indexing of web crawl results
- Incremental updates of documents
- Multi-tenancy (separate collections per user)
---
## Usage Examples
### 1. Adding Documents
```python
# Via Agent API
agent = SearchAgent(config)
agent.add_to_knowledge_base(
    texts=[
        "RAG combines retrieval with generation.",
        "ChromaDB is a vector database."
    ],
    metadatas=[
        {"source": "https://rag-tutorial.com"},
        {"source": "https://chromadb.docs"}
    ]
)
```
### 2. Standard Search
```python
# Via RAGManager
rag = RAGManager()
results = rag.search(
    query="What is a vector database?",
    top_k=5,
    min_relevance=0.5
)
for result in results:
    print(f"[{result['relevance']:.2f}] {result['text'][:100]}...")
```
### 3. Multi-Query Search
```python
# Query Expansion
queries = [
    "Vector Database",
    "Embedding storage systems",
    "Semantic search databases"
]
results = rag.multi_query_search(
    queries=queries,
    top_k=10,
    deduplicate=True
)
```
### 4. Hybrid Search
```python
# Semantic + Keyword Combination
results = rag.hybrid_search(
    query="ChromaDB features",
    top_k=5,
    semantic_weight=0.7  # 70% semantic, 30% keyword
)
```
---
## Summary
The CrawlLama RAG system uses **ChromaDB** for semantic document search with the **nomic-embed-text** embedding model. The workflow is:
1. **Indexing:** Documents manually added via `add_to_knowledge_base()`
2. **Chunking:** Texts split into 500-token chunks with 50-token overlap
3. **Embedding:** ChromaDB automatically creates embeddings
4. **Retrieval:** Cosine similarity search finds most similar documents
5. **Context Building:** Results formatted and inserted into LLM prompt
6. **Generation:** Local Ollama LLM generates response based on context
**Important:** The system clearly separates:
- **RAG Store** (ChromaDB) for semantic search
- **Memory Store** (JSON) for structured OSINT data
Web search results are NOT automatically indexed - this must be done manually.