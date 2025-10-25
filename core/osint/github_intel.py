"""GitHub Intelligence Module for OSINT (v1.4.1).

Provides:
- Developer Profile Analysis (Contributions, Languages, Repos)
- Repository Intelligence (Quality, Security, Contributors)
- Code Search & Organization Research

API: GitHub GraphQL API v4
Docs: https://docs.github.com/en/graphql
"""

import re
import logging
from typing import Dict, List, Optional, Any
import asyncio
import aiohttp
from datetime import datetime
import json

logger = logging.getLogger("crawllama")


class GitHubIntelligence:
    """GitHub OSINT capabilities."""

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize GitHub intelligence.
        
        Args:
            github_token: GitHub Personal Access Token (optional)
        """
        self.github_token = github_token
        self.rest_api_url = "https://api.github.com"
        self.graphql_url = "https://api.github.com/graphql"
        self.has_api_access = github_token is not None
        
        logger.info(f"GitHub Intelligence initialized (API access: {self.has_api_access})")

    async def analyze_developer(self, username: str) -> Dict:
        """
        Analyze GitHub developer profile.
        
        Args:
            username: GitHub username
            
        Returns:
            Dictionary with developer analysis:
            {
                'username': str,
                'name': str,
                'bio': str,
                'location': str,
                'email': str,
                'company': str,
                'blog': str,
                'twitter_username': str,
                'public_repos': int,
                'public_gists': int,
                'followers': int,
                'following': int,
                'created_at': str,
                'updated_at': str,
                'contributions_last_year': int,
                'top_languages': List[Dict],
                'popular_repos': List[Dict],
                'commit_patterns': Dict,
                'activity_score': float,
                'confidence': float
            }
        """
        logger.info(f"Analyzing GitHub developer: {username}")
        
        results = {
            'username': username,
            'name': None,
            'bio': None,
            'location': None,
            'email': None,
            'company': None,
            'blog': None,
            'twitter_username': None,
            'public_repos': 0,
            'public_gists': 0,
            'followers': 0,
            'following': 0,
            'created_at': None,
            'updated_at': None,
            'contributions_last_year': 0,
            'top_languages': [],
            'popular_repos': [],
            'commit_patterns': {},
            'activity_score': 0.0,
            'confidence': 0.0,
            'error': None
        }

        # Get basic profile (works without token)
        basic_profile = await self._get_basic_profile(username)
        if basic_profile.get('error'):
            results['error'] = basic_profile['error']
            return results
        
        results.update(basic_profile)

        # Get additional data if API access is available
        if self.has_api_access:
            # Get contributions
            contributions = await self._get_contributions(username)
            results['contributions_last_year'] = contributions
            
            # Get top languages
            languages = await self._get_top_languages(username)
            results['top_languages'] = languages
            
            # Get popular repos
            repos = await self._get_popular_repos(username)
            results['popular_repos'] = repos

        # Calculate activity score
        results['activity_score'] = self._calculate_activity_score(results)
        
        # Calculate confidence
        results['confidence'] = self._calculate_confidence(results)
        
        logger.info(f"GitHub developer analysis complete: {username} (confidence: {results['confidence']:.2f})")
        return results

    async def _get_basic_profile(self, username: str) -> Dict:
        """Get basic profile using REST API (no auth required)."""
        try:
            url = f"{self.rest_api_url}/users/{username}"
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'Crawllama-OSINT'
            }
            
            if self.has_api_access:
                headers['Authorization'] = f'token {self.github_token}'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        return {
                            'username': username,
                            'name': data.get('name'),
                            'bio': data.get('bio'),
                            'location': data.get('location'),
                            'email': data.get('email'),
                            'company': data.get('company'),
                            'blog': data.get('blog'),
                            'twitter_username': data.get('twitter_username'),
                            'public_repos': data.get('public_repos', 0),
                            'public_gists': data.get('public_gists', 0),
                            'followers': data.get('followers', 0),
                            'following': data.get('following', 0),
                            'created_at': data.get('created_at'),
                            'updated_at': data.get('updated_at'),
                            'error': None
                        }
                    elif response.status == 404:
                        return {'username': username, 'error': 'User not found'}
                    else:
                        return {'username': username, 'error': f"API error: {response.status}"}
                        
        except Exception as e:
            logger.error(f"GitHub API error: {e}")
            return {'username': username, 'error': str(e)}

    async def _get_contributions(self, username: str) -> int:
        """Get contribution count for last year."""
        if not self.has_api_access:
            return 0
        
        try:
            query = """
            query($username: String!) {
              user(login: $username) {
                contributionsCollection {
                  contributionCalendar {
                    totalContributions
                  }
                }
              }
            }
            """
            
            headers = {
                'Authorization': f'bearer {self.github_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'query': query,
                'variables': {'username': username}
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.graphql_url, headers=headers, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        contributions = data.get('data', {}).get('user', {}).get('contributionsCollection', {})
                        calendar = contributions.get('contributionCalendar', {})
                        return calendar.get('totalContributions', 0)
                        
        except Exception as e:
            logger.error(f"Contribution fetch error: {e}")
        
        return 0

    async def _get_top_languages(self, username: str) -> List[Dict]:
        """Get top programming languages used."""
        if not self.has_api_access:
            return []
        
        try:
            url = f"{self.rest_api_url}/users/{username}/repos"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            params = {
                'sort': 'updated',
                'per_page': 30
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=10) as response:
                    if response.status == 200:
                        repos = await response.json()
                        
                        # Count languages
                        language_stats = {}
                        for repo in repos:
                            lang = repo.get('language')
                            if lang:
                                language_stats[lang] = language_stats.get(lang, 0) + 1
                        
                        # Sort by count
                        sorted_langs = sorted(language_stats.items(), key=lambda x: x[1], reverse=True)
                        
                        return [
                            {'language': lang, 'repo_count': count}
                            for lang, count in sorted_langs[:5]
                        ]
                        
        except Exception as e:
            logger.error(f"Language fetch error: {e}")
        
        return []

    async def _get_popular_repos(self, username: str, limit: int = 5) -> List[Dict]:
        """Get user's most popular repositories."""
        try:
            url = f"{self.rest_api_url}/users/{username}/repos"
            headers = {
                'Accept': 'application/vnd.github.v3+json'
            }
            
            if self.has_api_access:
                headers['Authorization'] = f'token {self.github_token}'
            
            params = {
                'sort': 'stars',
                'per_page': limit
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=10) as response:
                    if response.status == 200:
                        repos = await response.json()
                        
                        return [
                            {
                                'name': repo.get('name'),
                                'description': repo.get('description'),
                                'language': repo.get('language'),
                                'stars': repo.get('stargazers_count', 0),
                                'forks': repo.get('forks_count', 0),
                                'url': repo.get('html_url'),
                                'created_at': repo.get('created_at'),
                                'updated_at': repo.get('updated_at')
                            }
                            for repo in repos
                        ]
                        
        except Exception as e:
            logger.error(f"Repository fetch error: {e}")
        
        return []

    async def analyze_repository(self, owner: str, repo: str) -> Dict:
        """
        Analyze GitHub repository.
        
        Args:
            owner: Repository owner username
            repo: Repository name
            
        Returns:
            Dictionary with repository analysis:
            {
                'owner': str,
                'name': str,
                'description': str,
                'language': str,
                'stars': int,
                'forks': int,
                'watchers': int,
                'open_issues': int,
                'license': str,
                'topics': List[str],
                'created_at': str,
                'updated_at': str,
                'pushed_at': str,
                'size': int,
                'contributors': List[Dict],
                'quality_score': float,
                'security_alerts': int,
                'confidence': float
            }
        """
        logger.info(f"Analyzing GitHub repository: {owner}/{repo}")
        
        results = {
            'owner': owner,
            'name': repo,
            'description': None,
            'language': None,
            'stars': 0,
            'forks': 0,
            'watchers': 0,
            'open_issues': 0,
            'license': None,
            'topics': [],
            'created_at': None,
            'updated_at': None,
            'pushed_at': None,
            'size': 0,
            'contributors': [],
            'quality_score': 0.0,
            'security_alerts': 0,
            'confidence': 0.0,
            'error': None
        }

        try:
            url = f"{self.rest_api_url}/repos/{owner}/{repo}"
            headers = {
                'Accept': 'application/vnd.github.v3+json'
            }
            
            if self.has_api_access:
                headers['Authorization'] = f'token {self.github_token}'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        results.update({
                            'description': data.get('description'),
                            'language': data.get('language'),
                            'stars': data.get('stargazers_count', 0),
                            'forks': data.get('forks_count', 0),
                            'watchers': data.get('watchers_count', 0),
                            'open_issues': data.get('open_issues_count', 0),
                            'license': data.get('license', {}).get('name') if data.get('license') else None,
                            'topics': data.get('topics', []),
                            'created_at': data.get('created_at'),
                            'updated_at': data.get('updated_at'),
                            'pushed_at': data.get('pushed_at'),
                            'size': data.get('size', 0),
                            'error': None
                        })
                        
                        # Get contributors if API access available
                        if self.has_api_access:
                            contributors = await self._get_contributors(owner, repo)
                            results['contributors'] = contributors
                    else:
                        results['error'] = f"API error: {response.status}"
                        
        except Exception as e:
            logger.error(f"Repository analysis error: {e}")
            results['error'] = str(e)

        # Calculate quality score
        results['quality_score'] = self._calculate_repo_quality(results)
        
        # Calculate confidence
        results['confidence'] = self._calculate_repo_confidence(results)
        
        return results

    async def _get_contributors(self, owner: str, repo: str, limit: int = 10) -> List[Dict]:
        """Get repository contributors."""
        try:
            url = f"{self.rest_api_url}/repos/{owner}/{repo}/contributors"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            params = {
                'per_page': limit
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=10) as response:
                    if response.status == 200:
                        contributors = await response.json()
                        
                        return [
                            {
                                'username': c.get('login'),
                                'contributions': c.get('contributions', 0),
                                'avatar': c.get('avatar_url'),
                                'profile': c.get('html_url')
                            }
                            for c in contributors
                        ]
                        
        except Exception as e:
            logger.error(f"Contributors fetch error: {e}")
        
        return []

    async def search_code(self, query: str, language: Optional[str] = None, max_results: int = 10) -> List[Dict]:
        """
        Search code across GitHub.
        
        Args:
            query: Search query
            language: Filter by language (optional)
            max_results: Maximum results to return
            
        Returns:
            List of code search results
        """
        logger.info(f"Searching GitHub code: {query}")
        
        if not self.has_api_access:
            logger.warning("Code search requires API access")
            return []
        
        try:
            url = f"{self.rest_api_url}/search/code"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            search_query = query
            if language:
                search_query += f" language:{language}"
            
            params = {
                'q': search_query,
                'per_page': min(max_results, 100)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        items = data.get('items', [])
                        
                        results = []
                        for item in items:
                            results.append({
                                'name': item.get('name'),
                                'path': item.get('path'),
                                'repository': item.get('repository', {}).get('full_name'),
                                'url': item.get('html_url'),
                                'score': item.get('score', 0)
                            })
                        
                        logger.info(f"Found {len(results)} code results")
                        return results
                    else:
                        logger.error(f"Code search error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Code search error: {e}")
        
        return []

    def _calculate_activity_score(self, profile: Dict) -> float:
        """Calculate developer activity score."""
        if profile.get('error'):
            return 0.0
        
        score = 0.0
        
        # Contributions
        contributions = profile.get('contributions_last_year', 0)
        score += min(contributions / 1000, 0.4)
        
        # Repositories
        repos = profile.get('public_repos', 0)
        score += min(repos / 100, 0.3)
        
        # Followers
        followers = profile.get('followers', 0)
        score += min(followers / 1000, 0.3)
        
        return min(score, 1.0)

    def _calculate_repo_quality(self, repo: Dict) -> float:
        """Calculate repository quality score."""
        if repo.get('error'):
            return 0.0
        
        score = 0.0
        
        # Stars
        stars = repo.get('stars', 0)
        score += min(stars / 1000, 0.3)
        
        # Forks
        forks = repo.get('forks', 0)
        score += min(forks / 100, 0.2)
        
        # Contributors
        contributors = len(repo.get('contributors', []))
        score += min(contributors / 10, 0.2)
        
        # Has description
        if repo.get('description'):
            score += 0.1
        
        # Has license
        if repo.get('license'):
            score += 0.1
        
        # Recent activity
        if repo.get('pushed_at'):
            score += 0.1
        
        return min(score, 1.0)

    def _calculate_confidence(self, profile: Dict) -> float:
        """Calculate confidence score."""
        if profile.get('error'):
            return 0.0
        
        confidence = 0.0
        
        if profile.get('name'):
            confidence += 0.15
        if profile.get('bio'):
            confidence += 0.15
        if profile.get('location'):
            confidence += 0.1
        if profile.get('public_repos', 0) > 0:
            confidence += 0.2
        if profile.get('followers', 0) > 0:
            confidence += 0.2
        if profile.get('top_languages'):
            confidence += 0.2
            
        return min(confidence, 1.0)

    def _calculate_repo_confidence(self, repo: Dict) -> float:
        """Calculate repository confidence score."""
        if repo.get('error'):
            return 0.0
        
        confidence = 0.0
        
        if repo.get('description'):
            confidence += 0.2
        if repo.get('language'):
            confidence += 0.2
        if repo.get('stars', 0) > 0:
            confidence += 0.2
        if repo.get('license'):
            confidence += 0.2
        if repo.get('contributors'):
            confidence += 0.2
            
        return min(confidence, 1.0)
