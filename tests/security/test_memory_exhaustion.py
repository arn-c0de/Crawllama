"""
Security Test: Memory Exhaustion Protection

Tests for DoS protection via large response size limits.

OWASP: API Security Top 10 - Lack of Resources & Rate Limiting
CWE-400: Uncontrolled Resource Consumption

Test Categories:
1. Content-Length header validation
2. Streaming download with size limit
3. Edge cases (missing header, incorrect header)
4. Different size limits for different endpoints
"""
from unittest.mock import MagicMock, Mock, patch

import pytest

from utils.safe_fetch import SafeFetcher


class TestMemoryExhaustionProtection:
    """Test protection against memory exhaustion via large downloads."""

    def test_reject_large_content_length_header(self):
        """Block downloads when Content-Length exceeds limit."""
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )

        # Mock DNS resolution to pass SSRF check
        with patch('utils.validators.socket.getaddrinfo') as mock_dns, \
             patch('requests.Session.request') as mock_request:

            # DNS returns safe public IP
            mock_dns.return_value = [
                (2, 1, 0, '', ('93.184.216.34', 80))
            ]

            # Mock response with large Content-Length
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {
                'Content-Length': '104857600'  # 100MB
            }
            mock_request.return_value = mock_response

            # Should raise ValueError for size exceeding 50MB default
            with pytest.raises(ValueError) as exc_info:
                fetcher.fetch("http://example.com/large-file.zip")

            assert "exceeds maximum allowed size" in str(exc_info.value).lower()
            assert "50" in str(exc_info.value)  # Default 50MB limit

    def test_reject_during_streaming_download(self):
        """Block download when actual size exceeds limit during streaming."""
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )

        with patch('utils.validators.socket.getaddrinfo') as mock_dns, \
             patch('requests.Session.request') as mock_request:

            mock_dns.return_value = [(2, 1, 0, '', ('93.184.216.34', 80))]

            # Mock response with no Content-Length header
            # but iter_content returns large chunks
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {}  # No Content-Length

            # Generate chunks that exceed 10MB
            chunk_size = 1024 * 1024  # 1MB chunks
            large_chunk = b'X' * chunk_size

            def generate_large_chunks():
                """Generate 15MB of data (exceeds 10MB limit)."""
                for _ in range(15):
                    yield large_chunk

            mock_response.iter_content = Mock(side_effect=lambda chunk_size: generate_large_chunks())
            mock_request.return_value = mock_response

            # Should raise ValueError during streaming
            with pytest.raises(ValueError) as exc_info:
                fetcher.fetch("http://example.com/no-content-length", max_size_mb=10)

            assert "exceeded" in str(exc_info.value).lower()
            assert "10" in str(exc_info.value)  # Our 10MB limit

    def test_allow_small_downloads(self):
        """Allow downloads within size limit."""
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )

        with patch('utils.validators.socket.getaddrinfo') as mock_dns, \
             patch('requests.Session.request') as mock_request:

            mock_dns.return_value = [(2, 1, 0, '', ('93.184.216.34', 80))]

            # Mock small response
            small_content = b'Small file content'
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {'Content-Length': str(len(small_content))}
            mock_response.iter_content = Mock(return_value=[small_content])
            mock_request.return_value = mock_response

            # Should succeed
            response = fetcher.fetch("http://example.com/small-file.txt", max_size_mb=1)

            assert response is not None
            assert response.status_code == 200

    def test_custom_size_limit(self):
        """Test custom size limits per request."""
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )

        with patch('utils.validators.socket.getaddrinfo') as mock_dns, \
             patch('requests.Session.request') as mock_request:

            mock_dns.return_value = [(2, 1, 0, '', ('93.184.216.34', 80))]

            # 6MB file
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {'Content-Length': '6291456'}  # 6MB
            mock_request.return_value = mock_response

            # Should fail with 5MB limit
            with pytest.raises(ValueError) as exc_info:
                fetcher.fetch("http://example.com/file", max_size_mb=5)

            assert "exceeds maximum" in str(exc_info.value).lower()

    def test_missing_content_length_with_chunked(self):
        """Handle responses without Content-Length (chunked transfer)."""
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )

        with patch('utils.validators.socket.getaddrinfo') as mock_dns, \
             patch('requests.Session.request') as mock_request:

            mock_dns.return_value = [(2, 1, 0, '', ('93.184.216.34', 80))]

            # No Content-Length, small chunks
            small_chunk = b'Small chunk\n'
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {}  # No Content-Length
            mock_response.iter_content = Mock(return_value=[small_chunk] * 10)
            mock_request.return_value = mock_response

            # Should succeed - total is small
            response = fetcher.fetch("http://example.com/chunked", max_size_mb=1)

            assert response is not None
            assert response.status_code == 200

    def test_malicious_content_length_mismatch(self):
        """Detect when Content-Length doesn't match actual size."""
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )

        with patch('utils.validators.socket.getaddrinfo') as mock_dns, \
             patch('requests.Session.request') as mock_request:

            mock_dns.return_value = [(2, 1, 0, '', ('93.184.216.34', 80))]

            # Claims 1KB but sends 15MB
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {'Content-Length': '1024'}  # Claims 1KB

            # But actually sends 15MB
            large_chunk = b'X' * (1024 * 1024)  # 1MB chunks

            def generate_deceptive_chunks():
                for _ in range(15):  # 15MB total
                    yield large_chunk

            mock_response.iter_content = Mock(side_effect=lambda chunk_size: generate_deceptive_chunks())
            mock_request.return_value = mock_response

            # Should be caught during streaming
            with pytest.raises(ValueError) as exc_info:
                fetcher.fetch("http://example.com/deceptive", max_size_mb=10)

            assert "exceeded" in str(exc_info.value).lower()


class TestPageReaderSizeLimits:
    """Test size limits are applied to page_reader functions."""

    def test_read_page_with_size_limit(self):
        """read_page should use size limit."""
        from tools.page_reader import read_page

        with patch('tools.page_reader.safe_get') as mock_safe_get, \
             patch('utils.domain_blacklist.is_url_not_blacklisted', return_value=True):

            # Mock response
            mock_response = MagicMock()
            mock_response.headers = {'Content-Type': 'text/html'}
            mock_response.text = '<html><body>Test</body></html>'
            mock_safe_get.return_value = mock_response

            # Call read_page
            read_page("http://example.com", smart_contact_search=False)

            # Verify safe_get was called with max_size_mb
            assert mock_safe_get.called
            # Check first call (may be called multiple times for contact search)
            call_kwargs = mock_safe_get.call_args_list[0][1]
            assert 'max_size_mb' in call_kwargs
            assert call_kwargs['max_size_mb'] == 20  # Default for read_page


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
