# Adaptive Agent Hopping System
## Overview
The **Adaptive Agent Hopping System** is an intelligent routing layer for **CrawlLama** that automatically selects the optimal agent based on **query complexity**, **system resources**, and **performance metrics**.

### Version
**1.0.0** – Initial Release
---

## Core Functionality
### Automatic Complexity Detection
The system analyzes incoming queries and classifies them into **three complexity levels**: | Complexity | Description | Agent | Tools | Hops |
|------------|-------------|-------|-------|------|
| **LOW** | Simple, factual questions<br>"What is the capital of France?" | SearchAgent | No | 0 |
| **MID** | Questions requiring web search<br>"Latest news about AI" | SearchAgent | Yes | 1 |
| **HIGH** | Multi-step reasoning, comparisons<br>"Compare X and Y, analyze trends" | MultiHopReasoningAgent | Yes | 1–5 |

### Multi-Factor Analysis
Complexity is determined by multiple factors:

1. **Query Length Heuristic**
 - < 50 characters: Tends to be simple
 - 50–150 characters: Medium
 - > 150 characters: Complex

2. **Multi-Part Detection**
 - Keywords: `"and"`, `"also"`, `"compare"`, `"versus"`, `"vs"`
 - Indicates complex queries

3. **Temporal/Sequential Indicators**
 - Keywords: `"after"`, `"before"`, `"then"`, `"first"`, `"next"`, `"steps"`
 - Signals multi-step reasoning

4. **LLM-Based Classification**
 - The LLM semantically analyzes the query
 - Falls back to heuristics on LLM failure

---

## Agent Escalation
The system supports **confidence-based escalation**:

```
LOW Complexity (SearchAgent, no tools)
 ↓ Confidence < 0.5
MID Complexity (SearchAgent with tools)
 ↓ Confidence < 0.5
HIGH Complexity (MultiHopReasoningAgent)
```

### Escalation Parameters
- **Max Escalation Attempts**: 2
- **Confidence Thresholds**:
 - Low: `< 0.5` → Escalate
 - Medium: `0.5 – 0.7`
 - High: `> 0.85`

---

## Resource-Based Adaptation
### Resource Monitoring
The system continuously monitors:
- **CPU Usage** (Threshold: 80%)
- **Memory Usage** (Threshold: 85%)

### Degradation Strategy
Under high resource load:
```
HIGH Complexity → MID Complexity (Downgrade)
Max Hops: 5 → Max Hops: 2 (Degraded Mode)
```
Prevents system overload and ensures stability.

---

## Architecture
### Component Overview
```
┌─────────────────────────────────────────────────────────────┐
│ CrawlLama API │
│ (app.py) │
└────────────────────────┬────────────────────────────────────┘
 │
 ▼
 ┌─────────────────────────────┐
 │ AdaptiveQueryProcessor │
 │ (adaptive_integration.py) │
 └──────────┬──────────────────┘
 │
 ┌────────────┴────────────┐
 ▼ ▼
┌──────────────────┐ ┌──────────────────────┐
│AdaptiveHopManager│ │ Query Execution │
│(adaptive_hops.py)│ │ • SearchAgent │
└──────────────────┘ │ • MultiHopAgent │
 │ └──────────────────────┘
 │
 ┌───┴────┐
 ▼ ▼
┌─────────┐ ┌──────────────┐
│System │ │Performance │
│Monitor │ │Tracker │
└─────────┘ └──────────────┘
```

### Class Structure
#### 1. **AdaptiveHopManager** (`core/adaptive_hops.py`)
Main class for complexity analysis and strategy decisions.

```python
class AdaptiveHopManager:
 def __init__(self, llm, config, system_monitor, performance_tracker)
 # Core Methods
 def analyze_query_complexity(query: str) -> (ComplexityLevel, metadata)
 def check_resource_constraints() -> resource_status
 def decide_agent_strategy(query: str) -> strategy_dict
 def should_escalate(strategy, confidence, attempt) -> (bool, new_strategy)
```

**Return Format of `decide_agent_strategy`:**
```python
{
 "complexity": "low" | "mid" | "high",
 "complexity_metadata": {
 "query_length": int,
 "factors": ["length: simple", "multi_part: yes", ...],
 "llm_classification": "LOW" | "MID" | "HIGH"
 },
 "resource_status": {
 "constrained": bool,
 "cpu_percent": float,
 "memory_percent": float,
 "recommendation": str
 },
 "agent_type": "SearchAgent" | "MultiHopReasoningAgent",
 "use_multihop": bool,
 "use_tools": bool,
 "max_hops": int,
 "confidence_threshold": float,
 "reasoning": [list of decision reasons],
 "degraded": bool # optional, only if downgraded
}
```

#### 2. **AdaptiveQueryProcessor** (`core/adaptive_integration.py`)
Integration layer between `AdaptiveHopManager` and agents.

```python
class AdaptiveQueryProcessor:
 def __init__(self, agent, multihop_agent, adaptive_manager)
 # Core Methods
 def process_query(query, force_complexity, enable_escalation) -> response
 def _execute_strategy(query, strategy) -> result
 def _estimate_confidence(answer) -> confidence_score
```

**Return Format of `process_query`:**
```python
{
 "answer": str,
 "confidence": float | None,
 "strategy": {
 "complexity": str,
 "agent_type": str,
 "use_multihop": bool,
 "use_tools": bool,
 "max_hops": int,
 "reasoning": [list of reasons]
 },
 "metadata": {
 "complexity_analysis": {...},
 "resource_status": {...},
 "attempts": int,
 "escalation_history": [
 {
 "attempt": int,
 "from_agent": str,
 "to_agent": str,
 "reason": str,
 "confidence": float
 }
 ],
 "elapsed_time": float
 },
 # Optional fields from MultiHopAgent
 "steps": int | None,
 "search_queries": [list] | None,
 "reasoning_path": [list] | None
}
```

#### 3. **ComplexityLevel** (Enum)
```python
class ComplexityLevel(Enum):
 LOW = "low"
 MID = "mid"
 HIGH = "high"
```

#### 4. **AdaptiveConfig** (Dataclass)
Configuration parameters for the adaptive system:
```python
@dataclass
class AdaptiveConfig:
 # Feature Toggles
 enable_resource_monitoring: bool = True
 enable_confidence_escalation: bool = True
 # Resource Thresholds
 cpu_threshold_high: float = 80.0
 memory_threshold_high: float = 85.0
 # Confidence Thresholds
 confidence_low: float = 0.5
 confidence_medium: float = 0.7
 confidence_high: float = 0.85
 # Max Hops per Complexity
 max_hops_low: int = 0
 max_hops_mid: int = 1
 max_hops_high: int = 5
 # Fallback
 fallback_on_resource_constraint: bool = True
 degraded_mode_max_hops: int = 2
```

---

## Integration into `app.py`
### Step 1: Add Imports
```python
# In app.py after existing imports:
from core.adaptive_integration import initialize_adaptive_system
```

### Step 2: Initialization
```python
# After initializing agent and multihop_agent (~line 295)
# Initialize adaptive system
adaptive_manager = None
adaptive_processor = None
try:
 adaptive_manager, adaptive_processor = initialize_adaptive_system(
 llm=agent.llm, # Reuse LLM from SearchAgent
 agent=agent,
 multihop_agent=multihop_agent,
 system_monitor=system_monitor,
 performance_tracker=performance_tracker
 )
 logger.info("Adaptive system initialized successfully")
except Exception as e:
 logger.error(f"Failed to initialize adaptive system: {e}", exc_info=True)
 # Continue without adaptive system
```

### Step 3: Extend Pydantic Models
```python
# After existing QueryRequest (~line 520)
class AdaptiveQueryRequest(BaseModel):
 """Request model for adaptive query endpoint."""
 query: str = Field(
 ...,
 min_length=1,
 max_length=MAX_QUERY_LENGTH,
 description="User query"
 )
 force_complexity: Optional[str] = Field(
 None,
 description="Force specific complexity: 'low', 'mid', or 'high'"
 )
 enable_escalation: bool = Field(
 True,
 description="Enable confidence-based escalation"
 )

 @validator('query')
 def sanitize_query_input(cls, v):
 return sanitize_query(v)

class AdaptiveQueryResponse(BaseModel):
 """Response model for adaptive query endpoint."""
 answer: str
 confidence: Optional[float]
 strategy: Dict[str, Any]
 metadata: Dict[str, Any]
 steps: Optional[int] = None
 search_queries: Optional[List[str]] = None
 reasoning_path: Optional[List[str]] = None
```

### Step 4: Add Endpoint
```python
# New endpoint after /query (~line 768)
@app.post(
 "/query-adaptive",
 response_model=AdaptiveQueryResponse,
 dependencies=[Depends(check_rate_limit)]
)
async def query_adaptive_endpoint(request: AdaptiveQueryRequest):
 """
 Adaptive query endpoint with automatic agent selection.
 This endpoint automatically selects the optimal agent based on:
 - Query complexity analysis
 - System resource constraints
 - Confidence-based escalation
 """
 if not adaptive_processor:
 raise HTTPException(
 status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
 detail="Adaptive system not available"
 )
 try:
 result = adaptive_processor.process_query(
 query=request.query,
 force_complexity=request.force_complexity,
 enable_escalation=request.enable_escalation
 )
 return AdaptiveQueryResponse(**result)
 except Exception as e:
 logger.error(f"Adaptive query processing failed: {e}", exc_info=True)
 raise HTTPException(
 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail="Adaptive query processing failed"
 )
```

### Step 5: Extend Stats Endpoint (Optional)
```python
# In existing /stats endpoint (~line 770)
@app.get("/stats", response_model=StatsResponse, dependencies=[Depends(check_rate_limit)])
async def stats_endpoint():
 """Get system statistics."""
 try:
 agent_stats = agent.get_stats() if agent else {}
 # ... existing code ...
 # Add adaptive system stats
 if adaptive_manager:
 adaptive_stats = adaptive_manager.get_stats()
 # Merge adaptive_stats into response
 # ... rest of code ...
```

---

## Usage Examples
### Example 1: Simple Query (LOW Complexity)
**Request:**
```bash
curl -X POST "http://localhost:8000/query-adaptive" \
 -H "X-API-Key: your-api-key" \
 -H "Content-Type: application/json" \
 -d '{
 "query": "What is Python?",
 "enable_escalation": true
 }'
```

**Response:**
```json
{
 "answer": "Python is a high-level programming language...",
 "confidence": 0.85,
 "strategy": {
 "complexity": "low",
 "agent_type": "SearchAgent",
 "use_multihop": false,
 "use_tools": false,
 "max_hops": 0,
 "reasoning": ["Low complexity: SearchAgent without tools"]
 },
 "metadata": {
 "complexity_analysis": {
 "query_length": 15,
 "factors": ["length: simple"],
 "llm_classification": "LOW"
 },
 "resource_status": {
 "constrained": false,
 "cpu_percent": 25.3,
 "memory_percent": 45.2
 },
 "attempts": 1,
 "escalation_history": [],
 "elapsed_time": 1.2
 }
}
```

### Example 2: Medium Query (MID Complexity)
**Request:**
```bash
curl -X POST "http://localhost:8000/query-adaptive" \
 -H "X-API-Key: your-api-key" \
 -H "Content-Type: application/json" \
 -d '{
 "query": "Latest developments in quantum computing 2025",
 "enable_escalation": true
 }'
```

**Response:**
```json
{
 "answer": "Recent quantum computing developments include...",
 "confidence": 0.75,
 "strategy": {
 "complexity": "mid",
 "agent_type": "SearchAgent",
 "use_multihop": false,
 "use_tools": true,
 "max_hops": 1,
 "reasoning": ["Mid complexity: SearchAgent with web tools"]
 },
 "metadata": {
 "complexity_analysis": {
 "query_length": 48,
 "factors": ["length: medium", "multi_part: no"],
 "llm_classification": "MID"
 },
 "attempts": 1,
 "elapsed_time": 2.8
 }
}
```

### Example 3: Complex Query with Escalation (HIGH Complexity)
**Request:**
```bash
curl -X POST "http://localhost:8000/query-adaptive" \
 -H "X-API-Key: your-api-key" \
 -H "Content-Type: application/json" \
 -d '{
 "query": "Compare the economic impact of AI in healthcare vs manufacturing, then analyze which sector shows more growth potential over the next 5 years",
 "enable_escalation": true
 }'
```

**Response:**
```json
{
 "answer": "Comparing AI impact across sectors:\n\n1. Healthcare...\n2. Manufacturing...\n\nAnalysis: Healthcare shows 23% higher growth potential...",
 "confidence": 0.88,
 "strategy": {
 "complexity": "high",
 "agent_type": "MultiHopReasoningAgent",
 "use_multihop": true,
 "use_tools": true,
 "max_hops": 5,
 "reasoning": ["High complexity: MultiHop with 5 hops"]
 },
 "metadata": {
 "complexity_analysis": {
 "query_length": 142,
 "factors": ["length: complex", "multi_part: yes", "temporal: yes"],
 "llm_classification": "HIGH"
 },
 "attempts": 1,
 "elapsed_time": 15.3
 },
 "steps": 4,
 "search_queries": [
 "AI impact healthcare economic 2025",
 "AI manufacturing economic impact",
 "healthcare AI growth forecast 5 years",
 "manufacturing AI adoption trends"
 ],
 "reasoning_path": [
 "Router: Query classified as COMPLEX",
 "Initial search: AI healthcare economics",
 "Follow-up 1: Compare with manufacturing",
 "Follow-up 2: Growth analysis next 5 years",
 "Synthesis: Combined analysis complete"
 ]
}
```

### Example 4: Force Complexity Override
**Request:**
```bash
curl -X POST "http://localhost:8000/query-adaptive" \
 -H "X-API-Key: your-api-key" \
 -H "Content-Type: application/json" \
 -d '{
 "query": "What is the weather?",
 "force_complexity": "high",
 "enable_escalation": false
 }'
```
Forces even a simple question through `MultiHopReasoningAgent`.

### Example 5: Escalation Scenario
If a LOW-complexity query returns low confidence:

**Initial Response (attempt 1):**
```json
{
 "strategy": {"complexity": "low", "agent_type": "SearchAgent"},
 "confidence": 0.4,
 "metadata": {
 "attempts": 2,
 "escalation_history": [
 {
 "attempt": 1,
 "from_agent": "SearchAgent",
 "to_agent": "SearchAgent",
 "reason": "Low confidence (0.40)",
 "confidence": 0.4
 }
 ]
 }
}
```
System automatically escalates to MID, then possibly HIGH.

---

## Configuration
### Default Configuration
Defined in `AdaptiveConfig`:
```python
config = AdaptiveConfig(
 enable_resource_monitoring=True,
 enable_confidence_escalation=True,
 cpu_threshold_high=80.0,
 memory_threshold_high=85.0,
 confidence_low=0.5,
 confidence_medium=0.7,
 confidence_high=0.85,
 max_hops_low=0,
 max_hops_mid=1,
 max_hops_high=5,
 fallback_on_resource_constraint=True,
 degraded_mode_max_hops=2
)
```

### Customization
Adjust in `initialize_adaptive_system()`:
```python
from core.adaptive_hops import AdaptiveConfig
custom_config = AdaptiveConfig(
 max_hops_high=3, # Reduce max hops for HIGH
 cpu_threshold_high=70.0, # Stricter CPU limit
 confidence_low=0.6 # Higher escalation threshold
)
adaptive_manager = AdaptiveHopManager(
 llm=llm,
 config=custom_config,
 system_monitor=system_monitor,
 performance_tracker=performance_tracker
)
```

---

## Metrics & Monitoring
### Available Stats
```python
# Adaptive Manager Stats
GET /stats
Response:
{
 "adaptive_manager": {
 "config": {
 "resource_monitoring": true,
 "confidence_escalation": true,
 "max_hops": { "low": 0, "mid": 1, "high": 5 }
 },
 "current_resources": {
 "cpu_percent": 35.2,
 "memory_percent": 62.1
 }
 }
}
```

### Logging
All key decisions are logged:
```
2025-10-28 12:34:56 - INFO - AdaptiveHopManager initialized
2025-10-28 12:35:01 - INFO - Query complexity: high | Factors: ['length: complex', 'multi_part: yes']
2025-10-28 12:35:01 - INFO - Agent strategy: MultiHopReasoningAgent | Reasoning: High complexity: MultiHop with 5 hops
2025-10-28 12:35:15 - INFO - Query processed successfully | Complexity: high | Agent: MultiHopReasoningAgent | Attempts: 1 | Time: 14.23s
```

---

## Testing
### Unit Tests
```python
# tests/unit/test_adaptive_hops.py
import pytest
from core.adaptive_hops import AdaptiveHopManager, ComplexityLevel, AdaptiveConfig

def test_complexity_analysis_low():
 class MockLLM:
 def generate(self, prompt, system_prompt=None):
 return "LOW"
 manager = AdaptiveHopManager(llm=MockLLM())
 complexity, metadata = manager.analyze_query_complexity("What is Python?")
 assert complexity == ComplexityLevel.LOW
 assert "llm_classification" in metadata

def test_complexity_analysis_high():
 class MockLLM:
 def generate(self, prompt, system_prompt=None):
 return "HIGH"
 manager = AdaptiveHopManager(llm=MockLLM())
 query = "Compare X and Y, then analyze trends over time"
 complexity, metadata = manager.analyze_query_complexity(query)
 assert complexity == ComplexityLevel.HIGH
 assert "multi_part: yes" in str(metadata["factors"])
```

### Integration Tests
```python
# tests/integration/test_adaptive_integration.py
def test_process_query_low_complexity(mock_agents):
 agent, multihop_agent, manager = mock_agents
 processor = AdaptiveQueryProcessor(agent=agent, multihop_agent=multihop_agent, adaptive_manager=manager)
 result = processor.process_query("Simple question?")
 assert result["strategy"]["complexity"] == "low"
 assert result["metadata"]["attempts"] == 1
```

---

## Troubleshooting
### Issue: Adaptive System Not Available
**Symptom:** `503 Service Unavailable`
**Fix:**
1. Check logs for initialization errors
2. Ensure LLM is available
3. Verify `adaptive_processor` was initialized

### Issue: All Queries Classified as HIGH
**Fix:**
1. Check LLM prompts in `analyze_query_complexity()`
2. Adjust heuristic thresholds
3. Use `force_complexity="low"` for testing

### Issue: No Escalation Despite Low Confidence
**Fix:**
1. Ensure `enable_escalation=true`
2. Check `enable_confidence_escalation` in config
3. Verify `attempt_count` vs `max_escalation_attempts`

---

## Best Practices
### 1. Query Optimization
```python
# Bad: Too vague
"Tell me about AI"
# Good: Specific
"What are the latest AI developments in healthcare in 2025?"
```

### 2. Use Escalation Wisely
```python
{ "query": "User question", "enable_escalation": true } # Safe
{ "query": "What is 2+2?", "enable_escalation": false } # Fast
```

### 3. Force Complexity for Special Cases
```python
{ "query": "Analyze Q4", "force_complexity": "high" } # Deep
{ "query": "Company address?", "force_complexity": "low" } # Fast
```

---

## Performance Optimizations
### 1. Cache Complexity Analysis
```python
from functools import lru_cache
@lru_cache(maxsize=1000)
def cached_complexity_analysis(query_hash):
 return manager.analyze_query_complexity(query)
```

### 2. Async Processing
```python
async def process_multiple_queries(queries):
 tasks = [asyncio.to_thread(adaptive_processor.process_query, q) for q in queries]
 return await asyncio.gather(*tasks)
```

---

## Roadmap
### Version 1.1 (Planned)
- [] Query caching
- [] ML-based complexity detection
- [] Latency-based agent selection
- [] A/B testing framework

### Version 2.0 (Vision)
- [] Reinforcement learning for agent routing
- [] User-specific adaptation
- [] Distributed agent pooling

---

## Resources
- [CrawlLama Docs](../README.md)
- [SearchAgent](../../core/agent/agent.py)
- [MultiHopAgent](../../core/langgraph_agent.py)

---

## Contributing
1. All features require unit tests (>80% coverage)
2. Document public APIs
3. Follow PEP 8
4. Add logging for decisions

---

## License
Part of CrawlLama — same license as main project.

---

## Authors
**CrawlLama Team**
- Version 1.0.0 – Initial Implementation (2025-10-28)

---

## FAQ
### Q: Can I disable resource monitoring?
**A:** Yes, set `enable_resource_monitoring=False`.

### Q: How to skip LLM complexity analysis?
**A:** Use `force_complexity` or adjust heuristics.

### Q: Does escalation work with `force_complexity`?
**A:** No — complexity is fixed.

---

**Good luck with the Adaptive Agent Hopping System! **

-