"""OSINT (Open Source Intelligence) Module for CrawlLama.

This module provides advanced search operators, email intelligence,
phone number analysis, and AI-powered query enhancement.

⚖️ IMPORTANT - Legal & Ethical Use Only:
- ✅ Security Research
- ✅ Threat Intelligence
- ✅ Investigative Journalism
- ✅ Compliance & Due Diligence
- ✅ Academic Research
- ❌ NO Stalking, Harassment, or Illegal Activities

All OSINT operations are logged for compliance.
"""

from .query_parser import OSINTQueryParser, SearchQuery
from .email_intel import EmailIntelligence
from .phone_intel import PhoneIntelligence
from .query_enhancer import QueryEnhancer
from .compliance import OSINTCompliance
from .social_intel import SocialIntelligence
from .domain_intel import DomainIntelligence
from .ip_intel import IPIntelligence
from .company_intel import CompanyIntelligence
from .sources import BreachManager

__version__ = "1.2.0"
__all__ = [
    "OSINTQueryParser",
    "SearchQuery",
    "EmailIntelligence",
    "PhoneIntelligence",
    "QueryEnhancer",
    "OSINTCompliance",
    "SocialIntelligence",
    "DomainIntelligence",
    "IPIntelligence",
    "CompanyIntelligence",
    "BreachManager"
]

# Terms of Use
OSINT_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════╗
║                    OSINT TERMS OF USE                        ║
╚══════════════════════════════════════════════════════════════╝

By using OSINT features, you agree to:

1. Use OSINT features ONLY for legitimate, legal purposes
2. Respect privacy laws (GDPR, CCPA, local regulations)
3. NO harassment, stalking, or intimidation
4. Comply with rate limits and API terms
5. All actions are logged for audit purposes
6. Violations will result in immediate access suspension

OSINT features are provided for:
✓ Security research and threat intelligence
✓ Investigative journalism
✓ Compliance and due diligence
✓ Academic research
✓ Legal investigations with proper authorization

Type 'accept' to agree to these terms.
"""
