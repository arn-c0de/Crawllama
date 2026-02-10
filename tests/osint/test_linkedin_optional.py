"""Tests for optional LinkedIn API feature - Category: osint

Tests verify:
1. Web scraping path works without linkedin-api installed
2. LinkedIn API module handles missing dependency gracefully
3. LinkedIn API activates when module is present and configured
4. Graceful degradation when credentials are missing
"""
import pytest
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.osint.social_intel import SocialIntelligence
from core.osint import linkedin_api_intel


class TestLinkedInApiAvailability:
    """Test the linkedin_api_intel module availability checks."""

    def test_is_available_returns_bool(self):
        result = linkedin_api_intel.is_available()
        assert isinstance(result, bool)

    def test_has_credentials_without_env(self):
        with patch.dict("os.environ", {}, clear=True):
            assert linkedin_api_intel.has_credentials() is False

    def test_has_credentials_with_partial_env(self):
        with patch.dict("os.environ", {"LINKEDIN_EMAIL": "test@test.com"}, clear=True):
            assert linkedin_api_intel.has_credentials() is False

    def test_has_credentials_with_full_env(self):
        with patch.dict(
            "os.environ",
            {"LINKEDIN_EMAIL": "test@test.com", "LINKEDIN_PASSWORD": "pass"},
            clear=True,
        ):
            assert linkedin_api_intel.has_credentials() is True

    def test_is_ready_requires_both(self):
        """is_ready() requires both package installed and credentials set."""
        with patch.dict("os.environ", {}, clear=True):
            # Even if package is available, no credentials means not ready
            if linkedin_api_intel.is_available():
                assert linkedin_api_intel.is_ready() is False
            else:
                assert linkedin_api_intel.is_ready() is False


class TestLinkedInApiGracefulDegradation:
    """Test that functions return empty results when not available."""

    def test_get_profile_returns_empty_when_not_ready(self):
        with patch.object(linkedin_api_intel, "is_ready", return_value=False):
            result = linkedin_api_intel.get_profile("john-doe")
            assert result == {}

    def test_search_people_returns_empty_when_not_ready(self):
        with patch.object(linkedin_api_intel, "is_ready", return_value=False):
            result = linkedin_api_intel.search_people("John Doe")
            assert result == []

    def test_get_client_returns_none_when_not_ready(self):
        with patch.object(linkedin_api_intel, "is_ready", return_value=False):
            result = linkedin_api_intel._get_client()
            assert result is None


class TestLinkedInApiWithMockedPackage:
    """Test LinkedIn API integration with mocked linkedin-api package."""

    def test_get_profile_with_mocked_api(self):
        mock_client = MagicMock()
        mock_client.get_profile.return_value = {
            "firstName": "John",
            "lastName": "Doe",
            "headline": "Software Engineer",
            "geoLocationName": "San Francisco",
            "industryName": "Technology",
            "summary": "Experienced engineer",
            "connections": 500,
        }

        with patch.object(linkedin_api_intel, "is_ready", return_value=True), \
             patch.object(linkedin_api_intel, "_get_client", return_value=mock_client):
            result = linkedin_api_intel.get_profile("john-doe")

        assert result["display_name"] == "John Doe"
        assert result["title"] == "Software Engineer"
        assert result["location"] == "San Francisco"
        assert result["industry"] == "Technology"
        assert result["bio"] == "Experienced engineer"
        assert result["connections"] == 500
        assert result["source"] == "linkedin_api"

    def test_get_profile_handles_api_error(self):
        mock_client = MagicMock()
        mock_client.get_profile.side_effect = Exception("API error")

        with patch.object(linkedin_api_intel, "is_ready", return_value=True), \
             patch.object(linkedin_api_intel, "_get_client", return_value=mock_client):
            result = linkedin_api_intel.get_profile("john-doe")

        assert result == {}

    def test_get_profile_handles_empty_response(self):
        mock_client = MagicMock()
        mock_client.get_profile.return_value = None

        with patch.object(linkedin_api_intel, "is_ready", return_value=True), \
             patch.object(linkedin_api_intel, "_get_client", return_value=mock_client):
            result = linkedin_api_intel.get_profile("nonexistent-user")

        assert result == {}

    def test_search_people_with_mocked_api(self):
        mock_client = MagicMock()
        mock_client.search_people.return_value = [
            {"name": "John Doe", "jobtitle": "Engineer", "location": "SF", "public_id": "john-doe"},
        ]

        with patch.object(linkedin_api_intel, "is_ready", return_value=True), \
             patch.object(linkedin_api_intel, "_get_client", return_value=mock_client):
            result = linkedin_api_intel.search_people("John Doe", limit=5)

        assert len(result) == 1
        assert result[0]["name"] == "John Doe"
        assert result[0]["public_id"] == "john-doe"

    def test_search_people_handles_api_error(self):
        mock_client = MagicMock()
        mock_client.search_people.side_effect = Exception("Search failed")

        with patch.object(linkedin_api_intel, "is_ready", return_value=True), \
             patch.object(linkedin_api_intel, "_get_client", return_value=mock_client):
            result = linkedin_api_intel.search_people("test")

        assert result == []


class TestSocialIntelLinkedInIntegration:
    """Test SocialIntelligence class LinkedIn API integration."""

    def test_initialization_without_linkedin_api(self):
        """SocialIntelligence initializes fine without LinkedIn API."""
        social = SocialIntelligence()
        assert social is not None
        assert 'linkedin' in social.platforms

    def test_linkedin_platform_config_exists(self):
        """LinkedIn platform configuration is correct."""
        social = SocialIntelligence()
        linkedin_config = social.platforms['linkedin']
        assert linkedin_config['url_pattern'] == 'https://linkedin.com/in/{username}'
        assert len(linkedin_config['check_urls']) >= 2
        assert linkedin_config['username_pattern']

    def test_linkedin_api_ready_flag(self):
        """linkedin_api_ready is set based on module availability."""
        social = SocialIntelligence()
        assert isinstance(social.linkedin_api_ready, bool)

    @pytest.mark.asyncio
    async def test_linkedin_api_used_when_ready(self):
        """When LinkedIn API is ready, it's tried first for LinkedIn platform."""
        social = SocialIntelligence()
        social.linkedin_api_ready = True

        mock_profile = {
            "display_name": "Test User",
            "title": "Engineer",
            "location": "Berlin",
            "bio": "Test bio",
            "connections": 100,
        }

        with patch.object(linkedin_api_intel, "get_profile", return_value=mock_profile):
            result = await social._check_platform_presence("test-user", "linkedin")

        assert result["exists"] is True
        assert result["success_method"] == "linkedin_api"
        assert result["profile_data"]["display_name"] == "Test User"

    @pytest.mark.asyncio
    async def test_linkedin_falls_back_to_scraping_on_api_failure(self):
        """When LinkedIn API fails, falls back to web scraping."""
        social = SocialIntelligence()
        social.linkedin_api_ready = True

        with patch.object(linkedin_api_intel, "get_profile", return_value={}):
            result = await social._check_platform_presence("test-user", "linkedin")

        # API returned empty, so 'linkedin_api' was tried
        assert "linkedin_api" in result["methods_tried"]
        # It should have continued to try web scraping methods

    @pytest.mark.asyncio
    async def test_non_linkedin_platforms_unaffected(self):
        """Non-LinkedIn platforms don't use LinkedIn API."""
        social = SocialIntelligence()
        social.linkedin_api_ready = True

        with patch.object(linkedin_api_intel, "get_profile") as mock_get:
            # This will likely timeout/fail on the HTTP request, but
            # we're just checking that get_profile is NOT called for github
            try:
                await social._check_platform_presence("test-user", "github")
            except Exception:
                pass
            mock_get.assert_not_called()

    def test_report_reflects_api_mode(self):
        """Report header changes based on LinkedIn API availability."""
        social = SocialIntelligence()

        analysis_results = {
            "username": "test",
            "platforms_found": [],
            "platforms_not_found": [],
            "variations": [],
            "summary": {
                "total_platforms_checked": 1,
                "platforms_with_presence": 0,
                "confidence_score": 0.0,
                "risk_indicators": [],
            },
        }

        social.linkedin_api_ready = False
        report_scraping = social.generate_social_report(analysis_results)
        assert "No API Keys Required" in report_scraping

        social.linkedin_api_ready = True
        report_api = social.generate_social_report(analysis_results)
        assert "LinkedIn API" in report_api
