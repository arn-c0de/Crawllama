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
from urllib.parse import urljoin, quote, urlparse
import time
import json
from bs4 import BeautifulSoup
import requests
from urllib.robotparser import RobotFileParser

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
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
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
        """Check if username exists on a specific platform using multiple methods."""
        platform_data = self.platforms[platform]
        check_urls = platform_data.get('check_urls', [platform_data['url_pattern']])

        result = {
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

        # For LinkedIn, try API first if available
        if platform == 'linkedin' and self.linkedin_api_ready:
            result['methods_tried'].append('linkedin_api')
            try:
                profile = linkedin_api_intel.get_profile(username)
                if profile:
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
                    return result
            except Exception as e:
                logger.debug(f"LinkedIn API lookup failed for {username}, falling back to web scraping: {e}")

        # Try multiple URLs and methods for better detection
        for i, url_template in enumerate(check_urls):
            check_url = url_template.format(username=username)
            method_name = f"method_{i+1}_{urlparse(check_url).netloc}"
            result['methods_tried'].append(method_name)
            
            try:
                # Check robots.txt first for ethical scraping
                if await self._check_robots_permission(check_url):
                    
                    # Use different headers for each attempt
                    headers = self.headers.copy()
                    headers['User-Agent'] = self.user_agents[i % len(self.user_agents)]
                    
                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=self.session_timeout),
                        headers=headers
                    ) as session:
                        
                        # Try HEAD request first (faster)
                        async with session.head(check_url, allow_redirects=True) as response:
                            if response.status == 200:
                                result['exists'] = True
                                result['success_method'] = method_name
                                
                                # Get full content for data extraction
                                async with session.get(check_url, allow_redirects=True) as get_response:
                                    if get_response.status == 200:
                                        content = await get_response.text()
                                        result['profile_data'] = self._extract_profile_data(content, platform)
                                break
                            elif response.status == 404:
                                continue  # Try next URL
                            
                else:
                    # Robots.txt blocked - use debug level instead of info
                    logger.debug(f"Robots.txt disallows access to {check_url}")
                    result['methods_tried'][-1] += "_robots_blocked"
                    
            except asyncio.TimeoutError:
                logger.warning(f"Timeout checking {check_url}")
                continue
            except Exception as e:
                logger.debug(f"Error with {check_url}: {e}")
                continue

        # If no method worked, try alternative detection methods
        if not result['exists']:
            alternative_result = await self._try_alternative_detection(username, platform)
            if alternative_result['exists']:
                result.update(alternative_result)

        return result

    async def _check_username_variations(self, base_username: str, platforms: List[str]) -> List[Dict]:
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

    async def _analyze_domain_social_presence(self, domain: str) -> Dict:
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

    async def _check_robots_permission(self, url: str) -> bool:
        """Check if robots.txt allows access to the URL."""
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            # Check if we're allowed to access this URL
            user_agent = self.user_agents[0]  # Use first user agent
            return rp.can_fetch(user_agent, url)
            
        except Exception as e:
            logger.debug(f"Robots.txt check failed for {url}: {e}")
            return True  # Default to allowed if check fails

    async def _try_alternative_detection(self, username: str, platform: str) -> Dict:
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

    def _extract_metadata(self, soup: BeautifulSoup, platform: str) -> Dict:
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

    def search_username_across_platforms(self, username: str) -> Dict:
        """Synchronous wrapper for username search across all platforms."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(self.analyze_username(username))

    def generate_social_report(self, analysis_results: Dict) -> str:
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
                report += f"│  ├─ ✅ VERIFIED ACCOUNT\n"
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
            report += f"\n🔄 USERNAME VARIATIONS FOUND:\n"
            for variation in analysis_results['variations']:
                report += f"├─ {variation['variation']}: {len(variation['platforms_found'])} platform(s)\n"
                for platform in variation['platforms_found']:
                    report += f"│  └─ {platform['platform']}: {platform['url']}\n"
        
        if analysis_results['summary'].get('risk_indicators'):
            report += f"\n⚠️  RISK INDICATORS:\n"
            for indicator in analysis_results['summary']['risk_indicators']:
                report += f"├─ {indicator}\n"
        
        # Add technical details
        report += f"\n🔧 TECHNICAL DETAILS:\n"
        total_methods = sum(len(p.get('methods_tried', [])) for p in analysis_results['platforms_found'])
        report += f"├─ Total Detection Attempts: {total_methods}\n"
        report += f"├─ Robots.txt Compliance: ✅ Checked\n"
        report += f"├─ User-Agent Rotation: ✅ Enabled\n"
        report += f"├─ HTML Parsing: ✅ BeautifulSoup + Regex\n"
        report += f"├─ Metadata Extraction: ✅ OpenGraph + Twitter Cards\n"
        report += f"└─ Alternative URLs: ✅ Multiple endpoints per platform\n"
        
        report += f"\n💡 RECOMMENDATIONS:\n"
        if found_count == 0:
            report += f"├─ Consider checking username variations or typos\n"
            report += f"├─ Try searching with quotes: \"{username}\"\n"
        elif found_count > 7:
            report += f"├─ High social media presence detected\n"
            report += f"├─ Consider cross-referencing profile information\n"
        
        report += f"└─ Use OSINT tools for deeper investigation\n"
        
        return report