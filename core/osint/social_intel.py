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

import json
import logging
import re
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import aiohttp
from bs4 import BeautifulSoup

from core.osint._common import DEFAULT_BROWSER_HEADERS, DEFAULT_USER_AGENTS, run_async
from utils import tor_mode

# Optional LinkedIn API integration (graceful fallback to web scraping)
try:
    from core.osint import linkedin_api_intel
    _LINKEDIN_API_MODULE = True
except ImportError:
    _LINKEDIN_API_MODULE = False

logger = logging.getLogger("crawllama")

# Extended social media platforms with multiple check URLs
SOCIAL_PLATFORMS = {
    'twitter': {
        'url_pattern': 'https://twitter.com/{username}',
        'check_urls': [
            'https://twitter.com/{username}',
            'https://x.com/{username}',
            'https://nitter.net/{username}'
        ],
        'indicators': ['twitter.com', 'x.com', '@'],
        'username_pattern': r'^[A-Za-z0-9_]{1,15}$',
        'extract_patterns': {
            'display_name': r'<title>([^(]+)\(@[^)]+\)',
            'followers': r'(\d+(?:,\d+)*)\s+Followers',
            'bio': r'<meta name="description" content="([^"]*)"'
        }
    },
    'instagram': {
        'url_pattern': 'https://instagram.com/{username}',
        'check_urls': [
            'https://instagram.com/{username}',
            'https://www.instagram.com/{username}',
            'https://picuki.com/profile/{username}',
            'https://imginn.com/{username}'
        ],
        'indicators': ['instagram.com', 'ig:', 'insta:'],
        'username_pattern': r'^[A-Za-z0-9_.]{1,30}$',
        'extract_patterns': {
            'display_name': r'"full_name":"([^"]*)"',
            'followers': r'"edge_followed_by":{"count":(\d+)',
            'bio': r'"biography":"([^"]*)"',
            'verified': r'"is_verified":true'
        }
    },
    'linkedin': {
        'url_pattern': 'https://linkedin.com/in/{username}',
        'check_urls': [
            'https://linkedin.com/in/{username}',
            'https://www.linkedin.com/in/{username}',
            'https://de.linkedin.com/in/{username}'
        ],
        'indicators': ['linkedin.com', 'li:'],
        'username_pattern': r'^[A-Za-z0-9\-]{3,100}$',
        'extract_patterns': {
            'display_name': r'<title>([^|]+) \|',
            'title': r'"headline":"([^"]*)"',
            'location': r'"geoLocationName":"([^"]*)"'
        }
    },
    'facebook': {
        'url_pattern': 'https://facebook.com/{username}',
        'check_urls': [
            'https://facebook.com/{username}',
            'https://www.facebook.com/{username}',
            'https://m.facebook.com/{username}'
        ],
        'indicators': ['facebook.com', 'fb:'],
        'username_pattern': r'^[A-Za-z0-9.]{5,50}$',
        'extract_patterns': {
            'display_name': r'<title>([^|]+)</title>',
            'about': r'"about":"([^"]*)"'
        }
    },
    'github': {
        'url_pattern': 'https://github.com/{username}',
        'check_urls': [
            'https://github.com/{username}',
            'https://api.github.com/users/{username}'
        ],
        'indicators': ['github.com', 'gh:'],
        'username_pattern': r'^[A-Za-z0-9\-]{1,39}$',
        'extract_patterns': {
            'display_name': r'"name":"([^"]*)"',
            'bio': r'"bio":"([^"]*)"',
            'location': r'"location":"([^"]*)"',
            'followers': r'"followers":(\d+)',
            'repos': r'"public_repos":(\d+)'
        }
    },
    'reddit': {
        'url_pattern': 'https://reddit.com/u/{username}',
        'check_urls': [
            'https://reddit.com/u/{username}',
            'https://www.reddit.com/user/{username}',
            'https://old.reddit.com/user/{username}'
        ],
        'indicators': ['reddit.com', 'u/', '/u/'],
        'username_pattern': r'^[A-Za-z0-9_\-]{3,20}$',
        'extract_patterns': {
            'karma': r'"total_karma":(\d+)',
            'created': r'"created_utc":(\d+)',
            'verified': r'"is_gold":true'
        }
    },
    'youtube': {
        'url_pattern': 'https://youtube.com/c/{username}',
        'check_urls': [
            'https://youtube.com/c/{username}',
            'https://youtube.com/@{username}',
            'https://www.youtube.com/c/{username}',
            'https://www.youtube.com/@{username}'
        ],
        'indicators': ['youtube.com', 'yt:'],
        'username_pattern': r'^[A-Za-z0-9_\-]{1,100}$',
        'extract_patterns': {
            'display_name': r'"title":"([^"]*)"',
            'subscribers': r'"subscriberCountText".*?"simpleText":"([^"]*)"',
            'videos': r'"videoCountText".*?"simpleText":"([^"]*)"'
        }
    },
    'tiktok': {
        'url_pattern': 'https://tiktok.com/@{username}',
        'check_urls': [
            'https://tiktok.com/@{username}',
            'https://www.tiktok.com/@{username}'
        ],
        'indicators': ['tiktok.com', 'tt:', '@'],
        'username_pattern': r'^[A-Za-z0-9_.]{1,24}$',
        'extract_patterns': {
            'display_name': r'"nickname":"([^"]*)"',
            'followers': r'"followerCount":(\d+)',
            'bio': r'"signature":"([^"]*)"'
        }
    },
    'twitch': {
        'url_pattern': 'https://twitch.tv/{username}',
        'check_urls': [
            'https://twitch.tv/{username}',
            'https://www.twitch.tv/{username}'
        ],
        'indicators': ['twitch.tv'],
        'username_pattern': r'^[A-Za-z0-9_]{4,25}$',
        'extract_patterns': {
            'display_name': r'"displayName":"([^"]*)"',
            'followers': r'"followers":{"totalCount":(\d+)'
        }
    },
    'telegram': {
        'url_pattern': 'https://t.me/{username}',
        'check_urls': [
            'https://t.me/{username}',
            'https://telegram.me/{username}'
        ],
        'indicators': ['t.me', 'telegram.me'],
        'username_pattern': r'^[A-Za-z0-9_]{5,32}$',
        'extract_patterns': {
            'display_name': r'<div class="tgme_page_title"[^>]*>([^<]+)',
            'description': r'<div class="tgme_page_description"[^>]*>([^<]+)'
        }
    },
    'discord': {
        'url_pattern': 'https://discord.com/users/{username}',
        'check_urls': [
            'https://discord.com/users/{username}',
            'https://discordapp.com/users/{username}'
        ],
        'indicators': ['discord.com', 'discordapp.com'],
        'username_pattern': r'^[A-Za-z0-9_]{2,32}$',
        'extract_patterns': {}
    },
    'pinterest': {
        'url_pattern': 'https://pinterest.com/{username}',
        'check_urls': [
            'https://pinterest.com/{username}',
            'https://www.pinterest.com/{username}',
            'https://de.pinterest.com/{username}'
        ],
        'indicators': ['pinterest.com'],
        'username_pattern': r'^[A-Za-z0-9_]{3,30}$',
        'extract_patterns': {
            'display_name': r'"fullName":"([^"]*)"',
            'followers': r'"followerCount":(\d+)'
        }
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
        self.session_timeout = 15
        self.user_agents = DEFAULT_USER_AGENTS
        self.headers = dict(DEFAULT_BROWSER_HEADERS)  # copy: instances may extend it
        # robots.txt cache: robots_url -> (fetched_at, parser or None on failure)
        self._robots_cache: dict[str, tuple[float, RobotFileParser | None]] = {}
        self._robots_cache_ttl = 3600  # seconds
        # Check LinkedIn API availability
        self.linkedin_api_ready = (
            _LINKEDIN_API_MODULE
            and linkedin_api_intel.is_ready()
        )
        if self.linkedin_api_ready:
            logger.info("Social Intelligence initialized with LinkedIn API + web scraping")
        elif _LINKEDIN_API_MODULE and linkedin_api_intel.is_available():
            logger.info("Social Intelligence initialized (LinkedIn API installed but credentials not set, using web scraping)")
        else:
            logger.info("Social Intelligence initialized with web scraping (install linkedin-api for API features)")

    async def analyze_username(self, username: str, platforms: list[str] | None = None) -> dict:
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

    async def discover_profiles_by_email(self, email: str) -> dict:
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

    async def monitor_social_activity(self, username: str, platforms: list[str]) -> dict:
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

    async def _check_platform_presence(self, username: str, platform: str) -> dict:
        """Check if username exists on a specific platform using multiple methods."""
        platform_data = self.platforms[platform]
        check_urls = platform_data.get('check_urls', [platform_data['url_pattern']])
        result = self._new_presence_result(username, platform, platform_data)

        # For LinkedIn, try API first if available
        if platform == 'linkedin' and self.linkedin_api_ready:
            if self._try_linkedin_api(username, result):
                return result

        # Try multiple URLs and methods for better detection. One session per
        # platform check: connections (and, in Tor mode, the SOCKS handshake)
        # are reused across all probe URLs instead of paid per URL.
        async with aiohttp.ClientSession(
            connector=tor_mode.aiohttp_connector(),
            timeout=aiohttp.ClientTimeout(total=self.session_timeout),
        ) as session:
            for i, url_template in enumerate(check_urls):
                check_url = url_template.format(username=username)
                method_name = f"method_{i+1}_{urlparse(check_url).netloc}"
                result['methods_tried'].append(method_name)

                if await self._probe_profile_url(session, check_url, i, method_name, platform, result):
                    break

        # If no method worked, try alternative detection methods
        if not result['exists']:
            alternative_result = await self._try_alternative_detection(username, platform)
            if alternative_result['exists']:
                result.update(alternative_result)

        return result

    @staticmethod
    def _new_presence_result(username: str, platform: str, platform_data: dict) -> dict:
        """Build the initial presence-check result dictionary."""
        return {
            'platform': platform,
            'username': username,
            'url': platform_data['url_pattern'].format(username=username),
            'exists': False,
            'profile_data': {},
            'last_checked': time.time(),
            'error': None,
            'methods_tried': [],
            'success_method': None
        }

    def _try_linkedin_api(self, username: str, result: dict) -> bool:
        """Look up a LinkedIn profile via the API; update result and report success."""
        result['methods_tried'].append('linkedin_api')
        try:
            profile = linkedin_api_intel.get_profile(username)
            if not profile:
                return False

            result['exists'] = True
            result['success_method'] = 'linkedin_api'
            result['profile_data'] = {
                'display_name': profile.get('display_name'),
                'bio': profile.get('bio'),
                'location': profile.get('location'),
                'verified': False,
                'follower_count': profile.get('connections'),
                'raw_data': {'source': 'linkedin_api', 'title': profile.get('title', '')},
            }
            return True
        except Exception as e:
            logger.debug(f"LinkedIn API lookup failed for {username}, falling back to web scraping: {e}")
            return False

    async def _probe_profile_url(
        self,
        session: aiohttp.ClientSession,
        check_url: str,
        attempt_index: int,
        method_name: str,
        platform: str,
        result: dict,
    ) -> bool:
        """Probe a single profile URL; update result and report whether it exists."""
        try:
            # Check robots.txt first for ethical scraping
            if not await self._check_robots_permission(session, check_url):
                # Robots.txt blocked - use debug level instead of info
                logger.debug(f"Robots.txt disallows access to {check_url}")
                result['methods_tried'][-1] += "_robots_blocked"
                return False

            # Rotate the User-Agent per attempt (per request, not per session)
            headers = self.headers.copy()
            headers['User-Agent'] = self.user_agents[attempt_index % len(self.user_agents)]

            # Try HEAD request first (faster)
            async with session.head(check_url, headers=headers, allow_redirects=True) as response:
                if response.status != 200:
                    return False  # Try next URL

                result['exists'] = True
                result['success_method'] = method_name

            # Get full content for data extraction
            async with session.get(check_url, headers=headers, allow_redirects=True) as get_response:
                if get_response.status == 200:
                    content = await get_response.text()
                    result['profile_data'] = self._extract_profile_data(content, platform)
            return True

        except TimeoutError:
            logger.warning(f"Timeout checking {check_url}")
            return False
        except Exception as e:
            logger.debug(f"Error with {check_url}: {e}")
            return False

    async def _check_username_variations(self, base_username: str, platforms: list[str]) -> list[dict]:
        """Check common username variations across platforms (non-recursive)."""
        variations_found = []
        current_year = str(time.localtime().tm_year)
        
        for variation_template in USERNAME_VARIATIONS[:5]:  # Check top 5 variations
            variation = variation_template.format(username=base_username, year=current_year)
            
            if variation != base_username:  # Skip if it's the same as original
                # Check variation directly on platforms WITHOUT calling analyze_username (prevents recursion)
                for platform in platforms[:3]:  # Check top 3 platforms only
                    if platform not in self.platforms:
                        continue
                    
                    platform_data = self.platforms[platform]
                    is_valid = self._validate_username_format(variation, platform_data['username_pattern'])
                    
                    if is_valid:
                        profile_data = await self._check_platform_presence(variation, platform)
                        if profile_data['exists']:
                            variations_found.append({
                                'variation': variation,
                                'template': variation_template,
                                'platform': platform,
                                'profile_data': profile_data
                            })

        return variations_found

    async def _analyze_domain_social_presence(self, domain: str) -> dict:
        """Analyze corporate social media presence based on domain."""
        domain_name = domain.replace('.com', '').replace('.org', '').replace('.net', '').replace('.de', '').replace('.co.uk', '')
        
        results = {
            'domain': domain,
            'corporate_accounts': [],
            'official_presence': False
        }

        # Check for official corporate accounts (directly, no recursion)
        corporate_usernames = [domain_name, f"official{domain_name}", f"{domain_name}official"]
        
        for username in corporate_usernames[:2]:  # Limit to 2 variations
            # Direct platform check without calling analyze_username
            for platform in ['twitter', 'linkedin', 'facebook']:
                if platform not in self.platforms:
                    continue
                
                platform_data = self.platforms[platform]
                is_valid = self._validate_username_format(username, platform_data['username_pattern'])
                
                if is_valid:
                    profile_data = await self._check_platform_presence(username, platform)
                    if profile_data['exists']:
                        results['corporate_accounts'].append(profile_data)
                        results['official_presence'] = True

        return results

    async def _get_platform_activity(self, username: str, platform: str) -> dict:
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

    def _extract_profile_data(self, content: str, platform: str) -> dict:
        """Extract detailed profile information from HTML content."""
        platform_data = self.platforms.get(platform, {})
        extract_patterns = platform_data.get('extract_patterns', {})
        
        profile_data = {
            'display_name': None,
            'bio': None,
            'follower_count': None,
            'following_count': None,
            'post_count': None,
            'verified': False,
            'location': None,
            'website': None,
            'join_date': None,
            'raw_data': {}
        }

        try:
            # Use BeautifulSoup for better HTML parsing
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract using platform-specific patterns
            for field, pattern in extract_patterns.items():
                matches = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if matches:
                    if field in ['followers', 'following', 'posts', 'repos', 'karma']:
                        # Convert numeric fields
                        try:
                            profile_data[f"{field.replace('followers', 'follower_count').replace('following', 'following_count').replace('posts', 'post_count')}"] = int(matches.group(1).replace(',', ''))
                        except Exception:
                            profile_data['raw_data'][field] = matches.group(1)
                    elif field == 'verified':
                        profile_data['verified'] = True
                    else:
                        profile_data[field] = matches.group(1).strip()

            # Generic extraction fallbacks
            if not profile_data['display_name']:
                # Try title tag
                title = soup.find('title')
                if title:
                    profile_data['display_name'] = self._clean_title(title.get_text())

            # Look for meta description
            if not profile_data['bio']:
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    profile_data['bio'] = meta_desc.get('content', '')[:200]

            # Extract additional metadata
            profile_data['raw_data'].update(self._extract_metadata(soup, platform))

            # Generic verification indicators
            if not profile_data['verified']:
                verified_indicators = ['verified', 'checkmark', 'badge', '✓', '✔', 'official']
                for indicator in verified_indicators:
                    if indicator.lower() in content.lower():
                        profile_data['verified'] = True
                        break

        except Exception as e:
            logger.error(f"Error extracting profile data for {platform}: {e}")

        return profile_data

    def _calculate_overall_sentiment(self, platforms_data: dict) -> str:
        """Calculate overall sentiment from platform data."""
        # Placeholder for sentiment analysis
        return 'neutral'

    def _calculate_activity_level(self, platforms_data: dict) -> str:
        """Calculate overall activity level from platform data."""
        # Placeholder for activity analysis
        return 'moderate'

    def _assess_risk_indicators(self, analysis_results: dict) -> list[str]:
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

    async def _check_robots_permission(self, session: aiohttp.ClientSession, url: str) -> bool:
        """Check if robots.txt allows access to the URL (cached per host)."""
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"

            parser = await self._get_robots_parser(session, robots_url)
            if parser is None:
                return True  # No readable robots.txt: default to allowed
            return parser.can_fetch(self.user_agents[0], url)

        except Exception as e:
            logger.debug(f"Robots.txt check failed for {url}: {e}")
            return True  # Default to allowed if check fails

    async def _get_robots_parser(self, session: aiohttp.ClientSession, robots_url: str) -> RobotFileParser | None:
        """Fetch and cache the parsed robots.txt for a host (None = unavailable).

        Fetched via aiohttp instead of RobotFileParser.read() (urllib): urllib
        cannot speak SOCKS, so it would bypass or break Tor mode. Failures are
        cached too, so an unreachable host is not re-fetched for every probe.
        """
        cached = self._robots_cache.get(robots_url)
        if cached and time.time() - cached[0] < self._robots_cache_ttl:
            return cached[1]

        parser: RobotFileParser | None = None
        try:
            async with session.get(robots_url, headers={'User-Agent': self.user_agents[0]}) as response:
                if response.status == 200:
                    parser = RobotFileParser()
                    parser.parse((await response.text()).splitlines())
        except Exception as e:
            logger.debug(f"robots.txt fetch failed for {robots_url}: {e}")

        self._robots_cache[robots_url] = (time.time(), parser)
        return parser

    async def _try_alternative_detection(self, username: str, platform: str) -> dict:
        """Try alternative detection methods for username existence."""
        result = {
            'platform': platform,
            'username': username,
            'exists': False,
            'profile_data': {},
            'method': 'alternative_search'
        }

        try:
            # LinkedIn API as alternative detection for LinkedIn platform
            if platform == 'linkedin' and self.linkedin_api_ready:
                profile = linkedin_api_intel.get_profile(username)
                if profile:
                    result['exists'] = True
                    result['method'] = 'linkedin_api_alternative'
                    result['profile_data'] = {
                        'display_name': profile.get('display_name'),
                        'bio': profile.get('bio'),
                        'location': profile.get('location'),
                        'verified': False,
                        'raw_data': {'source': 'linkedin_api'},
                    }
                    return result

            logger.debug(f"Alternative detection attempted for {username} on {platform}")

        except Exception as e:
            logger.error(f"Alternative detection error: {e}")

        return result

    def _clean_title(self, title: str) -> str:
        """Clean and extract username from page title."""
        # Remove common suffixes/prefixes
        title = title.strip()
        
        # Remove platform names
        for platform_name in ['Twitter', 'Instagram', 'LinkedIn', 'Facebook', 'GitHub', 'YouTube']:
            title = title.replace(f" - {platform_name}", "")
            title = title.replace(f" | {platform_name}", "")
            title = title.replace(f" ({platform_name})", "")
        
        # Extract name before (@username) pattern
        match = re.match(r'^([^(@]+)', title)
        if match:
            return match.group(1).strip()
            
        return title[:50]  # Limit length

    def _extract_metadata(self, soup: BeautifulSoup, platform: str) -> dict:
        """Extract additional metadata from HTML soup."""
        metadata = {}
        
        try:
            # Extract Open Graph data
            og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))
            for tag in og_tags:
                property_name = tag.get('property', '').replace('og:', '')
                content = tag.get('content', '')
                if content:
                    metadata[f"og_{property_name}"] = content

            # Extract Twitter Card data
            twitter_tags = soup.find_all('meta', attrs={'name': lambda x: x and x.startswith('twitter:')})
            for tag in twitter_tags:
                name = tag.get('name', '').replace('twitter:', '')
                content = tag.get('content', '')
                if content:
                    metadata[f"twitter_{name}"] = content

            # Look for JSON-LD structured data
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        metadata['structured_data'] = data
                        break
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue

        except Exception as e:
            logger.debug(f"Metadata extraction error: {e}")
            
        return metadata

    def search_username_across_platforms(self, username: str) -> dict:
        """Synchronous wrapper for username search across all platforms."""
        return run_async(self.analyze_username(username))

    def generate_social_report(self, analysis_results: dict) -> str:
        """Generate a comprehensive human-readable social intelligence report."""
        username = analysis_results['username']
        found_count = analysis_results['summary']['platforms_with_presence']
        total_count = analysis_results['summary']['total_platforms_checked']
        confidence = analysis_results['summary']['confidence_score']
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║                 SOCIAL MEDIA INTELLIGENCE REPORT            ║
╚══════════════════════════════════════════════════════════════╝

🎯 Target Username: {username}
📅 Analysis Date: {time.strftime('%Y-%m-%d %H:%M:%S')}
🔍 Analysis Depth: {'LinkedIn API + Web Scraping' if self.linkedin_api_ready else 'Enhanced Free Scraping (No API Keys Required)'}

📊 SUMMARY:
├─ Platforms Found: {found_count}/{total_count}
├─ Confidence Score: {confidence:.1f}%
├─ Detection Methods: Multiple URL checking, HTML parsing, metadata extraction
└─ Risk Level: {'🔴 HIGH' if len(analysis_results['summary']['risk_indicators']) > 2 else '🟡 MEDIUM' if len(analysis_results['summary']['risk_indicators']) > 0 else '🟢 LOW'}

🌐 PLATFORMS WITH PRESENCE:
"""
        
        for platform_data in analysis_results['platforms_found']:
            platform_name = platform_data['platform'].upper()
            url = platform_data['url']
            profile = platform_data.get('profile_data', {})
            
            report += f"├─ {platform_name}: {url}\n"
            
            if profile.get('verified'):
                report += "│  ├─ ✅ VERIFIED ACCOUNT\n"
            if profile.get('display_name'):
                report += f"│  ├─ 👤 Name: {profile['display_name']}\n"
            if profile.get('bio'):
                bio = profile['bio'][:80] + "..." if len(profile['bio']) > 80 else profile['bio']
                report += f"│  ├─ 📝 Bio: {bio}\n"
            if profile.get('follower_count'):
                report += f"│  ├─ 👥 Followers: {profile['follower_count']:,}\n"
            if profile.get('location'):
                report += f"│  ├─ 📍 Location: {profile['location']}\n"
            if platform_data.get('success_method'):
                report += f"│  └─ 🔧 Detection Method: {platform_data['success_method']}\n"
            else:
                report += f"│  └─ 🔧 Methods Tried: {len(platform_data.get('methods_tried', []))}\n"
        
        if analysis_results.get('variations'):
            report += "\n🔄 USERNAME VARIATIONS FOUND:\n"
            for variation in analysis_results['variations']:
                report += f"├─ {variation['variation']}: {len(variation['platforms_found'])} platform(s)\n"
                for platform in variation['platforms_found']:
                    report += f"│  └─ {platform['platform']}: {platform['url']}\n"
        
        if analysis_results['summary'].get('risk_indicators'):
            report += "\n⚠️  RISK INDICATORS:\n"
            for indicator in analysis_results['summary']['risk_indicators']:
                report += f"├─ {indicator}\n"
        
        # Add technical details
        report += "\n🔧 TECHNICAL DETAILS:\n"
        total_methods = sum(len(p.get('methods_tried', [])) for p in analysis_results['platforms_found'])
        report += f"├─ Total Detection Attempts: {total_methods}\n"
        report += "├─ Robots.txt Compliance: ✅ Checked\n"
        report += "├─ User-Agent Rotation: ✅ Enabled\n"
        report += "├─ HTML Parsing: ✅ BeautifulSoup + Regex\n"
        report += "├─ Metadata Extraction: ✅ OpenGraph + Twitter Cards\n"
        report += "└─ Alternative URLs: ✅ Multiple endpoints per platform\n"
        
        report += "\n💡 RECOMMENDATIONS:\n"
        if found_count == 0:
            report += "├─ Consider checking username variations or typos\n"
            report += f"├─ Try searching with quotes: \"{username}\"\n"
        elif found_count > 7:
            report += "├─ High social media presence detected\n"
            report += "├─ Consider cross-referencing profile information\n"
        
        report += "└─ Use OSINT tools for deeper investigation\n"
        
        return report