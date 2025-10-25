"""
Tests for GitHub Intelligence Module (v1.4.1)

Tests cover:
- Developer profile analysis
- Repository analysis
- Code search
- Contributions tracking
- Error handling
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from core.osint.github_intel import GitHubIntelligence


class TestGitHubIntelligence:
    """Test suite for GitHub Intelligence."""

    @pytest.fixture
    def github_intel(self):
        """Create GitHubIntelligence instance for testing."""
        return GitHubIntelligence(github_token="test_token")

    @pytest.fixture
    def github_intel_no_api(self):
        """Create GitHubIntelligence instance without API access."""
        return GitHubIntelligence()

    def test_initialization_with_token(self):
        """Test initialization with GitHub token."""
        intel = GitHubIntelligence(github_token="test_token")
        assert intel.github_token == "test_token"
        assert intel.has_api_access is True

    def test_initialization_without_token(self):
        """Test initialization without token."""
        intel = GitHubIntelligence()
        assert intel.github_token is None
        assert intel.has_api_access is False

    @pytest.mark.asyncio
    async def test_analyze_developer(self, github_intel):
        """Test developer profile analysis."""
        mock_profile = {
            'login': 'testuser',
            'name': 'Test User',
            'bio': 'Test bio',
            'location': 'Test City',
            'email': 'test@example.com',
            'company': 'Test Company',
            'blog': 'https://example.com',
            'twitter_username': 'testuser',
            'public_repos': 50,
            'public_gists': 10,
            'followers': 100,
            'following': 50,
            'created_at': '2015-01-01T00:00:00Z',
            'updated_at': '2025-01-01T00:00:00Z'
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_profile)

            result = await github_intel.analyze_developer('testuser')

            assert result['username'] == 'testuser'
            assert result['name'] == 'Test User'
            assert result['public_repos'] == 50
            assert result['followers'] == 100
            assert result['confidence'] > 0

    @pytest.mark.asyncio
    async def test_analyze_developer_no_token(self, github_intel_no_api):
        """Test developer analysis without API token."""
        mock_profile = {
            'login': 'testuser',
            'name': 'Test User',
            'public_repos': 50,
            'followers': 100
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_profile)

            result = await github_intel_no_api.analyze_developer('testuser')

            assert result['username'] == 'testuser'
            # Without token, some features are limited
            assert result['contributions_last_year'] == 0

    @pytest.mark.asyncio
    async def test_get_contributions(self, github_intel):
        """Test contributions fetching."""
        mock_response = {
            'data': {
                'user': {
                    'contributionsCollection': {
                        'contributionCalendar': {
                            'totalContributions': 1500
                        }
                    }
                }
            }
        }

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value.status = 200
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)

            contributions = await github_intel._get_contributions('testuser')

            assert contributions == 1500

    @pytest.mark.asyncio
    async def test_get_top_languages(self, github_intel):
        """Test top languages fetching."""
        mock_repos = [
            {'language': 'Python'},
            {'language': 'Python'},
            {'language': 'JavaScript'},
            {'language': 'Python'},
            {'language': 'Go'}
        ]

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_repos)

            languages = await github_intel._get_top_languages('testuser')

            assert len(languages) > 0
            assert languages[0]['language'] == 'Python'
            assert languages[0]['repo_count'] == 3

    @pytest.mark.asyncio
    async def test_get_popular_repos(self, github_intel):
        """Test popular repositories fetching."""
        mock_repos = [
            {
                'name': 'test-repo',
                'description': 'Test repository',
                'language': 'Python',
                'stargazers_count': 100,
                'forks_count': 20,
                'html_url': 'https://github.com/test/test-repo',
                'created_at': '2020-01-01T00:00:00Z',
                'updated_at': '2025-01-01T00:00:00Z'
            }
        ]

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_repos)

            repos = await github_intel._get_popular_repos('testuser', limit=5)

            assert len(repos) == 1
            assert repos[0]['name'] == 'test-repo'
            assert repos[0]['stars'] == 100

    @pytest.mark.asyncio
    async def test_analyze_repository(self, github_intel):
        """Test repository analysis."""
        mock_repo = {
            'name': 'test-repo',
            'description': 'Test repository',
            'language': 'Python',
            'stargazers_count': 100,
            'forks_count': 20,
            'watchers_count': 50,
            'open_issues_count': 5,
            'license': {'name': 'MIT'},
            'topics': ['python', 'testing'],
            'created_at': '2020-01-01T00:00:00Z',
            'updated_at': '2025-01-01T00:00:00Z',
            'pushed_at': '2025-01-01T00:00:00Z',
            'size': 1000
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_repo)

            result = await github_intel.analyze_repository('testuser', 'test-repo')

            assert result['owner'] == 'testuser'
            assert result['name'] == 'test-repo'
            assert result['stars'] == 100
            assert result['language'] == 'Python'
            assert result['confidence'] > 0

    @pytest.mark.asyncio
    async def test_get_contributors(self, github_intel):
        """Test contributors fetching."""
        mock_contributors = [
            {
                'login': 'user1',
                'contributions': 100,
                'avatar_url': 'https://example.com/avatar1.jpg',
                'html_url': 'https://github.com/user1'
            },
            {
                'login': 'user2',
                'contributions': 50,
                'avatar_url': 'https://example.com/avatar2.jpg',
                'html_url': 'https://github.com/user2'
            }
        ]

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_contributors)

            contributors = await github_intel._get_contributors('owner', 'repo', limit=10)

            assert len(contributors) == 2
            assert contributors[0]['username'] == 'user1'
            assert contributors[0]['contributions'] == 100

    @pytest.mark.asyncio
    async def test_search_code(self, github_intel):
        """Test code search functionality."""
        mock_response = {
            'items': [
                {
                    'name': 'test.py',
                    'path': 'src/test.py',
                    'repository': {'full_name': 'user/repo'},
                    'html_url': 'https://github.com/user/repo/blob/main/src/test.py',
                    'score': 10.5
                }
            ]
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)

            results = await github_intel.search_code('flask', language='python')

            assert len(results) == 1
            assert results[0]['name'] == 'test.py'
            assert results[0]['repository'] == 'user/repo'

    @pytest.mark.asyncio
    async def test_search_code_no_api(self, github_intel_no_api):
        """Test code search without API access."""
        results = await github_intel_no_api.search_code('test')
        assert results == []

    def test_calculate_activity_score(self, github_intel):
        """Test activity score calculation."""
        profile = {
            'contributions_last_year': 1000,
            'public_repos': 50,
            'followers': 500
        }
        score = github_intel._calculate_activity_score(profile)
        assert 0 <= score <= 1.0

    def test_calculate_repo_quality(self, github_intel):
        """Test repository quality score calculation."""
        repo = {
            'stars': 1000,
            'forks': 100,
            'contributors': [{'username': 'user1'}, {'username': 'user2'}],
            'description': 'Test description',
            'license': 'MIT',
            'pushed_at': '2025-01-01T00:00:00Z'
        }
        score = github_intel._calculate_repo_quality(repo)
        assert 0 <= score <= 1.0

    def test_calculate_confidence(self, github_intel):
        """Test confidence score calculation."""
        profile = {
            'name': 'Test User',
            'bio': 'Test bio',
            'location': 'Test City',
            'public_repos': 50,
            'followers': 100,
            'top_languages': [{'language': 'Python'}]
        }
        confidence = github_intel._calculate_confidence(profile)
        assert confidence == 1.0

    @pytest.mark.asyncio
    async def test_error_handling_user_not_found(self, github_intel):
        """Test error handling for non-existent user."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 404

            result = await github_intel.analyze_developer('nonexistent')
            assert result['error'] == 'User not found'

    @pytest.mark.asyncio
    async def test_error_handling_api_error(self, github_intel):
        """Test error handling for API errors."""
        with patch('aiohttp.ClientSession.get', side_effect=Exception('API Error')):
            result = await github_intel.analyze_developer('testuser')
            assert result['error'] is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
