# Adaptive Hops – Quick Start Guide
## What is Adaptive Hops?
An **intelligent routing system** that **automatically selects the optimal agent** for every query:
- **LOW Complexity** → `SearchAgent` (no tools, fast)
- **MID Complexity** → `SearchAgent` with web tools
- **HIGH Complexity** → `MultiHopReasoningAgent` (1–5 hops)

## Installation
All files are already in the project:
```
core/
 ├── adaptive_hops.py # Core logic
 └── adaptive_integration.py # Integration layer
examples/
 ├── adaptive_demo.py # Demo script
 └── app_integration_example.py # Integration example
ADAPTIVE_HOPS.md # Full documentation
```

## Quick Start (3 Steps)

### 1. Add Import
In `app.py` after line 23:
```python
from core.adaptive_integration import initialize_adaptive_system
```

### 2. Initialize System
In `app.py` after line 295 (after `multihop_agent` init):
```python
# Initialize adaptive system
adaptive_manager = None
adaptive_processor = None
try:
 adaptive_manager, adaptive_processor = initialize_adaptive_system(
 llm=agent.llm,
 agent=agent,
 multihop_agent=multihop_agent,
 system_monitor=system_monitor,
 performance_tracker=performance_tracker
 )
 logger.info("Adaptive system initialized")
except Exception as e:
 logger.error(f"Failed to initialize adaptive system: {e}")
```

### 3. Add Endpoint
In `app.py` after line 768 (after `/query` endpoint):
```python
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator

class AdaptiveQueryRequest(BaseModel):
 query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
 force_complexity: Optional[str] = None
 enable_escalation: bool = True

 @validator('query')
 def sanitize_query_input(cls, v):
 return sanitize_query(v)

class AdaptiveQueryResponse(BaseModel):
 answer: str
 confidence: Optional[float]
 strategy: Dict[str, Any]
 metadata: Dict[str, Any]
 steps: Optional[int] = None
 search_queries: Optional[List[str]] = None
 reasoning_path: Optional[List[str]] = None

@app.post("/query-adaptive", response_model=AdaptiveQueryResponse, dependencies=[Depends(check_rate_limit)])
async def query_adaptive_endpoint(request: AdaptiveQueryRequest):
 if not adaptive_processor:
 raise HTTPException(status_code=503, detail="Adaptive system not available")
 result = adaptive_processor.process_query(
 query=request.query,
 force_complexity=request.force_complexity,
 enable_escalation=request.enable_escalation
 )
 return AdaptiveQueryResponse(**result)
```

---

## Test It

### Option A: Run Demo Script
```bash
python examples/adaptive_demo.py
```
Shows all features: complexity analysis, strategy decisions, escalation, etc.

### Option B: Test API Endpoint
1. Start server:
```bash
python app.py
```
2. Send request:
```bash
curl -X POST "http://localhost:8000/query-adaptive" \
 -H "X-API-Key: your-api-key" \
 -H "Content-Type: application/json" \
 -d '{
 "query": "Compare AI in healthcare vs manufacturing",
 "enable_escalation": true
 }'
```
3. Check response:
```json
{
 "answer": "...",
 "confidence": 0.85,
 "strategy": {
 "complexity": "high",
 "agent_type": "MultiHopReasoningAgent",
 "max_hops": 5,
 "reasoning": ["High complexity: MultiHop with 5 hops"]
 },
 "metadata": {
 "attempts": 1,
 "elapsed_time": 12.5,
 "escalation_history": []
 }
}
```

---

## Usage Examples

### Simple Query (LOW)
```bash
curl ... -d '{"query": "What is Python?"}'
# → SearchAgent, no tools, ~0.8s
```

### Web Search Query (MID)
```bash
curl ... -d '{"query": "Latest AI news 2025"}'
# → SearchAgent + web tools, ~2.5s
```

### Complex Query (HIGH)
```bash
curl ... -d '{"query": "Compare X and Y, analyze trends, recommend best option"}'
# → MultiHopReasoningAgent, 5 hops, ~15s
```

### Force Complexity
```bash
curl ... -d '{"query": "Simple question", "force_complexity": "high"}'
# → Forces MultiHopAgent even for simple queries
```

---

## How It Works
```
Query → Complexity Analysis → Strategy Decision → Agent Execution
 │ │
 ├─ LLM Classification ├─ Resource Check
 ├─ Length Heuristic ├─ Agent Selection
 └─ Keyword Detection └─ Configuration
 ↓ (if confidence < 0.5)
 Escalation Loop
 LOW → MID → HIGH
```

---

## Features
- **Automatic Complexity Detection**
 - LLM-based + heuristics
 - 3 levels: LOW, MID, HIGH
- **Confidence-Based Escalation**
 - Auto-upgrade on low confidence
 - Max 2 escalation attempts
- **Resource-Based Degradation**
 - Downgrades complexity under high CPU/memory
 - Reduced hops in degraded mode
- **Flexible Configuration**
 - All thresholds customizable
 - Feature toggles for monitoring/escalation
- **Detailed Metrics**
 - Complexity breakdown
 - Strategy reasoning
 - Escalation history
 - Resource status

---

## Customize Configuration
```python
from core.adaptive_hops import AdaptiveConfig

custom_config = AdaptiveConfig(
 max_hops_high=3, # Reduce high-complexity hops
 cpu_threshold_high=70.0, # Stricter CPU limit
 confidence_low=0.6, # Higher escalation threshold
 enable_resource_monitoring=False # Disable monitoring
)
# Pass custom_config during initialization
```

---

## Next Steps
1. **Read Full Docs**: `ADAPTIVE_HOPS.md`
 - Architecture
 - API reference
 - Best practices
 - Troubleshooting
2. **Run Demo**: `python examples/adaptive_demo.py`
3. **Integrate into API**: See `examples/app_integration_example.py`
4. **Monitor in Production**: Use logs + `/stats` endpoint

---

## Benefits | Feature | Before | With Adaptive Hops |
|--------|--------|--------------------|
| Agent Selection | Manual (`use_multihop=true/false`) | **Automatic** based on complexity |
| Performance | Fixed strategy | **Optimized per query** |
| Resources | No adaptation | **Dynamic degradation** |
| Confidence | Not monitored | **Auto-escalation** |
| Transparency | Black box | **Full strategy + metadata** |

---

## Support
- **Full Docs**: `ADAPTIVE_HOPS.md`
- **Integration Code**: `examples/app_integration_example.py`
- **Demo**: `examples/adaptive_demo.py`
- **Issues**: GitHub Issues

---

**Happy Adaptive Hopping!**