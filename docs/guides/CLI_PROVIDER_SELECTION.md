# Cloud LLM Provider Selection in CLI Settings

## 📋 Overview

Ab Version 1.4.4 kannst du im CLI-Settings-Menü zwischen lokalen (Ollama) und Cloud-LLM-Providern wählen.

## 🎯 Verwendung

### 1. Settings-Menü öffnen

```bash
python main.py --interactive
```

Im interaktiven Modus:
```
❯ settings
```

### 2. LLM-Kategorie auswählen

```
Welche Kategorie möchtest du ändern?
> llm
```

### 3. Provider auswählen

```
=== LLM Einstellungen ===

Verfügbare Provider:
  • ollama - Lokale Modelle (kostenlos)
  • openai - GPT-3.5, GPT-4 (API-Key erforderlich)
  • anthropic - Claude 3 (API-Key erforderlich)
  • groq - Mixtral, LLaMA (kostenlos mit Free Tier)

LLM Provider [ollama]: groq
[OK] Provider geändert: groq
⚠️ Groq erfordert einen API-Key!
Setze GROQ_API_KEY in .env Datei
```

### 4. Modell auswählen

Das System zeigt automatisch passende Modelle für den gewählten Provider:

**Ollama:**
```
Ollama Modelle: qwen2.5:3b, qwen3:8b, deepseek-r1:8b, llama3:7b
LLM Model [qwen3:8b]: deepseek-r1:8b
```

**OpenAI:**
```
OpenAI Modelle: gpt-3.5-turbo, gpt-4, gpt-4-turbo
LLM Model [gpt-3.5-turbo]: gpt-4
```

**Anthropic:**
```
Anthropic Modelle: claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307
LLM Model [claude-3-sonnet-20240229]: claude-3-opus-20240229
```

**Groq:**
```
Groq Modelle: mixtral-8x7b-32768, llama2-70b-4096, gemma-7b-it
LLM Model [mixtral-8x7b-32768]: llama2-70b-4096
```

### 5. Einstellungen speichern

```
Einstellungen speichern? (y/n) [y]: y
[OK] Konfiguration gespeichert: config.json

Agent neu starten um Änderungen zu übernehmen? (y/n) [y]: y
[cyan]Lade Konfiguration neu...[/cyan]
[cyan]Initialisiere Agents neu...[/cyan]
```

## 🔐 API-Keys einrichten

### Methode 1: .env Datei

Bearbeite `.env` im Projekt-Root:

```bash
# OpenAI
OPENAI_API_KEY=sk-proj-your_key_here

# Anthropic
ANTHROPIC_API_KEY=sk-ant-your_key_here

# Groq
GROQ_API_KEY=gsk_your_key_here
```

### Methode 2: Interaktives Setup

```bash
python main.py --setup-keys
```

Folge den Anweisungen für sicheres API-Key-Setup.

## 📊 Provider-Vergleich

| Provider | Geschwindigkeit | Kosten | Setup | Empfehlung |
|----------|----------------|--------|-------|------------|
| **Ollama** | Schnell (lokal) | ✅ Kostenlos | Einfach | Development, Privacy |
| **Groq** | ⚡ Sehr schnell | ✅ Free Tier | API-Key | Production (Speed) |
| **Claude 3** | Schnell | 💰 Mittel | API-Key | Production (Quality) |
| **GPT-4** | Mittel | 💰💰 Teuer | API-Key | Complex Tasks |

## 💡 Tipps

### Provider nach Anwendungsfall

- **Development/Testing**: Ollama (kostenlos, schnell, keine API-Limits)
- **Production (Geschwindigkeit)**: Groq (sehr schnell, kostenloser Free Tier)
- **Production (Qualität)**: Claude 3 Sonnet (ausgewogenes Preis-Leistungs-Verhältnis)
- **Komplexe Aufgaben**: GPT-4 oder Claude 3 Opus (teuer, aber sehr fähig)

### Temperatur-Einstellungen

```
Temperature (0.0-1.0) [0.7]: 
```

- **0.0-0.3**: Deterministisch, faktentreu (gut für OSINT, Recherche)
- **0.4-0.7**: Ausgewogen (empfohlen für allgemeine Nutzung)
- **0.8-1.0**: Kreativ (gut für Brainstorming, kreatives Schreiben)

### Context-Größe

```
Max Tokens / Context Size (1000-32000) [16000]:
```

- Größerer Context = Mehr Informationen gleichzeitig verarbeiten
- Aber: Höhere Kosten bei Cloud-Providern
- RTX 3080: 16K-32K optimal
- Kleinere GPUs: 4K-8K empfohlen

## 🐛 Troubleshooting

### "API key not found" Fehler

1. Prüfe `.env` Datei:
   ```bash
   cat .env | grep API_KEY
   ```

2. Stelle sicher, dass `.env` geladen wird:
   ```bash
   python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('GROQ_API_KEY'))"
   ```

### "Invalid API key" Fehler

1. Prüfe Key-Format:
   - OpenAI: `sk-proj-...`
   - Anthropic: `sk-ant-...`
   - Groq: `gsk_...`

2. Verifiziere Key-Gültigkeit im Provider-Dashboard

3. Keine Anführungszeichen in `.env`:
   ```bash
   # FALSCH
   GROQ_API_KEY="gsk_..."

   # RICHTIG
   GROQ_API_KEY=gsk_...
   ```

### Provider-Wechsel funktioniert nicht

1. Nach Provider-Wechsel immer **Agent neu starten**
2. Bei Cloud-Providern: Installiere benötigte Pakete:
   ```bash
   pip install openai anthropic groq
   ```

## 📚 Weitere Ressourcen

- **Detaillierte Cloud-LLM-Dokumentation**: [CLOUD_LLM_INTEGRATION.md](CLOUD_LLM_INTEGRATION.md)
- **API-Key-Setup**: [SECURITY.md](../../SECURITY.md)
- **Provider-APIs**:
  - [OpenAI Platform](https://platform.openai.com/)
  - [Anthropic Console](https://console.anthropic.com/)
  - [Groq Console](https://console.groq.com/)
