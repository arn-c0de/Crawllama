# Cloud LLM Integration Guide

CrawLlama now supports cloud-based LLM providers in addition to local Ollama models.

## Supported Providers | Provider | Models | Speed | Cost | API Key Required |
|----------|--------|-------|------|------------------|
| **Ollama** (default) | Qwen, Llama, Mistral, etc. | Fast (local) | Free | No |
| **OpenAI** | GPT-3.5, GPT-4, GPT-4-Turbo | Fast | Paid | Yes |
| **Anthropic** | Claude 3 (Opus, Sonnet, Haiku) | Fast | Paid | Yes |
| **Groq** | Mixtral, LLaMA 2, Gemma | Very Fast | Free tier available | Yes |

---

## Quick Start

### 1. Install Cloud Provider Libraries

Uncomment the desired providers in `requirements.txt`:

```bash
# For OpenAI
pip install openai>=1.54.0

# For Anthropic
pip install anthropic>=0.40.0

# For Groq
pip install groq>=0.15.0

# Or install all at once
pip install openai anthropic groq
```

### 2. Add API Keys to `.env`

Copy `.env.example` to `.env` and add your API keys:

```bash
# OpenAI
OPENAI_API_KEY=sk-proj-your_key_here

# Anthropic
ANTHROPIC_API_KEY=sk-ant-your_key_here

# Groq
GROQ_API_KEY=gsk_your_key_here
```

### 3. Configure Provider in `config.json`

Edit the `llm` section in `config.json`:

```json
{
 "llm": {
 "provider": "openai",
 "model": "gpt-4-turbo",
 "temperature": 0.7,
 "max_tokens": 4096
 }
}
```

---

## Configuration Examples

### OpenAI GPT Models

```json
{
 "llm": {
 "provider": "openai",
 "model": "gpt-4-turbo",
 "temperature": 0.7,
 "max_tokens": 4096
 }
}
```

**Available Models:**
- `gpt-3.5-turbo` - Fast, cost-effective
- `gpt-4` - Most capable (slower, expensive)
- `gpt-4-turbo` - Fast GPT-4 variant
- `gpt-4-turbo-preview` - Latest preview

**Pricing:** See [OpenAI Pricing](https://openai.com/pricing)

---

### Anthropic Claude

```json
{
 "llm": {
 "provider": "anthropic",
 "model": "claude-3-sonnet-20240229",
 "temperature": 0.7,
 "max_tokens": 4096
 }
}
```

**Available Models:**
- `claude-3-opus-20240229` - Most capable (expensive)
- `claude-3-sonnet-20240229` - Balanced (recommended)
- `claude-3-haiku-20240307` - Fast, cost-effective

**Pricing:** See [Anthropic Pricing](https://www.anthropic.com/pricing)

---

### Groq (Fast Inference)

```json
{
 "llm": {
 "provider": "groq",
 "model": "mixtral-8x7b-32768",
 "temperature": 0.7,
 "max_tokens": 4096
 }
}
```

**Available Models:**
- `mixtral-8x7b-32768` - Mixtral 8x7B (32K context)
- `llama2-70b-4096` - LLaMA 2 70B (4K context)
- `gemma-7b-it` - Google Gemma 7B

**Pricing:** Free tier available! See [Groq Console](https://console.groq.com/)

---

### Local Ollama (Default)

```json
{
 "llm": {
 "provider": "ollama",
 "base_url": "http://127.0.0.1:11434",
 "model": "qwen2.5:3b",
 "temperature": 0.7,
 "max_tokens": 4096
 }
}
```

**No API key required** - runs 100% locally.

---

## Programmatic Usage

### Using the Factory Function

```python
from core.cloud_llm_client import get_llm_client

# Get OpenAI client
client = get_llm_client("openai", model="gpt-4")
response = client.generate("What is the capital of France?")
print(response)

# Get Anthropic client
client = get_llm_client("anthropic", model="claude-3-sonnet-20240229")
response = client.chat([
 {"role": "user", "content": "Hello, Claude!"}
])
print(response)

# Get Groq client
client = get_llm_client("groq", model="mixtral-8x7b-32768")
response = client.generate("Explain quantum computing")
print(response)
```

### Direct Client Initialization

```python
from core.cloud_llm_client import OpenAIClient, AnthropicClient, GroqClient

# OpenAI
openai_client = OpenAIClient(
 api_key="sk-proj-...", # Or from .env
 model="gpt-4",
 temperature=0.7
)

# Anthropic
anthropic_client = AnthropicClient(
 api_key="sk-ant-...",
 model="claude-3-opus-20240229",
 temperature=0.7
)

# Groq
groq_client = GroqClient(
 api_key="gsk_...",
 model="mixtral-8x7b-32768",
 temperature=0.7
)
```

---

## Advanced Configuration

### Temperature Settings

Controls randomness in responses:

```json
{
 "llm": {
 "temperature": 0.0 // Deterministic (0.0) to Creative (2.0)
 }
}
```

- **0.0-0.3**: Factual, deterministic (good for OSINT, research)
- **0.4-0.7**: Balanced (recommended)
- **0.8-1.0**: Creative (good for brainstorming)

### Token Limits

```json
{
 "llm": {
 "max_tokens": 4096 // Maximum response length
 }
}
```

**Note:** Different models have different context windows:
- GPT-3.5: 4K tokens
- GPT-4: 8K-32K tokens
- Claude 3: 200K tokens
- Mixtral: 32K tokens

---

## Testing

Run tests for cloud LLM clients:

```bash
# Run all cloud LLM tests
python -m pytest tests/unit/test_cloud_llm_client.py -v

# Run specific provider tests
python -m pytest tests/unit/test_cloud_llm_client.py::TestOpenAIClient -v
python -m pytest tests/unit/test_cloud_llm_client.py::TestAnthropicClient -v
python -m pytest tests/unit/test_cloud_llm_client.py::TestGroqClient -v
```

---

## Security Best Practices

1. **Never commit `.env` to Git**
 ```bash
 # .gitignore already includes .env
 echo ".env" >> .gitignore
 ```

2. **Use environment variables in production**
 ```bash
 export OPENAI_API_KEY="sk-proj-..."
 export ANTHROPIC_API_KEY="sk-ant-..."
 export GROQ_API_KEY="gsk_..."
 ```

3. **Rotate API keys regularly**
 - OpenAI: https://platform.openai.com/api-keys
 - Anthropic: https://console.anthropic.com/settings/keys
 - Groq: https://console.groq.com/keys

4. **Monitor API usage and costs**
 - Set spending limits in provider dashboards
 - Enable usage alerts

---

## Performance Comparison | Provider | Avg Response Time | Cost (1M tokens) | Context Window |
|----------|-------------------|------------------|----------------|
| **Ollama** | 1-5s (local) | Free | 4K-128K (model dependent) |
| **OpenAI GPT-4** | 2-10s | $30 (input) / $60 (output) | 8K-128K |
| **Anthropic Claude 3** | 2-8s | $15 (Sonnet) | 200K |
| **Groq Mixtral** | 0.5-2s | Free tier | 32K |

**Recommendation:**
- **Development/Testing**: Ollama (free, fast)
- **Production (speed)**: Groq (free tier, very fast)
- **Production (quality)**: Claude 3 Sonnet (balanced)
- **Production (complex tasks)**: GPT-4 or Claude 3 Opus

---

## Troubleshooting

### "API key not found" error

```bash
# Check if .env file exists and contains the key
cat .env | grep API_KEY

# Ensure .env is loaded
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('OPENAI_API_KEY'))"
```

### "Module not found" error

```bash
# Install missing provider library
pip install openai anthropic groq
```

### "Invalid API key" error

1. Verify key format:
 - OpenAI: `sk-proj-...`
 - Anthropic: `sk-ant-...`
 - Groq: `gsk_...`

2. Check key validity in provider dashboard

3. Ensure no extra spaces/quotes in `.env`:
 ```bash
 # BAD
 OPENAI_API_KEY="sk-proj-..."

 # GOOD
 OPENAI_API_KEY=sk-proj-...
 ```

### "Rate limit exceeded" error

1. **OpenAI**: Upgrade to paid tier or wait
2. **Anthropic**: Check usage limits in console
3. **Groq**: Free tier has limits, consider paid tier

---

## Additional Resources

- **OpenAI Documentation**: https://platform.openai.com/docs
- **Anthropic Documentation**: https://docs.anthropic.com/
- **Groq Documentation**: https://console.groq.com/docs
- **CrawLlama Main Docs**: [../README.md](../README.md)

---

## Contributing

Found a bug or want to add support for more providers? See [CONTRIBUTING.md](../CONTRIBUTING.md)

**Potential future providers:**
- Google Gemini API
- Cohere
- Azure OpenAI
- AWS Bedrock
