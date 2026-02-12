# Hallucination Detection & Quality Control

---

 **Navigation:** [Home](../../README.md) | [Docs](../README.md) | [Quickstart](../getting-started/QUICKSTART.md) | [LangGraph](LANGGRAPH_GUIDE.md) | [Plugins](PLUGIN_TUTORIAL.md)

---

## Overview

The Hallucination Detection module (`core/hallu_detect.py`) provides comprehensive quality control for LLM-generated content through automatic detection of hallucinations, fact-checking, and context alignment analysis.

---

## Features

### 1. **Multi-Level Hallucination Detection**
- **Pattern-based detection**: Identifies typical hallucination patterns such as fabricated citations and contradictory statements
- **Context alignment**: Checks if the answer matches the given context
- **Fact-checking**: External validation against Wikipedia and optional web search
- **Quality scoring**: Rating of answer quality based on various metrics

### 2. **Configurable Sensitivity**
- **Detection Level**: `low`, `medium`, `high` for different use cases
- **Adjustable thresholds**: Fine-tuning for specific requirements
- **Selective features**: Enable/disable individual checks

### 3. **Integration in LLM Client**
- **Automatic checking**: Each LLM response is optionally checked
- **Warning modes**: `silent`, `log`, `flag_response`, `block`
- **Performance-optimized**: Configurable timeouts and caching

---

## Configuration

### Config.json Settings

```json
{
 "hallucination_detection": {
 "enabled": false,
 "detection_level": "medium",
 "hallucination_threshold": 0.7,
 "context_alignment_threshold": 0.4,
 "fact_confidence_threshold": 0.6,
 "fact_checking_enabled": true,
 "context_analysis_enabled": true,
 "max_processing_time": 10.0,
 "cache_enabled": true,
 "batch_size": 5,
 "warning_mode": "flag_response",
 "fact_checker": {
 "wikipedia_check": true,
 "web_search_check": false,
 "min_claim_length": 10
 },
 "context_analyzer": {
 "min_context_overlap": 0.3,
 "contradiction_threshold": 0.7
 }
 }
}
```

### Parameter Explanation | Parameter | Description | Values | Default |
|-----------|-------------|-------|----------|
| `enabled` | Enables/disables detection | `true`/`false` | `false` |
| `detection_level` | Sensitivity level | `low`/`medium`/`high` | `medium` |
| `hallucination_threshold` | Threshold for hallucination (0-1) | `0.0-1.0` | `0.7` |
| `context_alignment_threshold` | Min. context alignment | `0.0-1.0` | `0.4` |
| `fact_confidence_threshold` | Min. fact confidence | `0.0-1.0` | `0.6` |
| `warning_mode` | How warnings are displayed | see below | `flag_response` |
| `max_processing_time` | Max. processing time (seconds) | Number | `10.0` |

### Warning Modes

- **`silent`**: No user warnings, logging only
- **`log`**: Warnings in logs, no response modification
- **`flag_response`**: Warning is appended to response
- **`block`**: Response is blocked at high risk

---

## Usage

### 1. **Direct API Usage**

```python
from core.hallu_detect import detect_hallucination

# Simple check
result = detect_hallucination(
 response="Paris is the capital of Germany.",
 context="What is the capital of France?"
)

print(f"Hallucination: {result.is_hallucination}")
print(f"Confidence: {result.confidence_score:.2f}")
print(f"Risk Level: {result.risk_level}")
```

### 2. **LLM Client Integration**

```python
from core.llm_client import OllamaClient

# Enable hallucination detection
hallu_config = {
 "enabled": True,
 "detection_level": "medium",
 "warning_mode": "flag_response"
}

client = OllamaClient(hallu_config=hallu_config)

# Normal generation with automatic checking
response = client.generate("Tell me about quantum computing")
# Response automatically contains quality warning if issues are found
```

### 3. **Advanced Configuration**

```python
from core.hallu_detect import create_detector

# Create custom detector
config = {
 "enabled": True,
 "detection_level": "high",
 "hallucination_threshold": 0.5, # More sensitive
 "fact_checking_enabled": True,
 "context_analysis_enabled": True,
 "fact_checker": {
 "wikipedia_check": True,
 "web_search_check": True # Enable web search
 }
}

detector = create_detector(config)
result = detector.detect(response, context)

# Detailed analysis
for violation in result.violations:
 print(f"Violation: {violation['type']} ({violation['severity']})")

for fact_check in result.fact_check_results:
 print(f"Fact: {fact_check['claim']} - Verified: {fact_check['verified']}")
```

---

## Detection Mechanisms

### 1. **Pattern-based Detection**

**Fabricated Citations/References:**
```
 "According to a 2023 study by..."
 "Research shows that..."
 "[Citation needed]"
```

**Internal Contradictions:**
```
 "X is always true" + "X is never true"
 "This can be done" + "This cannot be done"
```

**Unsupported Specific Information:**
```
 Exact numbers/times without context support
 Specific prices, percentages, dates
```

### 2. **Context Alignment**

- **Coverage**: How many context concepts are addressed?
- **Relevance**: Does the answer stay on topic?
- **Contradictions**: Does the answer contradict the context?

### 3. **Fact-checking**

**Wikipedia Integration:**
- Automatic search for key terms
- Similarity matching against Wikipedia content
- Confidence rating based on agreement

**Future Extensions:**
- Google Fact Check API
- Snopes Integration
- Custom Knowledge Bases

---

## Quality Metrics

### Result Object

```python
@dataclass
class HallucinationResult:
 is_hallucination: bool # Main result
 confidence_score: float # 0.0-1.0
 risk_level: str # "low"/"medium"/"high"
 violations: List[Dict] # Found issues
 context_alignment: float # Context alignment
 fact_check_results: List[Dict] # Fact-checking results
 quality_metrics: Dict # Additional metrics
 processing_time: float # Processing time
```

### Quality Metrics

- **`response_length`**: Response length
- **`repetition_score`**: Repetition rate (0-1)
- **`vague_language_score`**: Proportion of vague language
- **`sentence_count`**: Number of sentences
- **`context_alignment`**: Context alignment

---

## Performance & Limits

### **Speed Optimization**

- **Caching**: Wikipedia queries are cached
- **Timeouts**: Configurable max processing time
- **Batch Processing**: Efficient processing of multiple claims
- **Lazy Loading**: Components are loaded only when needed

### **Rate Limiting**

- **Wikipedia**: ~10 queries/second (respects API limits)
- **Web Search**: Configurable per provider
- **Local Checks**: No limits

### **Memory Usage**

- **Cache**: ~50MB for Wikipedia cache (configurable)
- **Models**: No additional ML models required
- **Memory**: <100MB additional RAM usage

---

## Testing & Validation

### Unit Tests

```bash
# Hallucination Detection Tests
python tests/test_hallucination_detection.py

# Integration in Test Suite
pytest tests/test_hallucination_detection.py -v

# Performance Tests
python -m pytest tests/ -k hallucination --benchmark
```

### Test Cases

The module is validated with various test scenarios:

1. **Normal Responses**: Correct answers without issues
2. **Fabricated Citations**: Made-up sources and studies
3. **Context Misalignment**: Answers without context reference
4. **Internal Contradictions**: Contradictory statements
5. **Unsupported Specifics**: Unverifiable specific claims

### Monitoring

```python
# Get statistics
detector = get_detector()
stats = detector.get_statistics()

print(f"Total checks: {stats['total_checks']}")
print(f"Hallucinations detected: {stats['hallucinations_detected']}")
print(f"Detection rate: {stats['hallucinations_detected']/stats['total_checks']*100:.1f}%")
print(f"Avg processing time: {stats['avg_processing_time']:.3f}s")
```

---

## Troubleshooting

### Common Issues

1. **Too Many False Positives**
 - Solution: Set `detection_level` to `low`
 - Increase thresholds: `hallucination_threshold: 0.8+`

2. **Too Slow Performance**
 - `fact_checking_enabled: false` for local tests
 - Reduce `max_processing_time`
 - `wikipedia_check: false` for network issues

3. **Wikipedia API Errors**
 - Rate Limiting: Automatic delays
 - Fallback: Local pattern detection continues to work

4. **Memory Issues**
 - `cache_enabled: false` disables caching
 - Reduce `batch_size` for less RAM usage

### Debug Mode

```python
import logging
logging.getLogger("crawllama").setLevel(logging.DEBUG)

# Detailed logs for hallucination detection
result = detector.detect(response, context)
```

---

## Roadmap & Extensions

### Planned Features (v1.5+)

- **ML-based Detection**: Training custom hallucination classifiers
- **Multi-Language Support**: Support for other languages
- **Custom Knowledge Bases**: Integration of custom fact-check sources
- **Real-time Monitoring**: Live dashboard for quality metrics
- **A/B Testing**: Comparison of different detection strategies

### API Extensions

- **Batch Processing**: Efficient processing of many responses
- **Webhook Integration**: Automatic notifications
- **Export Functions**: Reports as PDF/Excel
- **Fine-tuning Interface**: GUI for threshold adjustments

---

## Best Practices

### Production Environment

1. **Gradual Rollout**: Start with `detection_level: "low"`
2. **Monitoring**: Monitor detection rate and performance
3. **Feedback Loop**: Collect user feedback for false positives
4. **Adjust Thresholds**: Optimize thresholds based on use case

### Development

1. **Testing**: Use diverse test cases
2. **Logging**: Enable debug logs during development
3. **Caching**: Use local cache for faster tests
4. **Profiling**: Measure performance impact

### Compliance

1. **Privacy**: Wikipedia queries contain no user data
2. **Rate Limits**: Respect API limits of all services
3. **Logging**: All checks are logged for audit
4. **Configurable**: Features can be completely disabled

---

The Hallucination Detection module provides a robust, configurable solution for LLM quality control with minimal performance impact and maximum flexibility! 
