# Cloud LLM Provider Selection in CLI Settings

## Overview

Starting with v1.4.4, you can switch between local (Ollama) and cloud LLM providers from the interactive CLI settings menu.

## Usage

### 1. Open the settings menu

```bash
python main.py --interactive
```

In interactive mode:

```text
 settings
```

### 2. Select the LLM category

```text
Which category would you like to modify?
> llm
```

### 3. Select a provider

```text
=== LLM Settings ===

Available providers:
 • ollama - Local models (no API key required)
 • openai - GPT-3.5 / GPT-4 (API key required)
 • anthropic - Claude 3 (API key required)
 • groq - Mixtral / LLaMA (API key required, free tier available)

LLM Provider [ollama]: groq
[OK] Provider changed: groq
Warning: Groq requires an API key.
Set GROQ_API_KEY in your .env file.
```

### 4. Select a model

The CLI automatically suggests provider-specific models.

Ollama:

```text
Ollama models: qwen2.5:3b, qwen3:8b, deepseek-r1:8b, llama3:7b
LLM Model [qwen3:8b]: deepseek-r1:8b
```

OpenAI:

```text
OpenAI models: gpt-3.5-turbo, gpt-4, gpt-4-turbo
LLM Model [gpt-3.5-turbo]: gpt-4
```

Anthropic:

```text
Anthropic models: claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307
LLM Model [claude-3-sonnet-20240229]: claude-3-opus-20240229
```

Groq:

```text
Groq models: mixtral-8x7b-32768, llama2-70b-4096, gemma-7b-it
LLM Model [mixtral-8x7b-32768]: llama2-70b-4096
```

### 5. Save settings

```text
Save settings? (y/n) [y]: y
[OK] Configuration saved: config.json

Restart agent to apply changes? (y/n) [y]: y
[cyan]Reloading configuration...[/cyan]
[cyan]Reinitializing agents...[/cyan]
```

## API Key Setup

### Method 1: `.env` file

Edit `.env` in the project root:

```bash
# OpenAI
OPENAI_API_KEY=sk-proj-your_key_here

# Anthropic
ANTHROPIC_API_KEY=sk-ant-your_key_here

# Groq
GROQ_API_KEY=gsk_your_key_here
```

### Method 2: Interactive setup

```bash
python main.py --setup-keys
```

Then follow the prompts for secure API key setup.

## Provider Comparison | Provider | Speed | Cost | Setup | Recommended For |
|----------|-------|------|-------|-----------------|
| Ollama | Fast (local) | Free | Simple | Development, privacy-focused workflows |
| Groq | Very fast | Free tier available | API key | Production workloads focused on latency |
| Claude 3 | Fast | Paid | API key | Production workloads focused on output quality |
| GPT-4 | Medium | Paid (higher cost) | API key | Complex reasoning and high-accuracy tasks |

## Best Practices

### Choose provider by use case

- Development and testing: Ollama
- Production with speed priority: Groq
- Production with quality priority: Claude 3 Sonnet
- Complex tasks: GPT-4 or Claude 3 Opus

### Temperature settings

```text
Temperature (0.0-1.0) [0.7]:
```

- 0.0-0.3: Deterministic, factual responses (useful for OSINT and research)
- 0.4-0.7: Balanced output (recommended default)
- 0.8-1.0: Creative output (brainstorming and ideation)

### Context size

```text
Max Tokens / Context Size (1000-32000) [16000]:
```

- Larger context enables broader multi-source synthesis
- Cloud provider usage costs can increase with larger context windows
- RTX 3080-class hardware: 16K-32K is typically practical
- Smaller GPUs: 4K-8K is typically more stable

## Troubleshooting

### "API key not found"

1. Check `.env`:

```bash
cat .env | grep API_KEY
```

2. Verify dotenv loading:

```bash
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('GROQ_API_KEY'))"
```

### "Invalid API key"

1. Verify key format:
- OpenAI: `sk-proj-...`
- Anthropic: `sk-ant-...`
- Groq: `gsk_...`

2. Validate the key in the provider dashboard.

3. Do not wrap keys in quotes in `.env`:

```bash
# Incorrect
GROQ_API_KEY="gsk_..."

# Correct
GROQ_API_KEY=gsk_...
```

### Provider switch does not apply

1. Restart the agent after changing provider.
2. For cloud providers, install required SDKs:

```bash
pip install openai anthropic groq
```

## Additional Resources

- Cloud LLM integration guide: [CLOUD_LLM_INTEGRATION.md](CLOUD_LLM_INTEGRATION.md)
- API key setup and security policies: [SECURITY.md](../../SECURITY.md)
- Provider dashboards:
 - [OpenAI Platform](https://platform.openai.com/)
 - [Anthropic Console](https://console.anthropic.com/)
 - [Groq Console](https://console.groq.com/)
