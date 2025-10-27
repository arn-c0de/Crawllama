# Social Media Intelligence (OSINT)

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🔍 OSINT Guide](OSINT_USAGE.md) | [🎯 Context Usage](OSINT_CONTEXT_USAGE.md) | [🏥 Health](../health/HEALTH_MONITORING.md)

---

## Overview

The Social Intelligence module extends CrawlLama's OSINT capabilities with comprehensive social media analysis and monitoring.

## Features

### 1. Username Analysis
- **Cross-platform Search**: Verification of usernames across 8+ social media platforms
- **Format Validation**: Automatic validation of usernames against platform-specific rules
- **Variation Search**: Detection of common username variants (e.g., username2024, username_official)
- **Confidence Score**: Assessment of identity match probability (0.0-1.0 scale)

### 2. Email-based Profile Discovery
- **Username Extraction**: Automatic extraction of potential usernames from email addresses
- **Domain Analysis**: Search for corporate social media accounts based on email domain
- **Cross-Reference**: Linking email addresses with social media profiles

### 3. Activity Monitoring
- **Sentiment Analysis**: Assessment of social media activity tone
- **Activity Level**: Measurement of posting frequency and engagement
- **Time Series Analysis**: Monitoring behavioral patterns over time

### 4. Risk Assessment
- **Anomaly Detection**: Identification of unusual patterns (e.g., too many/few profiles)
- **Fake Account Detection**: Indicators of potential fake accounts
- **Privacy Scoring**: Assessment of privacy settings

## Supported Platforms

| Platform | Status | API Integration | Username Pattern |
|-----------|--------|----------------|------------------|
| Twitter   | ✅      | Optional       | 1-15 characters, A-Z, 0-9, _ |
| Instagram | ✅      | Optional       | 1-30 characters, A-Z, 0-9, _, . |
| LinkedIn  | ✅      | Optional       | 3-100 characters, A-Z, 0-9, - |
| Facebook  | ✅      | Optional       | 5-50 characters, A-Z, 0-9, . |
| GitHub    | ✅      | ✅             | 1-39 characters, A-Z, 0-9, - |
| Reddit    | ✅      | ✅             | 3-20 characters, A-Z, 0-9, _, - |
| YouTube   | ✅      | Optional       | 1-100 characters, A-Z, 0-9, _, - |
| TikTok    | ✅      | Optional       | 1-24 characters, A-Z, 0-9, _, . |

## Usage

### Basic Username Analysis

```python
from core.osint.social_intel import SocialIntelligence

async def analyze_user():
    social = SocialIntelligence()

    # Analyze a username
    results = await social.analyze_username(
        username="john_doe",
        platforms=["twitter", "instagram", "github"]
    )

    print(f"Found on {results['summary']['platforms_with_presence']} platforms")

    # Generate report
    report = social.generate_social_report(results)
    print(report)
```

### Email-based Search

```python
async def search_by_email():
    social = SocialIntelligence()

    # Discover profiles based on email
    results = await social.discover_profiles_by_email("john.doe@company.com")

    print(f"Username matches: {len(results['username_matches'])}")
    for match in results['username_matches']:
        print(f"  - {match['platform']}: {match['url']}")
```

### Activity Monitoring

```python
async def monitor_activity():
    social = SocialIntelligence()

    # Monitor social media activity
    activity = await social.monitor_social_activity(
        username="target_user",
        platforms=["twitter", "instagram"]
    )

    print(f"Activity level: {activity['activity_level']}")
    print(f"Sentiment: {activity['overall_sentiment']}")
```

## CLI Integration

The Social Intelligence module is integrated into the CrawlLama CLI:

```bash
# Analyze username
python main.py --osint --social-username "john_doe"

# Email-based search
python main.py --osint --social-email "john@example.com"

# Activity monitoring
python main.py --osint --social-monitor "target_user" --platforms twitter,instagram
```

## API Configuration (Optional)

For advanced features, API keys can be configured:

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

## Privacy & Compliance

⚖️ **Important Notes on Legal Use:**

- ✅ **Allowed**: Security research, threat intelligence, investigative journalism
- ❌ **Prohibited**: Stalking, harassment, illegal surveillance
- 📝 **Logging**: All OSINT operations are logged for compliance purposes
- 🔒 **Privacy**: Respect for GDPR, CCPA, and local privacy laws

## Output Formats

### JSON Structure

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
    "confidence_score": 0.375,
    "risk_indicators": ["Multiple username variations found"]
  }
}
```

### Report Format

```
╔══════════════════════════════════════════════════════════════╗
║                 SOCIAL MEDIA INTELLIGENCE REPORT            ║
╚══════════════════════════════════════════════════════════════╝

Target Username: john_doe
Analysis Date: 2025-10-24 15:30:45

SUMMARY:
├─ Platforms Found: 3/8
├─ Confidence Score: 0.375 (37.5%)
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

- **Concurrent Requests**: Maximum 5 parallel platform checks
- **Rate Limiting**: Automatic consideration of API limits
- **Timeout**: 10 seconds per platform check
- **Caching**: Results are cached for 1 hour
- **Batch Processing**: Support for bulk analysis

## Testing

```bash
# Run social intelligence tests
python tests/test_social_intel.py

# Unit tests
pytest tests/test_social_intel.py -v

# Coverage report
pytest tests/test_social_intel.py --cov=core.osint.social_intel
```

## Troubleshooting

### Common Issues

1. **Timeout Errors**:
   - Solution: Increase `session_timeout` in configuration
   - Default: 10 seconds

2. **Rate Limiting**:
   - Solution: Implement longer pauses between requests
   - Use API keys for higher limits

3. **False Positives**:
   - Solution: Use stricter validation patterns
   - Cross-reference with multiple indicators

### Debug Mode

```python
import logging
logging.getLogger("crawllama").setLevel(logging.DEBUG)
```

## Roadmap

### Planned Features (v1.5+)

- **Graph-based Analysis**: Visualization of social media connections
- **ML-based Classification**: Automatic categorization of accounts
- **Real-time Monitoring**: Live monitoring of social media activities
- **Deepfake Detection**: Detection of manipulated profile images
- **Behavioral Analysis**: Detection of bot accounts and coordinated campaigns

### API Extensions

- **Facebook Graph API**: Advanced Facebook analysis
- **Instagram Basic Display**: Official Instagram integration
- **TikTok Research API**: TikTok data analysis
- **Telegram Bot API**: Telegram channel monitoring
