# LangGraph Multi-Hop Reasoning Guide

---

 **Navigation:** [Home](../../README.md) | [Docs](../README.md) | [Quickstart](../getting-started/QUICKSTART.md) | [Plugins](PLUGIN_TUTORIAL.md) | [OSINT](../osint/OSINT_USAGE.md)

---

## Overview

CrawlLama uses LangGraph for complex, multi-stage reasoning processes. This guide explains how the multi-hop reasoning system works and how to use it.

## Architecture

### Reasoning Graph

The multi-hop agent uses a StateGraph with the following nodes:

```
┌─────────┐
│ Router │──┐
└─────────┘ │
 ▼
 ┌──────────────┐
 │Initial Search│
 └──────────────┘
 │
 ▼
 ┌─────────┐
 │ Analyze │◄──┐
 └─────────┘ │
 │ │
 ┌────┴────┐ │
 │ │ │
 Needs Ready │
 more? │ │
 │ │ │
 ▼ ▼ │
 ┌────────┐ ┌──────────┐
 │Follow-Up│ │Synthesize│
 └────────┘ └──────────┘
 │ │
 └──────────────┘
 │
 ▼
 ┌─────────┐
 │Critique │
 └─────────┘
 │
 ┌───┴───┐
 │ │
 Good Improve
 │ │
 ▼ │
 END └──► (back to Follow-Up)
```

## Node Descriptions

### 1. Router Node
**Purpose:** Classifies query complexity

**Logic:**
- Analyzes the input query
- Classifies as SIMPLE or COMPLEX
- SIMPLE → direct answer possible
- COMPLEX → requires multiple steps

**Examples:**
- SIMPLE: "What is Python?"
- COMPLEX: "Compare Python and JavaScript for web development"

### 2. Initial Search Node
**Purpose:** First information search

**Process:**
1. Performs web search with original query
2. Collects initial information
3. Stores results in context

### 3. Analyze Node
**Purpose:** Evaluation of collected information

**Checks:**
1. Is information complete?
2. What information is missing?
3. Confidence score (0-100%)

**Decision:**
```python
if complete and confidence >= threshold:
 → Synthesize
else if steps < max_hops:
 → Follow-Up
else:
 → Synthesize (with available info)
```

### 4. Follow-Up Node
**Purpose:** Targeted follow-up searches

**Process:**
1. LLM generates specific follow-up query
2. Performs additional search
3. Enriches context
4. Back to Analyze

**Example:**
- Original: "Compare Python and JavaScript"
- Follow-Up 1: "Python performance benchmarks"
- Follow-Up 2: "JavaScript modern features"

### 5. Synthesize Node
**Purpose:** Final answer generation

**Process:**
1. Combines all context information
2. Structures comprehensive answer
3. Cites sources
4. Generates coherent output

### 6. Critique Node (Optional)
**Purpose:** Self-critique of generated answer

**Evaluation:**
- Completeness
- Correctness
- Quality score

**Decision:**
```python
if quality >= threshold:
 → END
else if steps < max_hops:
 → Follow-Up (for improvement)
else:
 → END
```

## Usage

### Basic Usage

```python
from core.langgraph_agent import MultiHopReasoningAgent
import json

# Load config
config = json.load(open("config.json"))

# Initialize agent
agent = MultiHopReasoningAgent(
 config=config,
 max_hops=3, # Max reasoning steps
 confidence_threshold=0.7, # Min confidence to stop
 enable_critique=True # Enable self-critique
)

# Query
result = agent.query("Compare Python and JavaScript for web development")

# Result structure
print(result["answer"]) # Final answer
print(result["confidence"]) # Confidence score
print(result["steps"]) # Number of hops taken
print(result["search_queries"]) # Queries performed
print(result["reasoning_path"]) # Step-by-step reasoning
```

### Via CLI

```bash
# Enable multi-hop reasoning
python main.py --multihop "Complex question here"

# Custom max hops
python main.py --multihop --max-hops 5 "Your question"
```

### Via API

```bash
curl -X POST http://localhost:8000/query \
 -H "Content-Type: application/json" \
 -d '{
 "query": "Compare Python and JavaScript",
 "use_multihop": true,
 "max_hops": 3
 }'
```

## Configuration

### config.json

```json
{
 "llm": {
 "model": "qwen3:4b",
 "temperature": 0.7,
 "max_tokens": 4096
 },
 "multihop": {
 "enabled": true,
 "max_hops": 3,
 "confidence_threshold": 0.7,
 "enable_critique": true
 }
}
```

### Parameter Tuning

**max_hops:**
- Low (1-2): Faster, less thorough
- Medium (3-4): Balanced
- High (5+): Very thorough, slower

**confidence_threshold:**
- Low (0.5-0.6): Stops earlier
- Medium (0.7-0.8): Recommended
- High (0.9+): Very strict, more hops

**enable_critique:**
- `true`: Better quality, slower
- `false`: Faster, no self-checking

## Best Practices

### 1. When to Use Multi-Hop?

 **Suitable for:**
- Comparison questions
- Multi-aspect analyses
- Research-intensive questions
- "Pros and cons" questions

 **Not suitable for:**
- Simple fact questions
- Definitions
- Yes/no questions

### 2. Performance Optimization

```python
# For fast answers
agent = MultiHopReasoningAgent(
 config=config,
 max_hops=2,
 confidence_threshold=0.6,
 enable_critique=False
)

# For maximum quality
agent = MultiHopReasoningAgent(
 config=config,
 max_hops=5,
 confidence_threshold=0.8,
 enable_critique=True
)
```

### 3. Monitoring

```python
result = agent.query("Your question")

# Log reasoning path
for i, step in enumerate(result["reasoning_path"], 1):
 print(f"Step {i}: {step}")

# Check if enough information was gathered
if result["steps"] == max_hops:
 print("Warning: Reached max hops, might need more information")
```

## Examples

### Example 1: Technology Comparison

```python
query = "Compare React and Vue.js for building SPAs"

result = agent.query(query)

# Reasoning path:
# 1. Router: Complex query detected
# 2. Initial search: "React vs Vue.js SPA"
# 3. Analyze: Need more details on performance
# 4. Follow-up: "React performance benchmarks"
# 5. Follow-up: "Vue.js modern features"
# 6. Synthesize: Comprehensive comparison
# 7. Critique: Quality check passed
```

### Example 2: Pros/Cons Analysis

```python
query = "What are the pros and cons of electric vehicles?"

result = agent.query(query)

# Expected hops: 2-3
# - Initial: General EV info
# - Follow-up 1: EV advantages
# - Follow-up 2: EV disadvantages
# - Synthesize: Balanced overview
```

## Troubleshooting

### Problem: Too Many Hops

**Solution:**
- Increase `confidence_threshold`
- Reduce `max_hops`
- Improve initial query formulation

### Problem: Poor Answer Quality

**Solution:**
- Enable `enable_critique`
- Increase `max_hops`
- Lower `confidence_threshold`
- Use larger LLM model

### Problem: Long Response Times

**Solution:**
- Reduce `max_hops`
- Disable `enable_critique`
- Use caching
- Enable parallel searches

## Advanced Features

### Adding Custom Nodes

```python
# In langgraph_agent.py

def _custom_node(self, state: ReasoningState) -> ReasoningState:
 """Custom processing node."""
 # Your logic here
 return state

# Add to graph
workflow.add_node("custom", self._custom_node)
workflow.add_edge("analyze", "custom")
```

### Extending State

```python
class CustomReasoningState(ReasoningState):
 """Extended state with custom fields."""
 custom_data: List[str]
 extra_metadata: Dict[str, Any]
```

## Further Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [CrawlLama API Docs](API_DOCS.md)
- [Performance Tuning Guide](PERFORMANCE.md)
