# CrawlLama - Installation & Start

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🚀 Quickstart](QUICKSTART.md) | [🧠 LangGraph](../guides/LANGGRAPH_GUIDE.md)

---

## 🚀 Quick Installation

### Windows

1. **Run setup:**
```cmd
setup.bat
```

2. **Start Ollama (separate terminal):**
```cmd
ollama serve
```

⚠️ Note about initial installation:

When running `pip install -r requirements.txt` for the first time inside the newly created `venv`, installing all dependencies — especially packages like `torch`, `sentence-transformers`, and scientific libraries — can take **5–10 minutes** (or longer, depending on connection and hardware). Please wait until the process is complete; afterwards, the virtual environment is ready to use.

3. **Load model:**
```cmd
ollama pull deepseek-r1:8b
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

4. **Start CrawlLama:**
```cmd
run.bat
```

### Linux/macOS

1. **Run setup:**
```bash
chmod +x setup.sh run.sh
./setup.sh
```

2. **Start Ollama (separate terminal):**
```bash
ollama serve
```

3. **Load model:**
```bash
ollama pull deepseek-r1:8b
```

4. **Start CrawlLama:**
```bash
./run.sh
```

## 📦 What Does setup.bat/setup.sh Do?

1. ✅ Checks Python installation (min. 3.10)
2. ✅ Creates virtual environment (venv)
3. ✅ Activates venv automatically
4. ✅ Installs all dependencies in venv
5. ✅ Creates necessary directories (data/, logs/)
6. ✅ Copies .env.example to .env
7. ✅ Checks Ollama installation

## 🎮 Using run.bat/run.sh

**Important:** ALWAYS use the run scripts so the virtual environment is activated automatically!

### Examples:

```cmd
# Interactive
run.bat

# Direct question
run.bat "What is Python?"

# With options
run.bat --no-web "Offline question"
run.bat --debug "Debug mode"
run.bat --stats
run.bat --clear-cache
```

## 🔧 Manual venv Activation (if needed)

If you want to activate the venv manually:

**Windows:**
```cmd
venv\Scripts\activate
python main.py
```

**Linux/macOS:**
```bash
source venv/bin/activate
python main.py
```

## 📂 Directory Structure After Installation

```
crawllama/
├── venv/                  # Virtual environment (created by setup)
├── data/
│   ├── cache/             # Web cache
│   ├── embeddings/        # ChromaDB
│   └── history/           # Chat history
├── logs/
│   └── app.log           # Logs (automatically created)
├── setup.bat/setup.sh    # Setup script
├── run.bat/run.sh        # Start script (uses venv)
└── ...
```

## ⚠️ Common Issues

### "venv not found"
```bash
# Run setup again
setup.bat  # or ./setup.sh
```

### "Ollama not running"
```bash
# In separate terminal
ollama serve
```

### "Model not found"
```bash
ollama pull deepseek-r1:8b
```

### Dependencies missing
```bash
# Run setup again (installs in venv)
setup.bat  # or ./setup.sh
```

## 🎯 Alternative Models

```bash
# Standard (recommended)
ollama pull deepseek-r1:8b

# Faster, smaller
ollama pull qwen3:4b

# Larger, better
ollama pull llama3:7b
ollama pull mistral:7b

# Very good, needs more RAM
ollama pull phi3:14b
```

## ✅ Test Installation

```cmd
# Show statistics (without query)
run.bat --stats

# Should display:
# - tools_available: 3
# - web_enabled: true
# - model: deepseek-r1:8b
# - cache: {...}
```

## 🆘 Support

If you have problems:
- **GitHub Issues:** [Crawllama Issues](https://github.com/arn-c0de/Crawllama/issues)
- **Support Email:** [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com)
- **Documentation:** README.md, QUICKSTART.md
- **Debug Mode:** `run.bat --debug`
