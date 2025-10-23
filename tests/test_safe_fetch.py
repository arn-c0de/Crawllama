"""Tests for SafeFetcher."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from utils.safe_fetch import SafeFetcher, safe_get, safe_post


class TestSafeFetcher:
    """Test SafeFetcher class."""

    def test_initialization_defaults(self):
        """Test default initialization."""
        fetcher = SafeFetcher()
        assert fetcher.use_rate_limiting is True
        assert fetcher.use_blacklist is True
        assert fetcher.use_robots is True
        assert "CrawlLama" in fetcher.user_agent

    def test_initialization_custom(self):
        """Test custom initialization."""
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False,
            user_agent="CustomBot/1.0"
        )
        assert fetcher.use_rate_limiting is False
        assert fetcher.use_blacklist is False
        assert fetcher.use_robots is False
        assert fetcher.user_agent == "CustomBot/1.0"

    @patch('utils.safe_fetch.is_safe_url')
    def test_fetch_blacklisted_url(self, mock_is_safe_url):
        """Test that blacklisted URLs are blocked."""
        mock_is_safe_url.return_value = False

        fetcher = SafeFetcher(use_blacklist=True)

        with pytest.raises(ValueError) as exc_info:
            fetcher.fetch("https://blacklisted.com")

        assert "blacklisted" in str(exc_info.value).lower()

    @patch('utils.safe_fetch.throttler')
    @patch('utils.safe_fetch.is_safe_url')
    def test_fetch_robots_disallowed(self, mock_is_safe_url, mock_throttler):
        """Test that robots.txt disallowed URLs are blocked."""
        mock_is_safe_url.return_value = True
        mock_throttler.can_fetch.return_value = False

        fetcher = SafeFetcher(use_robots=True)

        with pytest.raises(ValueError) as exc_info:
            fetcher.fetch("https://disallowed.com")

        assert "robots.txt" in str(exc_info.value).lower()

    @patch('utils.safe_fetch.throttler')
    @patch('utils.safe_fetch.is_safe_url')
    @patch('utils.safe_fetch.fetch_with_retry')
    def test_fetch_success(self, mock_fetch, mock_is_safe_url, mock_throttler):
        """Test successful fetch."""
        # Setup mocks
        mock_is_safe_url.return_value = True
        mock_throttler.can_fetch.return_value = True
        mock_throttler.wait_if_needed.return_value = None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_fetch.return_value = mock_response

        fetcher = SafeFetcher()
        response = fetcher.fetch("https://example.com")

        assert response is not None
        assert response.status_code == 200
        mock_throttler.wait_if_needed.assert_called_once()

    @patch('utils.safe_fetch.throttler')
    @patch('utils.safe_fetch.is_safe_url')
    @patch('utils.safe_fetch.fetch_with_retry')
    def test_fetch_with_rate_limiting_disabled(
        self, mock_fetch, mock_is_safe_url, mock_throttler
    ):
        """Test fetch with rate limiting disabled."""
        mock_is_safe_url.return_value = True
        mock_throttler.can_fetch.return_value = True

        mock_response = Mock()
        mock_response.status_code = 200
        mock_fetch.return_value = mock_response

        fetcher = SafeFetcher(use_rate_limiting=False, use_robots=False)
        response = fetcher.fetch("https://example.com")

        assert response is not None
        # wait_if_needed should not be called when rate limiting is disabled
        mock_throttler.wait_if_needed.assert_not_called()

    @patch('utils.safe_fetch.fetch_with_retry')
    @patch('utils.safe_fetch.is_safe_url')
    def test_fetch_request_exception(self, mock_is_safe_url, mock_fetch):
        """Test handling of request exceptions."""
        mock_is_safe_url.return_value = True
        mock_fetch.side_effect = requests.RequestException("Connection error")

        fetcher = SafeFetcher(use_robots=False)
        response = fetcher.fetch("https://example.com")

        assert response is None

    @patch('utils.safe_fetch.throttler')
    @patch('utils.safe_fetch.is_safe_url')
    @patch('utils.safe_fetch.fetch_with_retry')
    def test_get_method(self, mock_fetch, mock_is_safe_url, mock_throttler):
        """Test GET method."""
        mock_is_safe_url.return_value = True
        mock_throttler.can_fetch.return_value = True
        mock_throttler.wait_if_needed.return_value = None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_fetch.return_value = mock_response

        fetcher = SafeFetcher()
        response = fetcher.get("https://example.com")

        assert response is not None
        mock_fetch.assert_called_once()

    @patch('utils.safe_fetch.throttler')
    @patch('utils.safe_fetch.is_safe_url')
    @patch('utils.safe_fetch.fetch_with_retry')
    def test_post_method(self, mock_fetch, mock_is_safe_url, mock_throttler):
        """Test POST method."""
        mock_is_safe_url.return_value = True
        mock_throttler.can_fetch.return_value = True
        mock_throttler.wait_if_needed.return_value = None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_fetch.return_value = mock_response

        fetcher = SafeFetcher()
        response = fetcher.post("https://example.com", data={"key": "value"})

        assert response is not None

    @patch('utils.safe_fetch.throttler')
    @patch('utils.safe_fetch.is_safe_url')
    @patch('utils.safe_fetch.fetch_with_retry')
    def test_head_method(self, mock_fetch, mock_is_safe_url, mock_throttler):
        """Test HEAD method."""
        mock_is_safe_url.return_value = True
        mock_throttler.can_fetch.return_value = True
        mock_throttler.wait_if_needed.return_value = None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_fetch.return_value = mock_response

        fetcher = SafeFetcher()
        response = fetcher.head("https://example.com")

        assert response is not None

    @patch('utils.safe_fetch.ProxyValidator')
    def test_proxy_usage(self, mock_proxy_validator_class):
        """Test proxy configuration."""
        mock_validator = Mock()
        mock_validator.get_proxies.return_value = {"http": "http://proxy:8080"}
        mock_validator.should_use_proxy.return_value = True
        mock_proxy_validator_class.load_from_env.return_value = mock_validator

        fetcher = SafeFetcher(use_proxy=True)
        assert fetcher.proxies == {"http": "http://proxy:8080"}

    def test_user_agent_header(self):
        """Test that User-Agent header is set."""
        fetcher = SafeFetcher(
            use_blacklist=False,
            use_robots=False,
            user_agent="TestBot/1.0"
        )

        with patch('utils.safe_fetch.fetch_with_retry') as mock_fetch:
            mock_fetch.return_value = Mock(status_code=200)

            fetcher.fetch("https://example.com")

            # Check that headers were passed with User-Agent
            call_kwargs = mock_fetch.call_args[1]
            assert "headers" in call_kwargs
            assert call_kwargs["headers"]["User-Agent"] == "TestBot/1.0"


class TestGlobalFunctions:
    """Test global helper functions."""

    @patch('utils.safe_fetch.SafeFetcher')
    def test_safe_get(self, mock_fetcher_class):
        """Test global safe_get function."""
        mock_fetcher = Mock()
        mock_response = Mock()
        mock_fetcher.get.return_value = mock_response
        mock_fetcher_class.return_value = mock_fetcher

        # Clear global instance
        import utils.safe_fetch
        utils.safe_fetch._safe_fetcher = None

        response = safe_get("https://example.com")
        mock_fetcher.get.assert_called_once()

    @patch('utils.safe_fetch.SafeFetcher')
    def test_safe_post(self, mock_fetcher_class):
        """Test global safe_post function."""
        mock_fetcher = Mock()
        mock_response = Mock()
        mock_fetcher.post.return_value = mock_response
        mock_fetcher_class.return_value = mock_fetcher

        # Clear global instance
        import utils.safe_fetch
        utils.safe_fetch._safe_fetcher = None

        response = safe_post("https://example.com", data={"test": "data"})
        mock_fetcher.post.assert_called_once()


@pytest.mark.skip(reason="Requires network access")
class TestRealRequests:
    """Integration tests with real HTTP requests."""

    def test_fetch_real_url(self):
        """Test fetching a real URL."""
        fetcher = SafeFetcher(
            use_robots=False,
            use_rate_limiting=False
        )

        response = fetcher.get("https://httpbin.org/get")
        assert response is not None
        assert response.status_code == 200

    def test_fetch_with_all_features(self):
        """Test fetch with all security features enabled."""
        fetcher = SafeFetcher(
            use_rate_limiting=True,
            use_blacklist=True,
            use_robots=True
        )

        response = fetcher.get("https://httpbin.org/get")
        assert response is not None
        assert response.status_code == 200
