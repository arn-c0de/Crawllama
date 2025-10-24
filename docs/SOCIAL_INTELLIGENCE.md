# Social Media Intelligence (OSINT)

## Überblick

Das Social Intelligence Modul erweitert CrawlLamas OSINT-Fähigkeiten um umfassende Social Media Analyse und Überwachung.

## Features

### 1. Username-Analyse
- **Plattform-übergreifende Suche**: Überprüfung von Benutzernamen auf 8+ Social Media Plattformen
- **Format-Validierung**: Automatische Validierung von Benutzernamen gegen plattformspezifische Regeln  
- **Variationen-Suche**: Erkennung häufiger Username-Varianten (z.B. username2024, username_official)
- **Confidence-Score**: Bewertung der Wahrscheinlichkeit einer Identitätsübereinstimmung

### 2. E-Mail-basierte Profil-Entdeckung
- **Username-Extraktion**: Automatische Extraktion potentieller Benutzernamen aus E-Mail-Adressen
- **Domain-Analyse**: Suche nach Corporate Social Media Accounts basierend auf E-Mail-Domain
- **Cross-Referenz**: Verknüpfung von E-Mail-Adressen mit Social Media Profilen

### 3. Aktivitäts-Monitoring
- **Sentiment-Analyse**: Bewertung der Tonalität von Social Media Aktivitäten
- **Aktivitätslevel**: Messung der Posting-Frequenz und Engagement
- **Zeitreihenanalyse**: Überwachung von Verhaltensmustern über Zeit

### 4. Risk Assessment
- **Anomalie-Erkennung**: Identifikation ungewöhnlicher Muster (z.B. zu viele/wenige Profile)
- **Fake Account Detection**: Hinweise auf potentielle Fake-Accounts
- **Privacy Scoring**: Bewertung der Datenschutz-Einstellungen

## Unterstützte Plattformen

| Plattform | Status | API-Integration | Username Pattern |
|-----------|--------|----------------|------------------|
| Twitter   | ✅      | Optional       | 1-15 Zeichen, A-Z, 0-9, _ |
| Instagram | ✅      | Optional       | 1-30 Zeichen, A-Z, 0-9, _, . |
| LinkedIn  | ✅      | Optional       | 3-100 Zeichen, A-Z, 0-9, - |
| Facebook  | ✅      | Optional       | 5-50 Zeichen, A-Z, 0-9, . |
| GitHub    | ✅      | ✅             | 1-39 Zeichen, A-Z, 0-9, - |
| Reddit    | ✅      | ✅             | 3-20 Zeichen, A-Z, 0-9, _, - |
| YouTube   | ✅      | Optional       | 1-100 Zeichen, A-Z, 0-9, _, - |
| TikTok    | ✅      | Optional       | 1-24 Zeichen, A-Z, 0-9, _, . |

## Verwendung

### Basic Username Analysis

```python
from core.osint.social_intel import SocialIntelligence

async def analyze_user():
    social = SocialIntelligence()
    
    # Analysiere einen Benutzernamen
    results = await social.analyze_username(
        username="john_doe",
        platforms=["twitter", "instagram", "github"]
    )
    
    print(f"Gefunden auf {results['summary']['platforms_with_presence']} Plattformen")
    
    # Generiere Report
    report = social.generate_social_report(results)
    print(report)
```

### E-Mail-basierte Suche

```python
async def search_by_email():
    social = SocialIntelligence()
    
    # Entdecke Profile basierend auf E-Mail
    results = await social.discover_profiles_by_email("john.doe@company.com")
    
    print(f"Username-Matches: {len(results['username_matches'])}")
    for match in results['username_matches']:
        print(f"  - {match['platform']}: {match['url']}")
```

### Aktivitäts-Monitoring

```python
async def monitor_activity():
    social = SocialIntelligence()
    
    # Überwache Social Media Aktivität
    activity = await social.monitor_social_activity(
        username="target_user",
        platforms=["twitter", "instagram"]
    )
    
    print(f"Aktivitätslevel: {activity['activity_level']}")
    print(f"Sentiment: {activity['overall_sentiment']}")
```

## CLI Integration

Das Social Intelligence Modul ist in die CrawlLama CLI integriert:

```bash
# Username analysieren
python main.py --osint --social-username "john_doe"

# E-Mail-basierte Suche
python main.py --osint --social-email "john@example.com"

# Aktivitäts-Monitoring
python main.py --osint --social-monitor "target_user" --platforms twitter,instagram
```

## API-Konfiguration (Optional)

Für erweiterte Features können API-Keys konfiguriert werden:

```json
{
  "social_apis": {
    "twitter": {
      "api_key": "your_twitter_api_key",
      "api_secret": "your_twitter_api_secret",
      "access_token": "your_access_token",
      "access_secret": "your_access_secret"
    },
    "instagram": {
      "access_token": "your_instagram_token"
    }
  }
}
```

## Datenschutz & Compliance

⚖️ **Wichtige Hinweise zur legalen Nutzung:**

- ✅ **Erlaubt**: Sicherheitsforschung, Threat Intelligence, Investigativer Journalismus
- ❌ **Verboten**: Stalking, Harassment, illegale Überwachung
- 📝 **Logging**: Alle OSINT-Operationen werden für Compliance-Zwecke protokolliert
- 🔒 **Datenschutz**: Respektierung von DSGVO, CCPA und lokalen Datenschutzgesetzen

## Output-Formate

### JSON-Struktur

```json
{
  "username": "john_doe",
  "platforms_found": [
    {
      "platform": "github",
      "username": "john_doe", 
      "url": "https://github.com/john_doe",
      "exists": true,
      "profile_data": {
        "display_name": "John Doe",
        "verified": false,
        "follower_count": 150
      },
      "last_checked": 1698765432.0
    }
  ],
  "summary": {
    "total_platforms_checked": 8,
    "platforms_with_presence": 3,
    "confidence_score": 37.5,
    "risk_indicators": ["Multiple username variations found"]
  }
}
```

### Report-Format

```
╔══════════════════════════════════════════════════════════════╗
║                 SOCIAL MEDIA INTELLIGENCE REPORT            ║
╚══════════════════════════════════════════════════════════════╝

Target Username: john_doe
Analysis Date: 2025-10-24 15:30:45

SUMMARY:
├─ Platforms Found: 3/8
├─ Confidence Score: 37.5%
└─ Risk Level: LOW

PLATFORMS WITH PRESENCE:
├─ GITHUB: https://github.com/john_doe
├─ TWITTER: https://twitter.com/john_doe
└─ LINKEDIN: https://linkedin.com/in/john_doe

USERNAME VARIATIONS FOUND:
├─ john_doe_2024: 2 platform(s)
└─ john_doe_official: 1 platform(s)
```

## Performance & Limits

- **Concurrent Requests**: Maximal 5 parallele Plattform-Checks
- **Rate Limiting**: Automatische Berücksichtigung von API-Limits
- **Timeout**: 10 Sekunden pro Plattform-Check
- **Caching**: Ergebnisse werden für 1 Stunde gecacht
- **Batch Processing**: Unterstützung für Bulk-Analysen

## Testing

```bash
# Social Intelligence Tests ausführen
python tests/test_social_intel.py

# Unit Tests
pytest tests/test_social_intel.py -v

# Coverage Report
pytest tests/test_social_intel.py --cov=core.osint.social_intel
```

## Troubleshooting

### Häufige Probleme

1. **Timeout Errors**: 
   - Lösung: Erhöhe `session_timeout` in der Konfiguration
   - Standard: 10 Sekunden

2. **Rate Limiting**:
   - Lösung: Implementiere längere Pausen zwischen Requests
   - API-Keys verwenden für höhere Limits

3. **False Positives**:
   - Lösung: Verwende strengere Validierungsmuster
   - Cross-Reference mit mehreren Indikatoren

### Debug-Modus

```python
import logging
logging.getLogger("crawllama").setLevel(logging.DEBUG)
```

## Roadmap

### Geplante Features (v1.3+)

- **Graph-basierte Analyse**: Visualisierung von Social Media Verbindungen
- **ML-basierte Klassifizierung**: Automatische Kategorisierung von Accounts
- **Real-time Monitoring**: Live-Überwachung von Social Media Aktivitäten
- **Deepfake Detection**: Erkennung manipulierter Profilbilder
- **Behavioral Analysis**: Erkennung von Bot-Accounts und koordinierten Kampagnen

### API-Erweiterungen

- **Facebook Graph API**: Erweiterte Facebook-Analyse
- **Instagram Basic Display**: Offizielle Instagram-Integration  
- **TikTok Research API**: TikTok-Datenanalyse
- **Telegram Bot API**: Telegram-Channel-Monitoring