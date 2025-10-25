# OSINT v1.4.1 - Nutzungsanleitung

## Neue OSINT-Module in v1.4.1

Der Agent hat jetzt Zugriff auf **11 spezialisierte OSINT-Module**:

### ✅ Basis-Module (bereits vorhanden)
1. **OSINTQueryParser** - Parst OSINT-Operatoren
2. **EmailIntelligence** - E-Mail-Analyse
3. **PhoneIntelligence** - Telefonnummer-Analyse
4. **QueryEnhancer** - KI-gestützte Query-Optimierung
5. **OSINTCompliance** - Compliance & Rate-Limiting

### 🆕 Neue Module (v1.4.1)
6. **LinkedInIntelligence** - LinkedIn Profile & Firmen
7. **TwitterIntelligence** - Twitter/X Profile & Aktivitäten
8. **GitHubIntelligence** - GitHub User & Repositories
9. **IPIntelligence** - IP-Adressen-Analyse
10. **DomainIntelligence** - Domain-Whois & DNS
11. **SocialIntelligence** - Social Media Aggregation

---

## 📖 Nutzung im Agent

### 1. LinkedIn Intelligence

**Beispiel-Queries:**
```
https://linkedin.com/in/max-mustermann
Analysiere https://linkedin.com/company/microsoft
site:linkedin.com/in Data Scientist Berlin
```

**Was macht der Agent?**
- Erkennt LinkedIn-URLs automatisch
- Analysiert Profile (Skills, Experience, Education)
- Analysiert Firmen (Employees, Industry, Growth)
- Nutzt Proxycurl API (falls konfiguriert) oder Fallback-Scraping

**Konfiguration (optional):**
```json
{
  "osint": {
    "proxycurl_api_key": "YOUR_API_KEY"
  }
}
```

---

### 2. Twitter Intelligence

**Beispiel-Queries:**
```
@elonmusk
Analysiere @github
twitter.com/username
```

**Was macht der Agent?**
- Erkennt Twitter-Handles (@username)
- Analysiert User-Profile (Followers, Tweets, Bio)
- Sentiment-Analyse von Tweets
- Nutzt Twitter API v2 (falls konfiguriert)

**Konfiguration (optional):**
```json
{
  "osint": {
    "twitter_bearer_token": "YOUR_BEARER_TOKEN"
  }
}
```

---

### 3. GitHub Intelligence

**Beispiel-Queries:**
```
github.com/torvalds
https://github.com/microsoft/vscode
Analysiere github.com/username/repo
```

**Was macht der Agent?**
- Analysiert GitHub-User (Repos, Followers, Activity)
- Analysiert Repositories (Stars, Forks, Issues, Contributors)
- Code-Sprachen und Technologien
- Nutzt GitHub API (falls konfiguriert) oder öffentliche Daten

**Konfiguration (optional):**
```json
{
  "osint": {
    "github_token": "YOUR_GITHUB_TOKEN"
  }
}
```

---

### 4. IP Intelligence

**Beispiel-Queries:**
```
8.8.8.8
Analysiere IP 1.1.1.1
Woher kommt 185.199.108.153?
```

**Was macht der Agent?**
- Geolocation (Land, Stadt, Koordinaten)
- ISP & Organization
- ASN (Autonomous System Number)
- Reputation & Blacklist-Check
- Nutzt ipinfo.io oder ip-api.com

---

### 5. Domain Intelligence

**Beispiel-Queries:**
```
example.com
Whois google.com
Wem gehört github.com?
```

**Was macht der Agent?**
- Whois-Daten (Registrar, Creation Date, Expiration)
- DNS-Records (A, MX, TXT, NS)
- Subdomain-Discovery
- SSL/TLS-Certificate-Info
- Reputation & Blacklist-Check

---

## 🔧 Erweiterte Nutzung

### Kombinierte Queries

```
email:john@example.com site:linkedin.com
@username github.com/username
8.8.8.8 domain:google.com
```

### OSINT-Operatoren (bestehend)

```
email:max@example.com         # E-Mail-Analyse
phone:+49123456789            # Telefon-Analyse
site:linkedin.com keyword     # Site-spezifische Suche
inurl:profile site:twitter.com # URL-Filter
intitle:CEO site:linkedin.com  # Title-Filter
filetype:pdf site:github.com   # Dateityp-Filter
```

---

## ⚙️ Konfiguration

Füge in `config.json` hinzu:

```json
{
  "osint": {
    "enabled": true,
    "max_results": 25,
    "safesearch": "strict",
    "proxycurl_api_key": "YOUR_PROXYCURL_KEY",
    "twitter_bearer_token": "YOUR_TWITTER_TOKEN",
    "github_token": "YOUR_GITHUB_TOKEN",
    "ipinfo_api_key": "YOUR_IPINFO_KEY"
  }
}
```

**API-Keys (optional):**
- Ohne API-Keys: Fallback auf öffentliche Daten / Scraping
- Mit API-Keys: Erweiterte Features & höhere Limits

---

## 🚀 Beispiel-Workflow

**Schritt 1: LinkedIn-Suche**
```
User: site:linkedin.com/in Data Scientist Berlin
Agent: [Zeigt 10 Profile mit Nummern [1]-[10]]
```

**Schritt 2: Profil-Details**
```
User: quelle 1
Agent: [Lädt Profil und analysiert mit LinkedInIntelligence]
- Name: Max Mustermann
- Position: Senior Data Scientist
- Skills: Python, ML, TensorFlow
- Experience: 5 Jahre bei Microsoft
```

**Schritt 3: Weitere Analyse**
```
User: Zeige GitHub von Max Mustermann
Agent: [Sucht github.com/maxmustermann]
- Public Repos: 42
- Stars: 1.2k
- Top Languages: Python (60%), JavaScript (30%)
```

---

## 📊 Features-Übersicht

| Modul | Queries | API Required | Fallback |
|-------|---------|--------------|----------|
| Email | `email:...` | ❌ | ✅ DNS/Validation |
| Phone | `phone:...` | ❌ | ✅ Format/Country |
| LinkedIn | URLs, `site:linkedin.com` | ⚠️ Optional | ✅ Scraping |
| Twitter | `@username` | ⚠️ Optional | ✅ Public Data |
| GitHub | `github.com/...` | ⚠️ Optional | ✅ Public API |
| IP | IP-Adressen | ⚠️ Optional | ✅ Free APIs |
| Domain | Domains | ❌ | ✅ Whois/DNS |

---

## 🔒 Compliance & Limits

- **Rate Limits:** 50 Email/Phone pro Stunde, 100 General OSINT
- **Logging:** Alle OSINT-Queries werden geloggt
- **Terms:** Terms müssen akzeptiert werden (beim ersten Start)
- **GDPR:** Respektiert Privacy-Laws (keine PII-Speicherung)

---

## 💡 Best Practices

1. **Kombiniere Module:** Email → LinkedIn → GitHub → Domain
2. **Nutze Quellen-Referenzen:** `quelle 1`, `quelle 2, 3, 5`
3. **Spezifische Queries:** Präzise Suchbegriffe statt breite Anfragen
4. **API-Keys:** Für beste Ergebnisse API-Keys konfigurieren
5. **Compliance:** Nur für legitime, legale Zwecke nutzen

---

## 🐛 Troubleshooting

**Problem:** "OSINT features sind nicht verfügbar"
- **Lösung:** Prüfe, ob alle Module in `core/osint/` vorhanden sind

**Problem:** "API error: 401"
- **Lösung:** API-Key in `config.json` überprüfen

**Problem:** "Rate limit exceeded"
- **Lösung:** Warte 1 Stunde oder nutze andere Module

**Problem:** "LinkedIn-Analyse fehlgeschlagen"
- **Lösung:** Proxycurl API-Key konfigurieren oder Fallback nutzen

---

## 📚 Weitere Dokumentation

- [OSINT_USAGE.md](OSINT_USAGE.md) - Basis-Anleitung
- [OSINT_CONTEXT_USAGE.md](OSINT_CONTEXT_USAGE.md) - Kontext-Integration
- [SOCIAL_INTELLIGENCE.md](SOCIAL_INTELLIGENCE.md) - Social Media Features
- [README.md](../../core/osint/README.md) - OSINT-Modul-Übersicht

---

**Version:** 1.4.1  
**Letzte Aktualisierung:** 26. Oktober 2025
