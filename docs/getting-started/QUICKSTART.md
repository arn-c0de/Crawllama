# CrawlLama - Quick Start Guide

---

 **Navigation:** 
[Home](../../README.md) | [Docs](../README.md) | [Installation](INSTALLATION.md) | [LangGraph](../guides/LANGGRAPH_GUIDE.md) | [OSINT](../osint/OSINT_USAGE.md)

---

## Installation in 5 Minutes

### Step 1: Check Prerequisites
- **Python 3.10+** installed 
- **Ollama** installed and running 
- **Git** to clone the repository 

### Step 2: Clone Repository
```bash
git clone https://github.com/arn-c0de/Crawllama.git
cd Crawllama
````

### Step 3: Run Setup Script

**Windows:**

```cmd
setup.bat
```

**Linux/macOS:**

```bash
chmod +x setup.sh
./setup.sh
```

The script automatically installs:

* Python dependencies
* Required directories
* Copies `.env.example` → `.env`

 **Note:** Installing dependencies (e.g., `torch`, `sentence-transformers`) may take **5–10 minutes** on first run.

---

### Step 4: Start Ollama

```bash
# In a separate terminal
ollama serve
```

 **Disk Space Requirements:**
Project + `venv` + optional models: ~1–2 GB (can increase with larger models).

Approx. model sizes:

* `qwen3:4b` → 2–4 GB
* `qwen3:8b` → 8–12 GB
* `deepseek-r1:8b` → 6–10 GB
* `llama3:7b` → 6–9 GB
* `mistral:7b` → 4–8 GB
* `phi3:14b` → 12–20+ GB

> Note: Sizes vary depending on format (FP16, INT8) and extra assets.

---

### Step 5: Download Model

```bash
ollama pull qwen3:8b
```

Other options:

```bash
ollama pull deepseek-r1:8b # Strong reasoning
ollama pull qwen3:4b # Smaller, faster
ollama pull llama3:7b # Larger, more accurate
ollama pull mistral:7b # Good for reasoning
ollama pull phi3:14b # High-performance, more RAM
```

---

### Step 6: Start CrawlLama

**Windows:**

```cmd
run.bat
```

**Linux/macOS:**

```bash
./run.sh
```

> Always use the run scripts to auto-activate the virtual environment.

---

## First Steps

### Interactive Mode

Start CrawlLama and ask questions:

```bash
run.bat # Windows
./run.sh # Linux/macOS
```

```
 What is Python?
 How does photosynthesis work?
 Who developed the theory of relativity?
```

---

## Customize Configuration

Edit `config.json`:

```json
{
 "llm": {
 "model": "deepseek-r1:8b",
 "temperature": 0.7,
 "max_tokens": 4096
 },
 "cache": {
 "enabled": true,
 "ttl_hours": 24
 }
}
```

---

## Common Commands | Windows | Linux/macOS | Description |
| ----------------------- | ------------------------ | ---------------- |
| `run.bat` | `./run.sh` | Interactive mode |
| `run.bat "Question"` | `./run.sh "Question"` | Direct question |
| `run.bat --stats` | `./run.sh --stats` | Show stats |
| `run.bat --clear-cache` | `./run.sh --clear-cache` | Clear cache |
| `run.bat --no-web` | `./run.sh --no-web` | Offline mode |
| `run.bat --debug` | `./run.sh --debug` | Debug mode |

---

## Troubleshooting

### Ollama Not Running

```bash
ollama serve
```

### Model Not Found

```bash
ollama pull qwen3:8b
```

### Import Errors

```bash
setup.bat # Windows
./setup.sh # Linux/macOS
```

### ChromaDB Issues

```bash
rm -rf data/embeddings/ # Linux/macOS
rmdir /s data\embeddings # Windows
```

---

## Further Documentation

* `README.md` - Main docs
* `docs/getting-started/INSTALLATION.md` - Detailed setup
* `docs/guides/LANGGRAPH_GUIDE.md` - Multi-hop reasoning

---

## Example Session

```
$ run.bat

╭──────────────────────────────╮
│ CrawlLama - Local Search Agent │
╰──────────────────────────────╯

 What is the capital of Germany?
The capital of Germany is **Berlin** (since 1990).

 How many inhabitants does Berlin have?
Berlin has about **3.7 million** people (2024).

 stats
{
 "tools_available": 3,
 "web_enabled": true,
 "model": "qwen3:4b",
 "cache": {
 "total_files": 2,
 "total_size_mb": 0.05
 }
}

 exit
Goodbye!
```

---

## You're Ready!

CrawlLama is now installed and ready for use.

If you encounter issues: [GitHub Issues](https://github.com/arn-c0de/Crawllama/issues)

