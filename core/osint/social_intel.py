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
        'api_check': 'https://twitter.com/{username}',
        'indicators': ['twitter.com', '@'],
        'username_pattern': r'^[A-Za-z0-9_]{1,15}$',
        'check_method': 'html'
    },
    'x': {  # Twitter/X alias
        'url_pattern': 'https://x.com/{username}',
        'api_check': 'https://x.com/{username}',
        'indicators': ['x.com', '@'],
        'username_pattern': r'^[A-Za-z0-9_]{1,15}$',
        'check_method': 'html'
    },
    'instagram': {
        'url_pattern': 'https://instagram.com/{username}',
        'api_check': 'https://www.instagram.com/{username}',
        'indicators': ['instagram.com', 'ig:', 'insta:'],
        'username_pattern': r'^[A-Za-z0-9_.]{1,30}$',
        'check_method': 'html'
    },
    'linkedin': {
        'url_pattern': 'https://linkedin.com/in/{username}',
        'api_check': 'https://www.linkedin.com/in/{username}',
        'indicators': ['linkedin.com', 'li:'],
        'username_pattern': r'^[A-Za-z0-9\-]{3,100}$',
        'check_method': 'html'
    },
    'facebook': {
        'url_pattern': 'https://facebook.com/{username}',
        'api_check': 'https://www.facebook.com/{username}',
        'indicators': ['facebook.com', 'fb:'],
        'username_pattern': r'^[A-Za-z0-9.]{5,50}$',
        'check_method': 'html'
    },
    'github': {
        'url_pattern': 'https://github.com/{username}',
        'api_check': 'https://api.github.com/users/{username}',
        'indicators': ['github.com', 'gh:'],
        'username_pattern': r'^[A-Za-z0-9\-]{1,39}$',
        'check_method': 'api'
    },
    'reddit': {
        'url_pattern': 'https://reddit.com/u/{username}',
        'api_check': 'https://www.reddit.com/user/{username}/about.json',
        'indicators': ['reddit.com', 'u/', '/u/'],
        'username_pattern': r'^[A-Za-z0-9_\-]{3,20}$',
        'check_method': 'api'
    },
    'youtube': {
        'url_pattern': 'https://youtube.com/@{username}',
        'api_check': 'https://www.youtube.com/@{username}',
        'indicators': ['youtube.com', 'yt:'],
        'username_pattern': r'^[A-Za-z0-9_\-]{1,100}$',
        'check_method': 'html'
    },
    'tiktok': {
        'url_pattern': 'https://tiktok.com/@{username}',
        'api_check': 'https://www.tiktok.com/@{username}',
        'indicators': ['tiktok.com', 'tt:', '@'],
        'username_pattern': r'^[A-Za-z0-9_.]{1,24}$',
        'check_method': 'html'
    },
    'twitch': {
        'url_pattern': 'https://twitch.tv/{username}',
        'api_check': 'https://www.twitch.tv/{username}',
        'indicators': ['twitch.tv'],
        'username_pattern': r'^[A-Za-z0-9_]{4,25}$',
        'check_method': 'html'
    },
    'pinterest': {
        'url_pattern': 'https://pinterest.com/{username}',
        'api_check': 'https://www.pinterest.com/{username}',
        'indicators': ['pinterest.com'],
        'username_pattern': r'^[A-Za-z0-9_]{3,30}$',
        'check_method': 'html'
    },
    'snapchat': {
        'url_pattern': 'https://snapchat.com/add/{username}',
        'api_check': 'https://www.snapchat.com/add/{username}',
        'indicators': ['snapchat.com'],
        'username_pattern': r'^[A-Za-z0-9._\-]{1,15}$',
        'check_method': 'html'
    },
    'medium': {
        'url_pattern': 'https://medium.com/@{username}',
        'api_check': 'https://medium.com/@{username}',
        'indicators': ['medium.com'],
        'username_pattern': r'^[A-Za-z0-9_]{1,50}$',
        'check_method': 'html'
    },
    'stackoverflow': {
        'url_pattern': 'https://stackoverflow.com/users/{username}',
        'api_check': 'https://api.stackexchange.com/2.3/users?order=desc&sort=reputation&inname={username}&site=stackoverflow',
        'indicators': ['stackoverflow.com'],
        'username_pattern': r'^.{1,50}$',
        'check_method': 'api'
    },
    'devto': {
        'url_pattern': 'https://dev.to/{username}',
        'api_check': 'https://dev.to/{username}',
        'indicators': ['dev.to'],
        'username_pattern': r'^[A-Za-z0-9_]{1,30}$',
        'check_method': 'html'
    },
    'gitlab': {
        'url_pattern': 'https://gitlab.com/{username}',
        'api_check': 'https://gitlab.com/api/v4/users?username={username}',
        'indicators': ['gitlab.com'],
        'username_pattern': r'^[A-Za-z0-9_\-\.]{1,255}$',
        'check_method': 'api'
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

    async def sherlock_search(self, username: str) -> Dict:
        """
        Sherlock-style username search across all platforms.
        Quick parallel search across all social media platforms.
        
        Args:
            username: Username to search
            
        Returns:
            Dictionary with found platforms
        """
        logger.info(f"Starting Sherlock-style search for: {username}")
        
        results = {
            'username': username,
            'search_timestamp': time.time(),
            'platforms_found': [],
            'platforms_checked': len(self.platforms),
            'success_rate': 0.0,
            'estimated_activity_level': 'unknown'
        }
        
        # Run all checks in parallel for speed
        tasks = []
        for platform in self.platforms.keys():
            # Validate format first
            platform_data = self.platforms[platform]
            if self._validate_username_format(username, platform_data['username_pattern']):
                tasks.append(self._check_platform_presence(username, platform))
        
        # Execute all checks concurrently
        if tasks:
            check_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in check_results:
                if isinstance(result, dict) and result.get('exists'):
                    results['platforms_found'].append(result)
        
        # Calculate success rate
        found_count = len(results['platforms_found'])
        results['success_rate'] = (found_count / results['platforms_checked'] * 100) if results['platforms_checked'] > 0 else 0
        
        # Estimate activity level
        if found_count == 0:
            results['estimated_activity_level'] = 'no_presence'
        elif found_count <= 2:
            results['estimated_activity_level'] = 'low'
        elif found_count <= 5:
            results['estimated_activity_level'] = 'moderate'
        else:
            results['estimated_activity_level'] = 'high'
        
        logger.info(f"Sherlock search completed: found on {found_count}/{results['platforms_checked']} platforms")
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
        check_method = platform_data.get('check_method', 'html')
        
        result = {
            'platform': platform,
            'username': username,
            'url': profile_url,
            'exists': False,
            'profile_data': {},
            'last_checked': time.time(),
            'error': None,
            'status_code': None
        }

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.session_timeout)) as session:
                # Use API check if available
                if check_method == 'api':
                    check_url = platform_data['api_check'].format(username=username)
                else:
                    check_url = profile_url
                
                async with session.get(check_url, headers=headers, allow_redirects=True) as response:
                    result['status_code'] = response.status
                    
                    if response.status == 200:
                        content = await response.text()
                        
                        # Platform-specific detection
                        if check_method == 'api':
                            # For API responses (GitHub, Reddit, etc.)
                            try:
                                import json
                                data = await response.json()
                                
                                if platform == 'github':
                                    result['exists'] = 'login' in data
                                    if result['exists']:
                                        result['profile_data'] = {
                                            'display_name': data.get('name'),
                                            'bio': data.get('bio'),
                                            'follower_count': data.get('followers'),
                                            'public_repos': data.get('public_repos'),
                                            'created_at': data.get('created_at'),
                                            'verified': data.get('site_admin', False)
                                        }
                                elif platform == 'reddit':
                                    result['exists'] = 'data' in data and data['data'].get('name')
                                    if result['exists']:
                                        user_data = data['data']
                                        result['profile_data'] = {
                                            'display_name': user_data.get('name'),
                                            'karma': user_data.get('total_karma'),
                                            'created_at': user_data.get('created_utc'),
                                            'verified': user_data.get('verified', False)
                                        }
                                elif platform == 'stackoverflow':
                                    items = data.get('items', [])
                                    result['exists'] = len(items) > 0
                                    if result['exists']:
                                        result['profile_data'] = {
                                            'display_name': items[0].get('display_name'),
                                            'reputation': items[0].get('reputation'),
                                            'user_id': items[0].get('user_id')
                                        }
                                elif platform == 'gitlab':
                                    result['exists'] = isinstance(data, list) and len(data) > 0
                                    if result['exists']:
                                        result['profile_data'] = {
                                            'display_name': data[0].get('name'),
                                            'username': data[0].get('username'),
                                            'bio': data[0].get('bio')
                                        }
                            except:
                                result['exists'] = False
                        else:
                            # For HTML responses - check for profile indicators
                            result['exists'] = self._detect_profile_existence(content, platform, username)
                            if result['exists']:
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

    def _detect_profile_existence(self, content: str, platform: str, username: str) -> bool:
        """
        Detect if profile exists based on HTML content.
        Uses platform-specific indicators.
        """
        content_lower = content.lower()
        
        # Negative indicators (profile doesn't exist)
        negative_indicators = [
            'page not found',
            '404',
            'this account doesn\'t exist',
            'user not found',
            'sorry, this page isn\'t available',
            'account suspended',
            'profile not available'
        ]
        
        for indicator in negative_indicators:
            if indicator in content_lower:
                return False
        
        # Platform-specific positive indicators
        platform_indicators = {
            'twitter': ['profile', 'tweets', 'following', username.lower()],
            'x': ['profile', 'posts', 'following', username.lower()],
            'instagram': ['posts', 'followers', 'following', username.lower()],
            'linkedin': ['experience', 'education', 'connections', username.lower()],
            'facebook': ['photos', 'friends', 'about', username.lower()],
            'youtube': ['videos', 'subscribers', 'about', username.lower()],
            'tiktok': ['followers', 'likes', 'videos', username.lower()],
            'twitch': ['videos', 'clips', 'followers', username.lower()],
            'pinterest': ['pins', 'boards', 'followers', username.lower()],
            'medium': ['stories', 'followers', 'reading', username.lower()],
            'devto': ['posts', 'tags', 'followers', username.lower()]
        }
        
        if platform in platform_indicators:
            indicators = platform_indicators[platform]
            matches = sum(1 for indicator in indicators if indicator in content_lower)
            # If at least 2 indicators found, profile likely exists
            return matches >= 2
        
        # Default: if username appears in content, profile likely exists
        return username.lower() in content_lower

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
        import re
        
        profile_data = {
            'display_name': None,
            'bio': None,
            'follower_count': None,
            'following_count': None,
            'post_count': None,
            'verified': False,
            'profile_image': None
        }

        # Verified badge detection
        verified_patterns = [
            'verified', 'checkmark', 'badge', 'official',
            'data-verified="true"', 'isVerified":true'
        ]
        profile_data['verified'] = any(pattern in content.lower() for pattern in verified_patterns)
        
        # Extract follower counts (various formats)
        follower_patterns = [
            r'(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)\s*(?:followers|Followers)',
            r'"followerCount["\s:]+(\d+)',
            r'followers["\s:]+(\d+(?:,\d+)*)',
        ]
        
        for pattern in follower_patterns:
            match = re.search(pattern, content)
            if match:
                follower_str = match.group(1)
                try:
                    # Convert K, M, B suffixes
                    if 'K' in follower_str:
                        profile_data['follower_count'] = int(float(follower_str.replace('K', '')) * 1000)
                    elif 'M' in follower_str:
                        profile_data['follower_count'] = int(float(follower_str.replace('M', '')) * 1000000)
                    elif 'B' in follower_str:
                        profile_data['follower_count'] = int(float(follower_str.replace('B', '')) * 1000000000)
                    else:
                        profile_data['follower_count'] = int(follower_str.replace(',', ''))
                    break
                except:
                    pass
        
        # Extract post/video counts
        post_patterns = [
            r'(\d+(?:,\d+)*)\s*(?:posts|videos|tweets)',
            r'"postCount["\s:]+(\d+)',
        ]
        
        for pattern in post_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    profile_data['post_count'] = int(match.group(1).replace(',', ''))
                    break
                except:
                    pass

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