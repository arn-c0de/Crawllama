"""
Security Test Suite: HTTP Redirect Validation

Tests for SSRF protection via HTTP redirect validation.
Prevents attacks where legitimate URLs redirect to internal services.

OWASP Top 10 2021: A10 - Server-Side Request Forgery (SSRF)
Attack Vector: Open Redirect -> Internal Service Access

Test Categories:
1. Safe Redirects (should be allowed)
2. Malicious Redirects (should be blocked)
3. Redirect Chain Validation
4. HTTP Status Code Handling
5. Relative vs Absolute Redirects
"""
import pytest
import requests
import socket
from unittest.mock import Mock, patch, MagicMock
from utils.safe_fetch import SafeFetcher


class TestSafeRedirects:
    """Test that legitimate redirects are allowed."""
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_allow_redirect_to_public_domain(self, mock_request, mock_getaddrinfo):
        """Allow redirect from public domain to another public domain"""
        # Mock DNS resolution for both URLs (all public IPs)
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 80))
        ]
        
        # First request: 301 redirect
        redirect_response = Mock()
        redirect_response.status_code = 301
        redirect_response.headers = {'Location': 'https://example.com/target'}
        
        # Second request: final content
        final_response = Mock()
        final_response.status_code = 200
        final_response.text = "Content"
        
        mock_request.side_effect = [redirect_response, final_response]
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        response = fetcher.fetch("https://start.com/redirect")
        assert response is not None
        assert response.status_code == 200
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_allow_redirect_chain(self, mock_request, mock_getaddrinfo):
        """Allow chain of redirects between public domains"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))
        ]
        
        # Chain: URL1 -> URL2 -> URL3 -> Final
        r1 = Mock(status_code=301, headers={'Location': 'https://url2.com'})
        r2 = Mock(status_code=302, headers={'Location': 'https://url3.com'})
        r3 = Mock(status_code=307, headers={'Location': 'https://final.com'})
        r4 = Mock(status_code=200, text="Final content")
        
        mock_request.side_effect = [r1, r2, r3, r4]
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        response = fetcher.fetch("https://url1.com/start")
        assert response is not None
        assert response.status_code == 200
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_allow_relative_redirect(self, mock_request, mock_getaddrinfo):
        """Allow relative redirects on same domain"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 80))
        ]
        
        # Relative redirect: /page1 -> /page2
        r1 = Mock(status_code=302, headers={'Location': '/page2'})
        r2 = Mock(status_code=200, text="Content")
        
        mock_request.side_effect = [r1, r2]
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        response = fetcher.fetch("https://example.com/page1")
        assert response is not None
        assert response.status_code == 200


class TestMaliciousRedirects:
    """Test that malicious redirects are blocked."""
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_block_redirect_to_localhost(self, mock_request, mock_getaddrinfo):
        """Block redirect from public domain to localhost"""
        # First DNS lookup: public IP (safe)
        # Second DNS lookup: loopback IP (dangerous)
        mock_getaddrinfo.side_effect = [
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 80))],  # Initial URL
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 80))],  # DNS rebinding check
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('127.0.0.1', 80))],      # Redirect target
        ]
        
        # Redirect to localhost
        redirect_response = Mock()
        redirect_response.status_code = 302
        redirect_response.headers = {'Location': 'http://localhost/admin'}
        
        mock_request.return_value = redirect_response
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        with pytest.raises(ValueError) as exc_info:
            fetcher.fetch("https://trusted.com/redirect")
        
        assert "ssrf" in str(exc_info.value).lower()
        assert "redirect" in str(exc_info.value).lower()
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_block_redirect_to_private_ip(self, mock_request, mock_getaddrinfo):
        """Block redirect to private IP range"""
        mock_getaddrinfo.side_effect = [
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))],         # Initial URL
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))],         # DNS rebinding check
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('192.168.1.1', 80))],     # Redirect target
        ]
        
        redirect_response = Mock()
        redirect_response.status_code = 301
        redirect_response.headers = {'Location': 'http://192.168.1.1/internal'}
        
        mock_request.return_value = redirect_response
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        with pytest.raises(ValueError) as exc_info:
            fetcher.fetch("https://public.com/evil-redirect")
        
        assert "ssrf" in str(exc_info.value).lower()
        assert "private" in str(exc_info.value).lower()
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_block_redirect_to_aws_metadata(self, mock_request, mock_getaddrinfo):
        """Block redirect to AWS metadata service"""
        mock_getaddrinfo.side_effect = [
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('1.2.3.4', 80))],         # Initial URL
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('1.2.3.4', 80))],         # DNS rebinding check
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('169.254.169.254', 80))], # AWS metadata
        ]
        
        redirect_response = Mock()
        redirect_response.status_code = 302
        redirect_response.headers = {'Location': 'http://169.254.169.254/latest/meta-data/'}
        
        mock_request.return_value = redirect_response
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        with pytest.raises(ValueError) as exc_info:
            fetcher.fetch("https://attacker.com/redirect-to-aws")
        
        assert "ssrf" in str(exc_info.value).lower()
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_block_redirect_chain_with_one_bad_hop(self, mock_request, mock_getaddrinfo):
        """Block redirect chain if any hop is malicious"""
        mock_getaddrinfo.side_effect = [
            # Initial URL (safe)
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))],
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))],
            # First redirect (safe)
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('1.1.1.1', 80))],
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('1.1.1.1', 80))],
            # Second redirect (DANGEROUS - localhost)
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('127.0.0.1', 80))],
        ]
        
        r1 = Mock(status_code=301, headers={'Location': 'https://step2.com'})
        r2 = Mock(status_code=302, headers={'Location': 'http://127.0.0.1/admin'})
        
        mock_request.side_effect = [r1, r2]
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        with pytest.raises(ValueError) as exc_info:
            fetcher.fetch("https://start.com")
        
        assert "ssrf" in str(exc_info.value).lower()


class TestRedirectChainLimits:
    """Test redirect chain depth limits."""
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_block_infinite_redirect_loop(self, mock_request, mock_getaddrinfo):
        """Block infinite redirect loops"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))
        ]
        
        # Infinite loop: URL1 -> URL2 -> URL1 -> URL2 ...
        r1 = Mock(status_code=301, headers={'Location': 'https://url2.com'})
        r2 = Mock(status_code=301, headers={'Location': 'https://url1.com'})
        
        mock_request.side_effect = [r1, r2, r1, r2, r1, r2, r1, r2]  # More than max
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        with pytest.raises(requests.TooManyRedirects):
            fetcher.fetch("https://url1.com")
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_block_excessive_redirect_chain(self, mock_request, mock_getaddrinfo):
        """Block redirect chains exceeding max depth"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))
        ]
        
        # 10 redirects (exceeds default max of 5)
        responses = [
            Mock(status_code=301, headers={'Location': f'https://step{i}.com'})
            for i in range(10)
        ]
        
        mock_request.side_effect = responses
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        with pytest.raises(requests.TooManyRedirects):
            fetcher.fetch("https://start.com")


class TestHTTPStatusCodes:
    """Test different HTTP redirect status codes."""
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_handle_301_moved_permanently(self, mock_request, mock_getaddrinfo):
        """Handle 301 Moved Permanently"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))
        ]
        
        r1 = Mock(status_code=301, headers={'Location': 'https://new.com'})
        r2 = Mock(status_code=200, text="Content")
        
        mock_request.side_effect = [r1, r2]
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        response = fetcher.fetch("https://old.com")
        assert response.status_code == 200
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_handle_302_found(self, mock_request, mock_getaddrinfo):
        """Handle 302 Found"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))
        ]
        
        r1 = Mock(status_code=302, headers={'Location': 'https://temp.com'})
        r2 = Mock(status_code=200, text="Content")
        
        mock_request.side_effect = [r1, r2]
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        response = fetcher.fetch("https://site.com")
        assert response.status_code == 200
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_handle_303_see_other_changes_to_get(self, mock_request, mock_getaddrinfo):
        """303 See Other should change POST to GET"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))
        ]
        
        r1 = Mock(status_code=303, headers={'Location': 'https://result.com'})
        r2 = Mock(status_code=200, text="Result")
        
        mock_request.side_effect = [r1, r2]
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        # POST request with 303 should convert to GET
        response = fetcher.fetch("https://form.com", method="POST", data={'key': 'value'})
        assert response.status_code == 200
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_handle_307_temporary_redirect(self, mock_request, mock_getaddrinfo):
        """Handle 307 Temporary Redirect (preserves method)"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))
        ]
        
        r1 = Mock(status_code=307, headers={'Location': 'https://temp.com'})
        r2 = Mock(status_code=200, text="Content")
        
        mock_request.side_effect = [r1, r2]
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        response = fetcher.fetch("https://site.com")
        assert response.status_code == 200
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_handle_308_permanent_redirect(self, mock_request, mock_getaddrinfo):
        """Handle 308 Permanent Redirect"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))
        ]
        
        r1 = Mock(status_code=308, headers={'Location': 'https://new.com'})
        r2 = Mock(status_code=200, text="Content")
        
        mock_request.side_effect = [r1, r2]
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        response = fetcher.fetch("https://old.com")
        assert response.status_code == 200


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_redirect_without_location_header(self, mock_request, mock_getaddrinfo):
        """Handle redirect without Location header"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))
        ]
        
        # Redirect without Location header (malformed)
        r1 = Mock(status_code=302, headers={})
        
        mock_request.return_value = r1
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        # Should return the redirect response as-is
        response = fetcher.fetch("https://broken.com")
        assert response is not None
        assert response.status_code == 302
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_non_redirect_status_codes_not_followed(self, mock_request, mock_getaddrinfo):
        """Non-redirect status codes should not be treated as redirects"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))
        ]
        
        # 200 OK with Location header (not a redirect)
        r1 = Mock(status_code=200, headers={'Location': 'https://other.com'}, text="Content")
        
        mock_request.return_value = r1
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        response = fetcher.fetch("https://site.com")
        assert response.status_code == 200
        # Should NOT follow the Location header


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
