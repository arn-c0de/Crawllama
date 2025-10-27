# CrawlLama - Quick Start Guide

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [📦 Installation](INSTALLATION.md) | [🧠 LangGraph](../guides/LANGGRAPH_GUIDE.md) | [🔍 OSINT](../osint/OSINT_USAGE.md)

---

## 🚀 Installation in 5 Minutes

### Step 1: Check Prerequisites

- **Python 3.10+** must be installed
- **Ollama** must be installed and running
- **Git** (to clone the repo)

### Step 2: Clone Repository

```bash
git clone https://github.com/arn-c0de/Crawllama.git
cd crawllama
```

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
- All Python dependencies
- Creates necessary directories
- Copies .env.example to .env

⚠️ Note about initial installation:

When running `pip install -r requirements.txt` for the first time inside the newly created `venv`, installing all dependencies — especially packages like `torch`, `sentence-transformers`, and scientific libraries — can take **5–10 minutes** (or longer, depending on connection and hardware). Please wait until the process is complete; afterwards, the virtual environment is ready to use.

### Step 4: Start Ollama

```bash
# In a separate terminal
ollama serve
```

Note about disk space: After installation (including `venv` and optional model downloads), the project typically requires about **1–2 GB** of free disk space. This value can be significantly higher depending on the operating system, Python packages (e.g., larger PyTorch/CUDA wheels), and additional models. Plan generously for extra space if disk space is limited.

Model download sizes (approximate):

- `qwen3:4b` — approx. **2–4 GB** (depending on format/quantization)
- `qwen3:8b` — approx. **8–12 GB**
- `deepseek-r1:8b` — approx. **6–10 GB**
- `llama3:7b` — approx. **6–9 GB**
- `mistral:7b` — approx. **4–8 GB**
- `phi3:14b` — approx. **12–20+ GB**

Note: Model sizes vary greatly depending on the provider, format (FP16, INT8 quantization, etc.), and additional assets. Quantized models (e.g., INT8) can significantly reduce size, while FP32/FP16 or models with additional tokenizer/vocab files require more space. Plan sufficient extra storage if you want to use larger models or multiple models simultaneously.

### Step 5: Download Model

```bash
ollama pull deepseek-r1:8b
```

Alternative models:
```bash
ollama pull qwen3:4b   # Smaller, faster
ollama pull llama3:7b    # Larger, better
ollama pull mistral:7b   # Very good for reasoning
ollama pull phi3:14b     # Even better, needs more RAM
```

### Step 6: Start CrawlLama

**Windows:**
```cmd
run.bat
```

**Linux/macOS:**
```bash
./run.sh
```

**Important:** Always use the run scripts so the virtual environment is activated automatically!

## 💡 First Steps

### Interactive Mode

Simply start and ask questions:

**Windows:**
```cmd
run.bat
```

**Linux/macOS:**
```bash
./run.sh
```

```
❯ What is Python?
❯ How does photosynthesis work?
❯ Who developed the theory of relativity?
```

### Direct Questions

**Windows:**
```cmd
run.bat "What is artificial intelligence?"
```

**Linux/macOS:**
```bash
./run.sh "What is artificial intelligence?"
```

### Offline Mode (without web search)

```cmd
run.bat --no-web "Explain the solar system"  # Windows
./run.sh --no-web "Explain the solar system"  # Linux/macOS
```

## 🔧 Customize Configuration

Edit `config.json`:

```json
{
  "llm": {
    "model": "deepseek-r1:8b",    // Change the model here
    "temperature": 0.7,       // Creativity (0.0-1.0)
    "max_tokens": 4096
  },
  "cache": {
    "enabled": true,          // Enable/disable cache
    "ttl_hours": 24          // Cache validity
  }
}
```

## 🎯 Common Commands

| Command (Windows) | Command (Linux/macOS) | Description |
|------------------|----------------------|--------------|
| `run.bat` | `./run.sh` | Interactive mode |
| `run.bat "Question"` | `./run.sh "Question"` | Direct question |
| `run.bat --stats` | `./run.sh --stats` | Show statistics |
| `run.bat --clear-cache` | `./run.sh --clear-cache` | Clear cache |
| `run.bat --no-web` | `./run.sh --no-web` | Offline mode |
| `run.bat --debug` | `./run.sh --debug` | Debug mode |

## ⚠️ Troubleshooting

### "Ollama is not running"

```bash
# Start Ollama in a separate terminal
ollama serve
```

### "Model not found"

```bash
# Download the model
ollama pull deepseek-r1:8b
```

### Import Errors

```bash
# Run setup again (automatically activates venv)
setup.bat  # Windows
./setup.sh  # Linux/macOS
```

### ChromaDB Errors

```bash
# Delete embeddings and restart
rm -rf data/embeddings/
# Windows: rmdir /s data\embeddings
```

## 📚 Further Documentation

- **README.md** - Complete documentation
- **docs/INSTALLATION.md** - Detailed setup guide
- **docs/LANGGRAPH_GUIDE.md** - Multi-hop reasoning details

## 💬 Example Session

```
$ run.bat  # Windows or ./run.sh (Linux/macOS)

╭─────────────────────────────────────────╮
│ CrawlLama - Local Search and Answer Agent │
╰─────────────────────────────────────────╯

❯ What is the capital of Germany?

Processing query...

The capital of Germany is **Berlin**. Berlin has been the capital since
reunification in 1990 and is also a federal state of the Federal
Republic of Germany.

❯ How many inhabitants does Berlin have?

Processing query...

[Searching the web...]

Berlin has about **3.7 million inhabitants** (as of 2024) and is
Germany's most populous city.

❯ stats

{
  "tools_available": 3,
  "web_enabled": true,
  "model": "qwen3:4b",
  "cache": {
    "total_files": 2,
    "total_size_mb": 0.05
  }
}

❯ exit
Goodbye!
```

## 🎉 Done!

You can now ask questions and use CrawlLama!

If you have problems: [GitHub Issues](https://github.com/arn-c0de/Crawllama/issues)
