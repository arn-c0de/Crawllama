# 🚀 CrawlLama - Installation & Start

---

📚 **Navigation:**  
[🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🚀 Quickstart](QUICKSTART.md) | [🧠 LangGraph](../guides/LANGGRAPH_GUIDE.md)

---

## 🛠️ Quick Installation

### Windows

1. **Run setup:**
```cmd
setup.bat
````

2. **Start Ollama (separate terminal):**

```cmd
ollama serve
```

⚠️ **Note:** The first `pip install -r requirements.txt` inside the new `venv` may take **5–10 minutes** or longer for packages like `torch` and `sentence-transformers`. Wait until installation completes.

3. **Download Model:**

```cmd
ollama pull deepseek-r1:8b
```

4. **Start CrawlLama:**

```cmd
run.bat
```

---

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

3. **Download Model:**

```bash
ollama pull deepseek-r1:8b
```

4. **Start CrawlLama:**

```bash
./run.sh
```

---

## 📦 What setup.bat / setup.sh Does

1. ✅ Checks Python (≥ 3.10)
2. ✅ Creates & activates virtual environment (`venv`)
3. ✅ Installs dependencies
4. ✅ Creates directories (`data/`, `logs/`)
5. ✅ Copies `.env.example` → `.env`
6. ✅ Verifies Ollama installation

---

## 🎮 Using run.bat / run.sh

**Always use the run scripts** to activate the virtual environment automatically.

**Examples:**

```cmd
# Interactive mode
run.bat

# Direct question
run.bat "What is Python?"

# Options
run.bat --no-web "Offline question"
run.bat --debug "Debug mode"
run.bat --stats
run.bat --clear-cache
```

---

## 🔧 Manual venv Activation

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

---

## 📂 Directory Structure After Installation

```
crawllama/
├── venv/                  # Virtual environment
├── data/
│   ├── cache/             # Web cache
│   ├── embeddings/        # ChromaDB
│   └── history/           # Chat history
├── logs/
│   └── app.log           # Logs
├── setup.bat/setup.sh    # Setup scripts
├── run.bat/run.sh        # Start scripts
└── ...
```

---

## ⚠️ Common Issues

| Issue                | Solution                                          |
| -------------------- | ------------------------------------------------- |
| `venv not found`     | Run `setup.bat` or `./setup.sh` again             |
| `Ollama not running` | Start Ollama: `ollama serve` in separate terminal |
| `Model not found`    | Download: `ollama pull deepseek-r1:8b`            |
| Missing dependencies | Run setup script again                            |

---

## 🎯 Alternative Models

```bash
# Recommended
ollama pull deepseek-r1:8b

# Faster, smaller
ollama pull qwen3:4b

# Larger, more accurate
ollama pull llama3:7b
ollama pull mistral:7b

# Very high performance, more RAM
ollama pull phi3:14b
```

> 💾 **Disk Space Note:** After setup + models, expect 1–2 GB minimum; larger models may require 6–20+ GB depending on format.

---

## ✅ Test Installation

```cmd
# Show system stats
run.bat --stats
```

Expected output:

```json
{
  "tools_available": 3,
  "web_enabled": true,
  "model": "deepseek-r1:8b",
  "cache": {...}
}
```

---

## 🆘 Support

* **GitHub Issues:** [Crawllama Issues](https://github.com/arn-c0de/Crawllama/issues)
* **Email:** [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com)
* **Documentation:** `README.md`, `QUICKSTART.md`
* **Debug Mode:** `run.bat --debug` or `./run.sh --debug`

