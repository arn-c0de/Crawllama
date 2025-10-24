# OSINT Cache Fix - Result Reference Support

## Problem
Nach einer OSINT-Suche (z.B. `site:example.com`) konnten die Ergebnisse nicht mit dem `quelle`-Befehl abgerufen werden. Der Fehler war:

```
❯: quelle 6 7
Keine vorherigen Suchergebnisse vorhanden. Bitte führen Sie zuerst eine Suche durch.
```

Obwohl die OSINT-Suche erfolgreich war und Ergebnisse anzeigte.

## Ursache
Das Problem lag im **Caching-Mechanismus**:

1. OSINT-Suche wurde durchgeführt → `last_search_results` wurde gesetzt ✅
2. Session wurde korrekt gespeichert ✅
3. **ABER**: Beim nächsten `quelle 6 7` Befehl wurde die **gecachte** Antwort zurückgegeben
4. Diese gecachte Antwort stammte von **vor** der OSINT-Suche (als noch keine Ergebnisse vorhanden waren)

### Cache-Flow (vorher):
```
User: site:example.com
→ OSINT-Suche → Ergebnisse [1-10] → Session speichern ✅

User: quelle 6 7
→ Cache-Check → Findet gecachte Antwort "Keine Ergebnisse" ❌
→ Gibt alte Antwort zurück (FALSCH!)
```

## Lösung
Result-Reference-Queries (wie `quelle`, `ergebnis`, `source`, etc.) werden jetzt **vom Caching ausgenommen**.

### Geänderte Dateien:
- `core/agent.py`

### Änderungen:
1. **Cache-Check erweitert** (Zeile 201-202):
   ```python
   # Check if query is a result reference (quelle/source) - skip cache for these
   is_result_ref = self._is_result_reference(user_query)
   if is_result_ref:
       logger.info(f"Result reference detected - cache disabled for: '{user_query}'")
   ```

2. **Cache-Get-Bedingung erweitert** (Zeile 205):
   ```python
   if self.cache and not force_context_mode and not is_result_ref:
   ```

3. **Cache-Set-Bedingung erweitert** (Zeile 240):
   ```python
   if self.cache and not force_context_mode and not is_result_ref:
   ```

4. **Email-Search-Ergebnisse speichern** (Zeile ~1675):
   ```python
   # Store results in session for quelle/source commands
   if unique_results:
       self.last_search_results = unique_results
       self.last_search_query = f'email:{email}'
       logger.info(f"Stored {len(unique_results)} email search results in session state")
   ```

5. **Phone-Search-Ergebnisse speichern** (Zeile ~1763):
   ```python
   # Store results in session for quelle/source commands
   if unique_results:
       self.last_search_results = unique_results
       self.last_search_query = f'phone:{phone_result["input"]}'
       logger.info(f"Stored {len(unique_results)} phone search results in session state")
   ```

### Cache-Flow (nachher):
```
User: site:example.com
→ OSINT-Suche → Ergebnisse [1-10] → Session speichern ✅

User: quelle 6 7
→ Cache-Check → Result-Reference erkannt → Cache ÜBERSPRUNGEN ✅
→ Lädt aktuelle Session → Findet last_search_results [1-10] ✅
→ Gibt Ergebnisse 6 und 7 zurück (KORREKT!)
```

## Erkannte Result-Reference-Patterns
Die folgenden Patterns werden als Result-References erkannt:

- `quelle 1`, `quellen 2, 3`
- `ergebnis 5`, `ergebnisse 1-3`
- `result 4`, `results 2, 5`
- `source 6`, `sources 1, 7, 9`
- `durchsuche quellen`
- `suche in quellen`
- `analysiere ergebnisse`
- Und viele weitere Varianten...

Siehe `RESULT_REFERENCE_PATTERNS` in `core/agent.py` für die vollständige Liste.

## Getestete Szenarien

### ✅ Szenario 1: OSINT + Quelle
```
❯: site:example.com
→ Ergebnisse [1-10] angezeigt

❯: quelle 6 7
→ Ergebnisse 6 und 7 werden korrekt abgerufen
```

### ✅ Szenario 2: Web-Suche + Quelle
```
❯: Python tutorials
→ Ergebnisse [1-5] angezeigt

❯: quelle 2
→ Ergebnis 2 wird korrekt abgerufen
```

### ✅ Szenario 3: Email-OSINT + Quelle
```
❯: email:info@example.com
→ Email-Analyse + Online-Ergebnisse [1-4] angezeigt

❯: quelle 1 2 3 4
→ Ergebnisse 1-4 werden korrekt abgerufen
```

### ✅ Szenario 4: Phone-OSINT + Quelle
```
❯: phone:+49123456789
→ Phone-Analyse + Online-Ergebnisse [1-3] angezeigt

❯: quelle 1 2 3
→ Ergebnisse 1-3 werden korrekt abgerufen
```

### ✅ Szenario 5: Context-Only Mode
```
❯: site:example.com
→ Ergebnisse [1-10] angezeigt

❯: <quelle 6 7
→ Nur URLs werden angezeigt (kein LLM-Aufruf)
```

## Zusätzliche Vorteile
- **Bessere Logging**: Result-References werden jetzt im Log erkannt
- **Konsistentes Verhalten**: Quelle-Befehle funktionieren gleich wie der `<` Prefix
- **Keine Performance-Einbußen**: Cache funktioniert weiterhin für normale Queries

## Testing
Um zu testen, ob die Änderung funktioniert:

1. Führen Sie eine OSINT-Suche durch:
   ```
   site:example.com
   ```

2. Verwenden Sie den `quelle` Befehl:
   ```
   quelle 1 2 3
   ```

3. Überprüfen Sie das Log:
   ```
   INFO: Result reference detected - cache disabled for: 'quelle 1 2 3'
   ```

4. Die Ergebnisse sollten korrekt abgerufen werden! ✅

---

**Datum:** 25.10.2025  
**Status:** ✅ Behoben  
**Version:** 1.0
