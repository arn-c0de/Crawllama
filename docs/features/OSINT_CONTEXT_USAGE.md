# OSINT Ergebnisse als Kontext nutzen

## Übersicht
Nach einer OSINT-Suche können Sie die Ergebnisse als **Kontext-Quelle** für weitere Analysen verwenden.

## Workflow

### 1. OSINT-Suche durchführen
```
❯: site:example.com
```

**Ausgabe:**
```
[1] Example - Homepage
    https://example.com
    This is the homepage...

[2] Example - Kontakt
    https://example.com/kontakt
    Kontaktieren Sie uns...

[3] Example - Impressum
    https://example.com/impressum
    Impressum und rechtliche Hinweise...
```

### 2. Ergebnisse als Kontext verwenden

#### Option A: Mit LLM-Analyse
```
❯: quelle 1 2 3
```

Der Agent wird:
1. Die URLs der Ergebnisse 1, 2 und 3 laden
2. Den Inhalt extrahieren
3. Eine **KI-Analyse** durchführen
4. Die Informationen zusammenfassen

**Beispiel:**
```
❯: fasse quellen 1 2 3 zusammen

✓ Ergebnis #1 geladen
✓ Ergebnis #2 geladen
✓ Ergebnis #3 geladen

Zusammenfassung der Quellen:

Die Website example.com bietet folgende Hauptbereiche:
- Homepage [1]: Hauptinformationen und Übersicht
- Kontakt [2]: Kontaktformular und E-Mail: info@example.com
- Impressum [3]: Rechtliche Informationen, Firmensitz in...
```

#### Option B: Nur URLs (Context-Only Mode)
```
❯: <quelle 1 2 3
```

**Ausgabe (ohne LLM-Aufruf):**
```
[1] Example - Homepage - https://example.com
[2] Example - Kontakt - https://example.com/kontakt
[3] Example - Impressum - https://example.com/impressum
```

## Erweiterte Verwendung

### Spezifische Analyse-Befehle

#### Kontaktdaten extrahieren
```
❯: finde kontaktdaten in quellen 1-5
```

#### Vergleich
```
❯: vergleiche quellen 2 und 5
```

#### Suche in Quellen
```
❯: suche nach "öffnungszeiten" in quellen 1-10
```

#### Email/Telefon-Extraktion
```
❯: extrahiere emails aus quellen 1 2 3
```

### Kombinierte OSINT-Operatoren

#### Site + Email-Suche
```
❯: site:example.com email:@example.com
```

Dann:
```
❯: analysiere quellen mit emails
```

#### Site + Intext-Suche
```
❯: site:example.com intext:"impressum"
```

Dann:
```
❯: fasse impressum-informationen aus quellen zusammen
```

## Tipps & Best Practices

### 1. Selektive Quellenauswahl
Wählen Sie nur relevante Ergebnisse aus:
```
❯: quelle 2 5 7    # Nur bestimmte Ergebnisse
```

Statt alle Ergebnisse:
```
❯: quelle 1-10     # Alle Ergebnisse (langsamer!)
```

### 2. Context-Only Mode für Übersicht
Verwenden Sie `<quelle` für schnelle URL-Übersicht:
```
❯: <quelle 1-5     # Schnelle Liste ohne Analyse
```

### 3. Gezielte Nachfragen
Nach der ersten Analyse können Sie spezifische Fragen stellen:
```
❯: site:example.com
❯: quelle 3
❯: welche kontaktdaten enthält diese seite?
```

### 4. Mehrfache Quellenverwendung
Sie können dieselben Quellen mehrfach verwenden:
```
❯: site:example.com
❯: quelle 1 2 3           # Erste Analyse
❯: finde öffnungszeiten   # Follow-up
❯: quelle 4 5             # Weitere Quellen
```

## Cache-Verhalten

### ✅ Result-References werden NICHT gecacht
```
❯: quelle 1 2 3
→ Immer aktuelle Ergebnisse aus Session
```

### ✅ Web-Seiten werden gecacht
```
❯: quelle 1
→ Lädt https://example.com (gecacht für 24h)

❯: quelle 1
→ Verwendet gecachten Inhalt (schneller!)
```

### ⚠️ Session wird automatisch gespeichert
Nach jeder OSINT-Suche wird die Session gespeichert:
```
INFO: Session saved to data\session.json
```

**Sicherheitshinweis:** Die `session.json` Datei ist bereits in `.gitignore` eingetragen und wird nicht ins Repository committed. Wenn du sensible Daten in Sessions speicherst, solltest du die Datei zusätzlich verschlüsseln oder die Session-Speicherung deaktivieren.

## Troubleshooting

### Problem: "Keine vorherigen Suchergebnisse"
**Ursache:** Keine OSINT/Web-Suche durchgeführt  
**Lösung:** Führen Sie zuerst eine Suche durch:
```
❯: site:example.com
❯: quelle 1
```

### Problem: "Ergebnis X existiert nicht"
**Ursache:** Ungültige Ergebnisnummer  
**Lösung:** Überprüfen Sie die verfügbaren Ergebnisse:
```
❯: <quelle 1-20    # Zeigt verfügbare Ergebnisse
```

### Problem: Cache zeigt alte Ergebnisse
**Ursache:** Cache-Problem (sollte nicht mehr auftreten)  
**Lösung:** Verwenden Sie Context-Only Mode:
```
❯: <quelle 1 2 3
```

Oder leeren Sie den Cache:
```
❯: /cache clear
```

## Beispiel-Workflows

### Workflow 1: Firmen-Recherche
```
# 1. Domain-Suche
❯: site:firma-example.de

# 2. Impressum und Kontakt laden
❯: quelle 2 3

# 3. Spezifische Analyse
❯: extrahiere firmendaten und kontaktinformationen

# 4. Weitere Details
❯: finde geschäftsführer und firmensitz
```

### Workflow 2: E-Mail-OSINT
```
# 1. E-Mail-Suche
❯: email:info@example.com

# 2. Ergebnisse analysieren
❯: quelle 1-5

# 3. Kontext extrahieren
❯: in welchen kontexten wird diese email erwähnt?
```

### Workflow 3: Konkurrenzanalyse
```
# 1. Suche Firma A
❯: site:firma-a.de
❯: quelle 1 2 3

# 2. Suche Firma B
❯: site:firma-b.de
❯: quelle 1 2 3

# 3. Vergleich
❯: vergleiche die beiden firmen basierend auf den quellen
```

## Performance-Tipps

### 🚀 Schneller
- Verwenden Sie Context-Only Mode: `<quelle 1-5`
- Wählen Sie nur relevante Ergebnisse: `quelle 2 5 7`
- Nutzen Sie gecachte Inhalte

### 🐌 Langsamer
- Alle Ergebnisse laden: `quelle 1-20`
- Mehrfache redundante Analysen
- Cache deaktiviert

---

**Weitere Dokumentation:**
- [OSINT_USAGE.md](OSINT_USAGE.md) - OSINT-Operatoren
- [OSINT_CACHE_FIX.md](OSINT_CACHE_FIX.md) - Cache-Probleme
- [QUICKSTART.md](QUICKSTART.md) - Erste Schritte

**Letzte Aktualisierung:** 25.10.2025
