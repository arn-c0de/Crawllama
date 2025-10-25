"""LinkedIn Intelligence Module for OSINT (v1.4.1).

Provides:
- Professional Profile Analysis (Skills, Experience, Education)
- Company Research (Employees, Industry, Growth)
- Network Analysis (Connections, Influence)

API: Proxycurl API (alternative to LinkedIn official API)
Docs: https://nubela.co/proxycurl/
"""

import re
import logging
from typing import Dict, List, Optional, Any
import asyncio
import aiohttp
from datetime import datetime

logger = logging.getLogger("crawllama")


class LinkedInIntelligence:
    """LinkedIn OSINT capabilities."""

    def __init__(self, proxycurl_api_key: Optional[str] = None):
        """
        Initialize LinkedIn intelligence.
        
        Args:
            proxycurl_api_key: Proxycurl API Key (optional)
        """
        self.proxycurl_api_key = proxycurl_api_key
        self.base_url = "https://nubela.co/proxycurl/api/v2"
        self.has_api_access = proxycurl_api_key is not None
        
        logger.info(f"LinkedIn Intelligence initialized (API access: {self.has_api_access})")

    async def analyze_profile(self, profile_url: str) -> Dict:
        """
        Analyze LinkedIn profile.
        
        Args:
            profile_url: LinkedIn profile URL (e.g., https://linkedin.com/in/username)
            
        Returns:
            Dictionary with profile analysis:
            {
                'profile_url': str,
                'full_name': str,
                'headline': str,
                'summary': str,
                'location': str,
                'connections': int,
                'current_company': str,
                'current_position': str,
                'skills': List[str],
                'experience': List[Dict],
                'education': List[Dict],
                'certifications': List[Dict],
                'languages': List[Dict],
                'industry': str,
                'profile_pic': str,
                'confidence': float
            }
        """
        logger.info(f"Analyzing LinkedIn profile: {profile_url}")
        
        results = {
            'profile_url': profile_url,
            'full_name': None,
            'headline': None,
            'summary': None,
            'location': None,
            'connections': 0,
            'current_company': None,
            'current_position': None,
            'skills': [],
            'experience': [],
            'education': [],
            'certifications': [],
            'languages': [],
            'industry': None,
            'profile_pic': None,
            'confidence': 0.0,
            'error': None
        }

        if not self.has_api_access:
            # Fallback to basic scraping
            results = await self._analyze_profile_scraping(profile_url)
        else:
            # Use Proxycurl API
            results = await self._analyze_profile_api(profile_url)

        # Calculate confidence
        results['confidence'] = self._calculate_confidence(results)
        
        logger.info(f"LinkedIn profile analysis complete (confidence: {results['confidence']:.2f})")
        return results

    async def _analyze_profile_api(self, profile_url: str) -> Dict:
        """Analyze profile using Proxycurl API."""
        try:
            headers = {
                'Authorization': f'Bearer {self.proxycurl_api_key}'
            }
            
            url = f"{self.base_url}/linkedin"
            params = {
                'url': profile_url,
                'fallback_to_cache': 'on-error',
                'use_cache': 'if-present'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract current position
                        current_company = None
                        current_position = None
                        experiences = data.get('experiences', [])
                        if experiences:
                            latest = experiences[0]
                            current_company = latest.get('company')
                            current_position = latest.get('title')
                        
                        return {
                            'profile_url': profile_url,
                            'full_name': data.get('full_name'),
                            'headline': data.get('headline'),
                            'summary': data.get('summary'),
                            'location': data.get('city') or data.get('state') or data.get('country'),
                            'connections': data.get('connections', 0),
                            'current_company': current_company,
                            'current_position': current_position,
                            'skills': data.get('skills', []),
                            'experience': self._format_experience(data.get('experiences', [])),
                            'education': self._format_education(data.get('education', [])),
                            'certifications': data.get('certifications', []),
                            'languages': data.get('languages', []),
                            'industry': data.get('industry'),
                            'profile_pic': data.get('profile_pic_url'),
                            'error': None
                        }
                    else:
                        error_msg = f"API error: {response.status}"
                        logger.error(error_msg)
                        return {'profile_url': profile_url, 'error': error_msg}
                        
        except Exception as e:
            logger.error(f"Proxycurl API error: {e}")
            return {'profile_url': profile_url, 'error': str(e)}

    async def _analyze_profile_scraping(self, profile_url: str) -> Dict:
        """Fallback: Basic profile scraping (ethical)."""
        logger.warning("Using fallback scraping method - limited data available")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(profile_url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # Basic extraction from HTML (very limited)
                        return {
                            'profile_url': profile_url,
                            'full_name': self._extract_name(html),
                            'headline': self._extract_headline(html),
                            'summary': None,
                            'location': self._extract_location(html),
                            'connections': self._extract_connections(html),
                            'current_company': None,
                            'current_position': None,
                            'skills': [],
                            'experience': [],
                            'education': [],
                            'certifications': [],
                            'languages': [],
                            'industry': None,
                            'profile_pic': None,
                            'error': None
                        }
                    else:
                        return {'profile_url': profile_url, 'error': f"Profile not found: {response.status}"}
                        
        except Exception as e:
            logger.error(f"LinkedIn scraping error: {e}")
            return {'profile_url': profile_url, 'error': str(e)}

    async def analyze_company(self, company_url: str) -> Dict:
        """
        Analyze LinkedIn company page.
        
        Args:
            company_url: LinkedIn company URL
            
        Returns:
            Dictionary with company analysis:
            {
                'company_url': str,
                'name': str,
                'tagline': str,
                'description': str,
                'website': str,
                'industry': str,
                'company_size': str,
                'headquarters': str,
                'founded': int,
                'employees': int,
                'followers': int,
                'specialties': List[str],
                'confidence': float
            }
        """
        logger.info(f"Analyzing LinkedIn company: {company_url}")
        
        results = {
            'company_url': company_url,
            'name': None,
            'tagline': None,
            'description': None,
            'website': None,
            'industry': None,
            'company_size': None,
            'headquarters': None,
            'founded': None,
            'employees': 0,
            'followers': 0,
            'specialties': [],
            'confidence': 0.0,
            'error': None
        }

        if not self.has_api_access:
            logger.warning("Company analysis requires API access")
            return results

        try:
            headers = {
                'Authorization': f'Bearer {self.proxycurl_api_key}'
            }
            
            url = f"{self.base_url}/linkedin/company"
            params = {
                'url': company_url,
                'use_cache': 'if-present'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        results.update({
                            'name': data.get('name'),
                            'tagline': data.get('tagline'),
                            'description': data.get('description'),
                            'website': data.get('website'),
                            'industry': data.get('industry'),
                            'company_size': data.get('company_size'),
                            'headquarters': data.get('headquarters'),
                            'founded': data.get('founded_year'),
                            'employees': data.get('employee_count', 0),
                            'followers': data.get('follower_count', 0),
                            'specialties': data.get('specialities', []),
                            'error': None
                        })
                    else:
                        results['error'] = f"API error: {response.status}"
                        
        except Exception as e:
            logger.error(f"Company analysis error: {e}")
            results['error'] = str(e)

        results['confidence'] = self._calculate_company_confidence(results)
        return results

    async def search_profiles(self, keywords: str, location: Optional[str] = None, max_results: int = 10) -> List[Dict]:
        """
        Search LinkedIn profiles by keywords.
        
        Args:
            keywords: Search keywords (job title, skills, etc.)
            location: Location filter (optional)
            max_results: Maximum results to return
            
        Returns:
            List of profile summaries
        """
        logger.info(f"Searching LinkedIn profiles: {keywords}")
        
        if not self.has_api_access:
            logger.warning("Profile search requires API access")
            return []

        results = []
        
        try:
            headers = {
                'Authorization': f'Bearer {self.proxycurl_api_key}'
            }
            
            url = f"{self.base_url}/search/person"
            params = {
                'query': keywords,
                'location': location,
                'page_size': min(max_results, 100)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get('results', [])
                        logger.info(f"Found {len(results)} profiles")
                    else:
                        logger.error(f"Search error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Profile search error: {e}")

        return results

    def _format_experience(self, experiences: List[Dict]) -> List[Dict]:
        """Format experience data."""
        formatted = []
        for exp in experiences:
            formatted.append({
                'company': exp.get('company'),
                'title': exp.get('title'),
                'location': exp.get('location'),
                'start_date': exp.get('starts_at'),
                'end_date': exp.get('ends_at'),
                'description': exp.get('description'),
                'duration': self._calculate_duration(exp.get('starts_at'), exp.get('ends_at'))
            })
        return formatted

    def _format_education(self, education: List[Dict]) -> List[Dict]:
        """Format education data."""
        formatted = []
        for edu in education:
            formatted.append({
                'school': edu.get('school'),
                'degree': edu.get('degree_name'),
                'field_of_study': edu.get('field_of_study'),
                'start_date': edu.get('starts_at'),
                'end_date': edu.get('ends_at'),
                'grade': edu.get('grade'),
                'activities': edu.get('activities_and_societies')
            })
        return formatted

    def _calculate_duration(self, start: Optional[Dict], end: Optional[Dict]) -> str:
        """Calculate duration between dates."""
        if not start:
            return "Unknown"
        
        if not end:
            return "Present"
        
        try:
            start_year = start.get('year', 0)
            end_year = end.get('year', 0)
            years = end_year - start_year
            
            if years == 0:
                return "< 1 year"
            elif years == 1:
                return "1 year"
            else:
                return f"{years} years"
        except:
            return "Unknown"

    def _calculate_confidence(self, profile: Dict) -> float:
        """Calculate confidence score."""
        if profile.get('error'):
            return 0.0
        
        confidence = 0.0
        
        if profile.get('full_name'):
            confidence += 0.15
        if profile.get('headline'):
            confidence += 0.15
        if profile.get('summary'):
            confidence += 0.1
        if profile.get('current_company'):
            confidence += 0.15
        if profile.get('skills'):
            confidence += 0.15
        if profile.get('experience'):
            confidence += 0.15
        if profile.get('education'):
            confidence += 0.15
            
        return min(confidence, 1.0)

    def _calculate_company_confidence(self, company: Dict) -> float:
        """Calculate company confidence score."""
        if company.get('error'):
            return 0.0
        
        confidence = 0.0
        
        if company.get('name'):
            confidence += 0.2
        if company.get('description'):
            confidence += 0.2
        if company.get('industry'):
            confidence += 0.2
        if company.get('employees', 0) > 0:
            confidence += 0.2
        if company.get('website'):
            confidence += 0.2
            
        return min(confidence, 1.0)

    def _extract_name(self, html: str) -> Optional[str]:
        """Extract name from HTML."""
        match = re.search(r'<title>([^|]+)\|', html)
        return match.group(1).strip() if match else None

    def _extract_headline(self, html: str) -> Optional[str]:
        """Extract headline from HTML."""
        match = re.search(r'<meta property="og:description" content="([^"]+)"', html)
        return match.group(1) if match else None

    def _extract_location(self, html: str) -> Optional[str]:
        """Extract location from HTML."""
        match = re.search(r'location["\s:]+([^<>"]+)', html, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _extract_connections(self, html: str) -> int:
        """Extract connection count from HTML."""
        try:
            match = re.search(r'(\d+)\+?\s+connections?', html, re.IGNORECASE)
            return int(match.group(1)) if match else 0
        except:
            return 0
