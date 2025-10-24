# Search Engine Limitations

## DuckDuckGo Ergebnislimit

### Problem
DuckDuckGo begrenzt die Anzahl der Suchergebnisse oft auf **10 Ergebnisse**, unabhängig davon, wie viele Ergebnisse angefordert werden. Dies ist eine bekannte Limitation der DuckDuckGo API/DDGS-Bibliothek.

### Konfiguration
In der `config.json` können Sie die maximale Anzahl der Ergebnisse konfigurieren:

```json
{
  "search": {
    "max_results": 25,  // Für normale Websuchen
    ...
  },
  "osint": {
    "max_results": 25,  // Für OSINT/site: Suchen
    ...
  }
}
```

**Hinweis:** Auch wenn Sie `max_results: 25` setzen, kann DuckDuckGo trotzdem nur 10 Ergebnisse zurückgeben.

### Lösungsansätze

#### 1. Fallback auf andere Suchmaschinen
Wenn mehr Ergebnisse benötigt werden, können Sie alternative Suchprovider verwenden:

```json
{
  "search": {
    "provider": "brave",  // oder "serper"
    "fallback_providers": ["duckduckgo"]
  }
}
```

**Brave Search** und **Serper** unterstützen mehr Ergebnisse:
- Brave: bis zu 20+ Ergebnisse
- Serper: bis zu 100+ Ergebnisse (mit API-Key)

#### 2. Mehrfache Suchen mit unterschiedlichen Keywords
Statt einer einzigen Suche können Sie mehrere Suchen mit spezifischeren Keywords durchführen:

```
site:example.com produkt
site:example.com dienstleistung
site:example.com kontakt
```

#### 3. Paginierung (nicht unterstützt)
DuckDuckGo unterstützt keine echte Paginierung über die DDGS-API.

### Aktuelle Implementierung
Crawllama protokolliert automatisch eine Warnung, wenn weniger Ergebnisse zurückkommen als angefordert:

```
⚠️ DuckDuckGo returned only 10 results (requested: 25). This is a known limitation.
```

### Empfehlung
Für OSINT-Analysen mit vielen Ergebnissen:
1. Setzen Sie `"provider": "brave"` in der config.json
2. Oder verwenden Sie Serper mit einem API-Key
3. Oder führen Sie mehrere spezifische Suchen durch

### API-Keys einrichten

#### Serper (empfohlen für viele Ergebnisse)
1. Registrieren Sie sich bei https://serper.dev/
2. Holen Sie sich einen kostenlosen API-Key (2500 Anfragen/Monat)
3. Setzen Sie die Umgebungsvariable: `SERPER_API_KEY=your_key_here`

#### Brave Search
1. Registrieren Sie sich bei https://brave.com/search/api/
2. Holen Sie sich einen kostenlosen API-Key (2000 Anfragen/Monat)
3. Setzen Sie die Umgebungsvariable: `BRAVE_API_KEY=your_key_here`

### Status
- ✅ DuckDuckGo: Kostenlos, keine API-Keys, aber nur ~10 Ergebnisse
- ✅ Brave: Kostenlos (mit API-Key), bis zu 20+ Ergebnisse
- ✅ Serper: Kostenlos (mit API-Key), bis zu 100+ Ergebnisse

---

**Letzte Aktualisierung:** 24.10.2025
