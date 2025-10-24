"""Social Media Intelligence Module for OSINT.

Provides:
- Social media profile discovery
- Username enumeration
- Account validation
- Profile information extraction
- Cross-platform correlation
- Social graph analysis
- Sentiment and activity monitoring
"""

import re
import logging
from typing import Dict, List, Optional, Any
import asyncio
import aiohttp
from urllib.parse import urljoin, quote
import time

logger = logging.getLogger("crawllama")

# Common social media platforms and their profile URL patterns
SOCIAL_PLATFORMS = {
    'twitter': {
        'url_pattern': 'https://twitter.com/{username}',
        'api_check': 'https://api.twitter.com/1.1/users/show.json?screen_name={username}',
        'indicators': ['twitter.com', '@'],
        'username_pattern': r'^[A-Za-z0-9_]{1,15}$'
    },
    'instagram': {
        'url_pattern': 'https://instagram.com/{username}',
        'api_check': 'https://www.instagram.com/{username}/?__a=1',
        'indicators': ['instagram.com', 'ig:', 'insta:'],
        'username_pattern': r'^[A-Za-z0-9_.]{1,30}$'
    },
    'linkedin': {
        'url_pattern': 'https://linkedin.com/in/{username}',
        'api_check': 'https://www.linkedin.com/in/{username}',
        'indicators': ['linkedin.com', 'li:'],
        'username_pattern': r'^[A-Za-z0-9\-]{3,100}$'
    },
    'facebook': {
        'url_pattern': 'https://facebook.com/{username}',
        'api_check': 'https://www.facebook.com/{username}',
        'indicators': ['facebook.com', 'fb:'],
        'username_pattern': r'^[A-Za-z0-9.]{5,50}$'
    },
    'github': {
        'url_pattern': 'https://github.com/{username}',
        'api_check': 'https://api.github.com/users/{username}',
        'indicators': ['github.com', 'gh:'],
        'username_pattern': r'^[A-Za-z0-9\-]{1,39}$'
    },
    'reddit': {
        'url_pattern': 'https://reddit.com/u/{username}',
        'api_check': 'https://www.reddit.com/user/{username}/about.json',
        'indicators': ['reddit.com', 'u/', '/u/'],
        'username_pattern': r'^[A-Za-z0-9_\-]{3,20}$'
    },
    'youtube': {
        'url_pattern': 'https://youtube.com/c/{username}',
        'api_check': 'https://www.youtube.com/c/{username}',
        'indicators': ['youtube.com', 'yt:'],
        'username_pattern': r'^[A-Za-z0-9_\-]{1,100}$'
    },
    'tiktok': {
        'url_pattern': 'https://tiktok.com/@{username}',
        'api_check': 'https://www.tiktok.com/@{username}',
        'indicators': ['tiktok.com', 'tt:', '@'],
        'username_pattern': r'^[A-Za-z0-9_.]{1,24}$'
    }
}

# Common username variations
USERNAME_VARIATIONS = [
    '{username}',
    '{username}_{year}',
    '{username}{year}',
    '{username}_official',
    '{username}.official',
    'official_{username}',
    '{username}_real',
    'real_{username}',
    '{username}123',
    '{username}_1',
]


class SocialIntelligence:
    """Social Media OSINT capabilities."""

    def __init__(self):
        """Initialize social intelligence."""
        self.platforms = SOCIAL_PLATFORMS
        self.session_timeout = 10
        logger.info("Social Intelligence initialized")

    async def analyze_username(self, username: str, platforms: Optional[List[str]] = None) -> Dict:
        """
        Comprehensive username analysis across social platforms.

        Args:
            username: Username to analyze
            platforms: List of platforms to check (default: all)

        Returns:
            Dictionary with analysis results:
            {
                'username': str,
                'platforms_found': List[Dict],
                'platforms_not_found': List[str],
                'variations': List[Dict],
                'summary': Dict
            }
        """
        logger.info(f"Starting social analysis for username: {username}")
        
        if platforms is None:
            platforms = list(self.platforms.keys())
        
        results = {
            'username': username,
            'platforms_found': [],
            'platforms_not_found': [],
            'variations': [],
            'summary': {
                'total_platforms_checked': len(platforms),
                'platforms_with_presence': 0,
                'confidence_score': 0.0,
                'risk_indicators': []
            }
        }

        # Check username validity for each platform
        for platform in platforms:
            if platform not in self.platforms:
                logger.warning(f"Unknown platform: {platform}")
                continue
                
            platform_data = self.platforms[platform]
            is_valid = self._validate_username_format(username, platform_data['username_pattern'])
            
            if is_valid:
                profile_data = await self._check_platform_presence(username, platform)
                if profile_data['exists']:
                    results['platforms_found'].append(profile_data)
                    results['summary']['platforms_with_presence'] += 1
                else:
                    results['platforms_not_found'].append(platform)
            else:
                results['platforms_not_found'].append(platform)
                logger.debug(f"Username {username} invalid for {platform}")

        # Check common variations if original username not found on major platforms
        if results['summary']['platforms_with_presence'] < 3:
            variations = await self._check_username_variations(username, platforms[:5])  # Check top 5 platforms
            results['variations'] = variations

        # Calculate confidence score
        total_checked = results['summary']['total_platforms_checked']
        found = results['summary']['platforms_with_presence']
        results['summary']['confidence_score'] = (found / total_checked) * 100 if total_checked > 0 else 0

        # Risk assessment
        results['summary']['risk_indicators'] = self._assess_risk_indicators(results)

        logger.info(f"Social analysis completed for {username}: {found}/{total_checked} platforms")
        return results

    async def discover_profiles_by_email(self, email: str) -> Dict:
        """
        Discover social media profiles associated with an email address.

        Args:
            email: Email address to search

        Returns:
            Dictionary with discovered profiles
        """
        logger.info(f"Starting profile discovery for email: {email}")
        
        username = email.split('@')[0]  # Extract username part
        domain = email.split('@')[1] if '@' in email else ''
        
        results = {
            'email': email,
            'extracted_username': username,
            'domain': domain,
            'direct_matches': [],
            'username_matches': [],
            'domain_analysis': {}
        }

        # Check if email username exists on social platforms
        username_results = await self.analyze_username(username)
        results['username_matches'] = username_results['platforms_found']

        # Domain analysis for corporate/organization profiles
        if domain and domain not in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']:
            domain_analysis = await self._analyze_domain_social_presence(domain)
            results['domain_analysis'] = domain_analysis

        return results

    async def monitor_social_activity(self, username: str, platforms: List[str]) -> Dict:
        """
        Monitor social media activity and sentiment for a username.

        Args:
            username: Username to monitor
            platforms: Platforms to monitor

        Returns:
            Dictionary with activity analysis
        """
        logger.info(f"Starting activity monitoring for: {username}")
        
        results = {
            'username': username,
            'monitoring_timestamp': time.time(),
            'platforms': {},
            'overall_sentiment': 'neutral',
            'activity_level': 'unknown',
            'recent_posts': []
        }

        for platform in platforms:
            if platform in self.platforms:
                activity_data = await self._get_platform_activity(username, platform)
                results['platforms'][platform] = activity_data

        # Analyze overall activity and sentiment
        results['overall_sentiment'] = self._calculate_overall_sentiment(results['platforms'])
        results['activity_level'] = self._calculate_activity_level(results['platforms'])

        return results

    def _validate_username_format(self, username: str, pattern: str) -> bool:
        """Validate username format against platform-specific pattern."""
        try:
            return bool(re.match(pattern, username))
        except re.error:
            logger.error(f"Invalid regex pattern: {pattern}")
            return False

    async def _check_platform_presence(self, username: str, platform: str) -> Dict:
        """Check if username exists on a specific platform."""
        platform_data = self.platforms[platform]
        profile_url = platform_data['url_pattern'].format(username=username)
        
        result = {
            'platform': platform,
            'username': username,
            'url': profile_url,
            'exists': False,
            'profile_data': {},
            'last_checked': time.time(),
            'error': None
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.session_timeout)) as session:
                async with session.get(profile_url, allow_redirects=False) as response:
                    if response.status == 200:
                        result['exists'] = True
                        # Extract basic profile information if possible
                        content = await response.text()
                        result['profile_data'] = self._extract_profile_data(content, platform)
                    elif response.status == 404:
                        result['exists'] = False
                    else:
                        result['exists'] = False
                        result['error'] = f"HTTP {response.status}"
                        
        except asyncio.TimeoutError:
            result['error'] = "Timeout"
            logger.warning(f"Timeout checking {platform} for {username}")
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Error checking {platform} for {username}: {e}")

        return result

    async def _check_username_variations(self, base_username: str, platforms: List[str]) -> List[Dict]:
        """Check common username variations across platforms."""
        variations_found = []
        current_year = str(time.localtime().tm_year)
        
        for variation_template in USERNAME_VARIATIONS[:5]:  # Check top 5 variations
            variation = variation_template.format(username=base_username, year=current_year)
            
            if variation != base_username:  # Skip if it's the same as original
                variation_results = await self.analyze_username(variation, platforms[:3])  # Check top 3 platforms
                if variation_results['summary']['platforms_with_presence'] > 0:
                    variations_found.append({
                        'variation': variation,
                        'template': variation_template,
                        'platforms_found': variation_results['platforms_found']
                    })

        return variations_found

    async def _analyze_domain_social_presence(self, domain: str) -> Dict:
        """Analyze corporate social media presence based on domain."""
        domain_name = domain.replace('.com', '').replace('.org', '').replace('.net', '')
        
        results = {
            'domain': domain,
            'corporate_accounts': [],
            'official_presence': False
        }

        # Check for official corporate accounts
        corporate_usernames = [domain_name, f"official{domain_name}", f"{domain_name}official"]
        
        for username in corporate_usernames:
            username_results = await self.analyze_username(username, ['twitter', 'linkedin', 'facebook'])
            if username_results['summary']['platforms_with_presence'] > 0:
                results['corporate_accounts'].extend(username_results['platforms_found'])
                results['official_presence'] = True

        return results

    async def _get_platform_activity(self, username: str, platform: str) -> Dict:
        """Get recent activity data for a platform (placeholder for API integration)."""
        # This would integrate with actual social media APIs
        return {
            'platform': platform,
            'username': username,
            'last_post': None,
            'post_frequency': 'unknown',
            'follower_count': None,
            'sentiment': 'neutral',
            'activity_score': 0
        }

    def _extract_profile_data(self, content: str, platform: str) -> Dict:
        """Extract basic profile information from HTML content."""
        # Basic extraction - would be enhanced with platform-specific parsers
        profile_data = {
            'display_name': None,
            'bio': None,
            'follower_count': None,
            'verified': False
        }

        # Simple extraction patterns (would be expanded)
        if 'verified' in content.lower() or 'checkmark' in content.lower():
            profile_data['verified'] = True

        return profile_data

    def _calculate_overall_sentiment(self, platforms_data: Dict) -> str:
        """Calculate overall sentiment from platform data."""
        # Placeholder for sentiment analysis
        return 'neutral'

    def _calculate_activity_level(self, platforms_data: Dict) -> str:
        """Calculate overall activity level from platform data."""
        # Placeholder for activity analysis
        return 'moderate'

    def _assess_risk_indicators(self, analysis_results: Dict) -> List[str]:
        """Assess potential risk indicators from social analysis."""
        risk_indicators = []
        
        found_count = analysis_results['summary']['platforms_with_presence']
        
        if found_count == 0:
            risk_indicators.append("No social media presence found")
        elif found_count > 7:
            risk_indicators.append("Extensive social media presence")
        
        # Check for suspicious patterns in variations
        if len(analysis_results['variations']) > 3:
            risk_indicators.append("Multiple username variations found")

        return risk_indicators

    def generate_social_report(self, analysis_results: Dict) -> str:
        """Generate a human-readable social intelligence report."""
        username = analysis_results['username']
        found_count = analysis_results['summary']['platforms_with_presence']
        total_count = analysis_results['summary']['total_platforms_checked']
        confidence = analysis_results['summary']['confidence_score']
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║                 SOCIAL MEDIA INTELLIGENCE REPORT            ║
╚══════════════════════════════════════════════════════════════╝

Target Username: {username}
Analysis Date: {time.strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY:
├─ Platforms Found: {found_count}/{total_count}
├─ Confidence Score: {confidence:.1f}%
└─ Risk Level: {'HIGH' if len(analysis_results['summary']['risk_indicators']) > 2 else 'MEDIUM' if len(analysis_results['summary']['risk_indicators']) > 0 else 'LOW'}

PLATFORMS WITH PRESENCE:
"""
        
        for platform_data in analysis_results['platforms_found']:
            report += f"├─ {platform_data['platform'].upper()}: {platform_data['url']}\n"
            if platform_data['profile_data'].get('verified'):
                report += f"│  └─ VERIFIED ACCOUNT ✓\n"
        
        if analysis_results['variations']:
            report += f"\nUSERNAME VARIATIONS FOUND:\n"
            for variation in analysis_results['variations']:
                report += f"├─ {variation['variation']}: {len(variation['platforms_found'])} platform(s)\n"
        
        if analysis_results['summary']['risk_indicators']:
            report += f"\nRISK INDICATORS:\n"
            for indicator in analysis_results['summary']['risk_indicators']:
                report += f"⚠️  {indicator}\n"
        
        return report