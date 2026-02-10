"""Optional LinkedIn API Intelligence Module.

Provides LinkedIn profile lookup via the linkedin-api package.
This module is OPTIONAL - if linkedin-api is not installed, all functions
gracefully return empty results and the system falls back to web scraping.

IMPORTANT - Terms of Service:
    Using the LinkedIn API library may violate LinkedIn's Terms of Service.
    This module is provided for authorized security research, threat intelligence,
    and compliance/due diligence purposes ONLY. Users are responsible for
    ensuring their use complies with applicable laws and LinkedIn's ToS.

Installation:
    pip install linkedin-api==2.3.1 lxml==5.3.0

Configuration (environment variables):
    LINKEDIN_EMAIL    - LinkedIn account email
    LINKEDIN_PASSWORD - LinkedIn account password

Security Warning:
    Never commit LinkedIn credentials to version control.
    Use environment variables or a .env file (already in .gitignore).
"""

import os
import logging
from typing import Dict, Optional

logger = logging.getLogger("crawllama")

# Try to import linkedin-api; set availability flag
LINKEDIN_API_AVAILABLE = False
try:
    from linkedin_api import Linkedin
    LINKEDIN_API_AVAILABLE = True
    logger.debug("linkedin-api package available")
except ImportError:
    logger.debug("linkedin-api not installed - LinkedIn API features disabled (web scraping will be used)")


def is_available() -> bool:
    """Check if LinkedIn API is available (package installed)."""
    return LINKEDIN_API_AVAILABLE


def has_credentials() -> bool:
    """Check if LinkedIn credentials are configured."""
    return bool(os.environ.get("LINKEDIN_EMAIL") and os.environ.get("LINKEDIN_PASSWORD"))


def is_ready() -> bool:
    """Check if LinkedIn API is both available and configured."""
    return is_available() and has_credentials()


def _get_client() -> Optional[object]:
    """Create and return an authenticated LinkedIn API client.

    Returns None if the package is not installed or credentials are missing.
    """
    if not is_ready():
        return None

    try:
        client = Linkedin(
            os.environ["LINKEDIN_EMAIL"],
            os.environ["LINKEDIN_PASSWORD"],
        )
        return client
    except Exception as e:
        logger.warning(f"Failed to authenticate with LinkedIn API: {e}")
        return None


def get_profile(username: str) -> Dict:
    """Fetch a LinkedIn profile by public identifier (slug).

    Args:
        username: LinkedIn public profile slug (e.g. 'john-doe-123abc').

    Returns:
        Dictionary with profile data, or empty dict on failure.
        Keys may include: firstName, lastName, headline, locationName,
        industryName, summary, geoLocationName, etc.
    """
    if not is_ready():
        if not is_available():
            logger.debug("LinkedIn API not available - install linkedin-api to enable")
        elif not has_credentials():
            logger.debug("LinkedIn credentials not set - set LINKEDIN_EMAIL and LINKEDIN_PASSWORD")
        return {}

    try:
        client = _get_client()
        if client is None:
            return {}

        profile = client.get_profile(username)
        if not profile:
            return {}

        # Extract relevant fields into a normalized structure
        return {
            'display_name': f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip(),
            'title': profile.get('headline', ''),
            'location': profile.get('geoLocationName', '') or profile.get('locationName', ''),
            'industry': profile.get('industryName', ''),
            'bio': profile.get('summary', ''),
            'connections': profile.get('connections', None),
            'source': 'linkedin_api',
        }

    except Exception as e:
        logger.warning(f"LinkedIn API profile lookup failed for '{username}': {e}")
        return {}


def search_people(keywords: str, limit: int = 5) -> list:
    """Search LinkedIn for people matching keywords.

    Args:
        keywords: Search query string.
        limit: Maximum number of results to return.

    Returns:
        List of dicts with basic profile info, or empty list on failure.
    """
    if not is_ready():
        return []

    try:
        client = _get_client()
        if client is None:
            return []

        results = client.search_people(keywords=keywords, limit=limit)
        return [
            {
                'name': r.get('name', ''),
                'headline': r.get('jobtitle', ''),
                'location': r.get('location', ''),
                'public_id': r.get('public_id', ''),
            }
            for r in (results or [])
        ]

    except Exception as e:
        logger.warning(f"LinkedIn API people search failed for '{keywords}': {e}")
        return []
