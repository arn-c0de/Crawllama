# Memory Breach Storage - Dokumentation

## 📖 Übersicht

Das Memory-System speichert jetzt automatisch **Breach/Vulnerability-Daten** für jede gescannte E-Mail. Diese Informationen bleiben persistent gespeichert und können später abgerufen werden.

---

## ✨ Features

### 1. **Automatisches Speichern bei Email-Scans**
Wenn Sie eine E-Mail analysieren (z.B. `644aaronh@gmail.com`), werden die Ergebnisse automatisch gespeichert:
- ✅ HIBP Breach-Daten (wenn verfügbar)
- ✅ Vulnerability/Leak-Daten (LeakCheck, DeHashed, lokale Listen)
- ✅ Zeitstempel des letzten Scans
- ✅ Severity-Level

### 2. **Persistente Speicherung**
- Daten werden in `data/memory.json` gespeichert
- Überleben Session-Clears
- Können jederzeit abgerufen werden

### 3. **Formatierte Reports**
- Kompakte Übersicht über alle E-Mails
- Detaillierte Breach-Reports auf Anfrage
- Status-Indikatoren (SAFE, EXPOSED, COMPROMISED)

---

## 🚀 Verwendung

### Automatisch beim Scannen

Wenn Sie eine E-Mail scannen, werden die Breach-Daten automatisch gespeichert:

```
❯: 644aaronh@gmail.com
```

Das System:
1. Analysiert die E-Mail
2. Prüft auf Breaches & Leaks
3. Speichert die Ergebnisse automatisch
4. Zeigt die Informationen an

---

### Abrufen gespeicherter Daten

#### Option 1: Über Python-API

```python
from core.memory_store import get_memory_store

memory = get_memory_store()

# Einzelne E-Mail mit Breach-Daten abrufen
email_data = memory.get_email_with_breach_info('test@example.com')
print(email_data)

# Formatierten Report generieren
report = memory.format_email_breach_report('test@example.com')
print(report)

# Alle E-Mails auflisten
all_emails = memory.get_all_emails()
for entry in all_emails:
    email = entry['value']
    breach_data = entry.get('metadata', {}).get('breach_data', {})
    if breach_data:
        print(f"{email}: Breach-Daten vorhanden")
```

#### Option 2: Im Chat

```
❯: <zeige mir alle gespeicherten emails
```

Das System zeigt dann alle E-Mails mit ihrem Breach-Status an.

---

## 📊 Datenstruktur

### Gespeichertes Format in `data/memory.json`:

```json
{
  "emails": [
    {
      "value": "test@example.com",
      "added_at": "2025-01-27T10:30:00",
      "last_updated": "2025-01-27T11:00:00",
      "user_id": "anonymous",
      "metadata": {
        "source": "osint_scan",
        "breach_data": {
          "last_checked": "2025-01-27T11:00:00",
          "hibp": {
            "pwned": true,
            "breach_count": 3,
            "paste_count": 1,
            "severity": "high",
            "last_breach": "2024-01-15",
            "breaches": [
              {"name": "Breach1", "date": "2024-01"},
              {"name": "Breach2", "date": "2023-05"}
            ]
          },
          "vulnerability": {
            "vulnerable": true,
            "leak_count": 5,
            "severity": "medium",
            "found_in": ["Collection #1", "Pastebin"],
            "breach_sources": [
              {
                "source": "Collection #1",
                "type": "credential_dump",
                "date": "2019-01"
              },
              {
                "source": "Pastebin",
                "type": "paste_dump",
                "date": "2024-01"
              }
            ]
          }
        }
      }
    }
  ]
}
```

---

## 🎯 API-Funktionen

### `update_email_breach_info(email, breach_info, vuln_info)`
Aktualisiert Breach-Daten für eine E-Mail.

**Parameter:**
- `email`: E-Mail-Adresse
- `breach_info`: HIBP Breach-Daten (dict)
- `vuln_info`: Vulnerability/Leak-Daten (dict)

**Beispiel:**
```python
memory = get_memory_store()

breach_info = {
    'pwned': True,
    'breach_count': 3,
    'severity': 'high',
    'breaches': [...]
}

vuln_info = {
    'vulnerable': True,
    'leak_count': 5,
    'found_in': ['Collection #1'],
    'breach_sources': [...]
}

memory.update_email_breach_info('test@example.com', breach_info, vuln_info)
```

---

### `get_email_with_breach_info(email)`
Ruft E-Mail mit formatierten Breach-Daten ab.

**Rückgabe:**
```python
{
    'email': 'test@example.com',
    'added_at': '2025-01-27T10:30:00',
    'last_updated': '2025-01-27T11:00:00',
    'metadata': {...},
    'breach_summary': {
        'status': 'COMPROMISED',  # SAFE, EXPOSED, COMPROMISED
        'last_checked': '2025-01-27T11:00:00',
        'details': [
            {
                'type': 'Data Breach',
                'severity': 'HIGH',
                'breach_count': 3,
                'breaches': [...]
            },
            {
                'type': 'Public Leak',
                'severity': 'MEDIUM',
                'leak_count': 5,
                'sources': [...]
            }
        ]
    }
}
```

---

### `format_email_breach_report(email)`
Generiert formatierten Breach-Report.

**Beispiel-Output:**
```
============================================================
EMAIL BREACH REPORT (from Memory)
============================================================
Email: test@example.com
Added: 2025-01-27T10:30:00
Updated: 2025-01-27T11:00:00

🚨 Status: COMPROMISED
   Last Checked: 2025-01-27T11:00:00

============================================================
Data Breach - Severity: HIGH
============================================================
Breach Count: 3
Paste Count: 1
Last Breach: 2024-01-15

Known Breaches:
  1. Breach1 (2024-01)
  2. Breach2 (2023-05)

============================================================
Public Leak - Severity: MEDIUM
============================================================
Leak Count: 5
Found in: Collection #1, Pastebin

Leak Sources:
  1. Collection #1 (credential_dump)
  2. Pastebin (paste_dump)

============================================================
```

---

## 🔄 Workflow

### Email-Scan Workflow:

```
1. User scannt Email
   ↓
2. System analysiert:
   - HIBP (Breaches)
   - LeakCheck (Vulnerabilities)
   - Lokale Listen
   - GitHub Leaks
   ↓
3. Ergebnisse werden angezeigt
   ↓
4. Automatisches Speichern:
   - remember_email() → Email in Memory
   - update_email_breach_info() → Breach-Daten hinzufügen
   ↓
5. Daten persistent in data/memory.json
```

### Abruf-Workflow:

```
1. User fragt nach Email
   ↓
2. System ruft aus Memory ab:
   - get_email_with_breach_info()
   ↓
3. Formatierter Report wird generiert:
   - format_email_breach_report()
   ↓
4. Anzeige mit Status-Indikatoren
```

---

## 📋 Status-Indikatoren

| Status | Bedeutung | Icon |
|--------|-----------|------|
| **SAFE** | Keine Breaches oder Leaks gefunden | ✅ |
| **EXPOSED** | In öffentlichen Listen gefunden | 🔓 |
| **COMPROMISED** | In Daten-Breaches gefunden | 🚨 |
| **NO SCAN DATA** | Noch nicht gescannt | ❓ |

---

## 🧪 Testing

### Test-Skript ausführen:

```bash
python test_memory_breach.py
```

**Was das Skript testet:**
1. ✅ Speichern von Breach-Daten
2. ✅ Abrufen einzelner E-Mails
3. ✅ Generieren von Reports
4. ✅ Auflisten aller E-Mails mit Status

---

## 💡 Tipps & Best Practices

### 1. Regelmäßige Re-Scans
Breach-Daten veralten. Scannen Sie wichtige E-Mails regelmäßig:

```python
# Letzter Scan abrufen
email_data = memory.get_email_with_breach_info('important@example.com')
last_checked = email_data['breach_summary']['last_checked']

# Wenn älter als 30 Tage → Re-Scan
```

### 2. Batch-Verarbeitung
Scannen Sie mehrere E-Mails auf einmal:

```python
emails = memory.get_all_emails()
for entry in emails:
    email = entry['value']
    # Re-scan alte Einträge
```

### 3. Monitoring
Überwachen Sie kritische E-Mails:

```python
critical_emails = ['admin@company.com', 'ceo@company.com']
for email in critical_emails:
    data = memory.get_email_with_breach_info(email)
    if data['breach_summary']['status'] != 'SAFE':
        # Alert senden
        print(f"ALERT: {email} is compromised!")
```

---

## 🔐 Sicherheit & Datenschutz

### Was wird gespeichert?
- ✅ E-Mail-Adresse
- ✅ Breach-Status (pwned/not pwned)
- ✅ Anzahl der Breaches
- ✅ Namen der Breaches (keine Passwörter!)
- ✅ Leak-Quellen

### Was wird NICHT gespeichert?
- ❌ Passwörter
- ❌ Vollständige Leak-Daten
- ❌ Persönliche Informationen

### Datenschutz:
- Daten werden nur lokal gespeichert (`data/memory.json`)
- Keine Cloud-Übertragung
- Verschlüsselung möglich (implementieren Sie eigene Encryption)

---

## 📌 Beispiel-Session

```
❯: 644aaronh@gmail.com

[System analysiert...]

✅ Email: 644aaronh@gmail.com
🚨 Status: EXPOSED
   Leak Count: 9
   Found in: Tunngle.net, Deezer.com, Trello.com, ...

[Breach-Daten werden automatisch in Memory gespeichert]

---

❯: <gibt es leaks?

[System ruft gespeicherte Daten ab]

Ja, für 644aaronh@gmail.com:
- 9 Leaks gefunden
- Zuletzt gescannt: 2025-01-27 11:30:00
- Status: EXPOSED

Details siehe gespeicherte Daten in Memory.
```

---

## 🛠️ Erweiterte Konfiguration

### Memory-Limits anpassen:

```python
from core.memory_store import MemoryStore

# Custom Limits
memory = MemoryStore(
    memory_file="custom_memory.json",
    per_user_limit=500,  # Standard: 100
    global_limit=5000     # Standard: 1000
)
```

### Alte Daten bereinigen:

```python
import datetime

memory = get_memory_store()
cutoff_date = datetime.datetime.now() - datetime.timedelta(days=90)

for entry in memory.get_all_emails():
    last_updated = entry.get('last_updated')
    if last_updated and datetime.datetime.fromisoformat(last_updated) < cutoff_date:
        memory.forget_email(entry['value'])
        print(f"Removed old data for: {entry['value']}")
```

---

## ❓ FAQ

**Q: Werden die Daten automatisch aktualisiert?**
A: Nein, nur wenn Sie eine E-Mail erneut scannen.

**Q: Kann ich die Speicherung deaktivieren?**
A: Ja, kommentieren Sie die Zeilen in `agent.py` aus (Zeile 1805-1813).

**Q: Wie groß wird die Memory-Datei?**
A: Pro E-Mail ca. 1-2 KB. Bei 1000 E-Mails ca. 1-2 MB.

**Q: Kann ich Breach-Daten exportieren?**
A: Ja, `data/memory.json` ist eine normale JSON-Datei.

---

## 🎓 Zusammenfassung

**Was Sie wissen müssen:**
1. ✅ Breach-Daten werden automatisch bei jedem Scan gespeichert
2. ✅ Daten sind persistent in `data/memory.json`
3. ✅ Können jederzeit abgerufen werden
4. ✅ Formatierte Reports verfügbar
5. ✅ Status-Indikatoren zeigen Gefahr an

**Vorteil:**
- Keine erneuten API-Calls nötig
- Historische Daten verfügbar
- Schneller Überblick über alle E-Mails

---

**Letzte Aktualisierung:** 2025-01-27
