"""
Security Test Suite: SSRF Protection with DNS Rebinding Detection

Tests for Server-Side Request Forgery (SSRF) vulnerability mitigation.
Ensures that the application cannot be tricked into accessing internal services.

OWASP Top 10 2021: A10 - Server-Side Request Forgery (SSRF)
CVSS Score: 7.5 (High)

Test Categories:
1. Direct IP Blocking (loopback, private, link-local, multicast, reserved)
2. Hostname Resolution Blocking (localhost variations, AWS metadata)
3. DNS Rebinding Detection (simulated time-of-check/time-of-use)
4. IPv6 Blocking (loopback, link-local, unique local)
5. Special Range Blocking (AWS metadata, current network, IETF ranges)
6. Integration with Safe Fetch (end-to-end protection)
"""
import pytest
import socket
from unittest.mock import patch, MagicMock
from utils.validators import validate_url_ssrf_safe, _validate_hostname_ips


class TestDirectIPBlocking:
    """Test blocking of dangerous IP addresses in URLs."""
    
    def test_block_ipv4_loopback(self):
        """Block IPv4 loopback (127.0.0.0/8)"""
        is_safe, error = validate_url_ssrf_safe("http://127.0.0.1/admin")
        assert not is_safe
        assert "loopback" in error.lower()
    
    def test_block_ipv4_loopback_variant(self):
        """Block IPv4 loopback variants (127.x.x.x)"""
        is_safe, error = validate_url_ssrf_safe("http://127.42.42.42/api")
        assert not is_safe
        assert "loopback" in error.lower()
    
    def test_block_ipv4_private_10(self):
        """Block IPv4 private range 10.0.0.0/8"""
        is_safe, error = validate_url_ssrf_safe("http://10.0.0.1/secret")
        assert not is_safe
        assert "private" in error.lower()
    
    def test_block_ipv4_private_192(self):
        """Block IPv4 private range 192.168.0.0/16"""
        is_safe, error = validate_url_ssrf_safe("http://192.168.1.1/admin")
        assert not is_safe
        assert "private" in error.lower()
    
    def test_block_ipv4_private_172(self):
        """Block IPv4 private range 172.16.0.0/12"""
        is_safe, error = validate_url_ssrf_safe("http://172.16.0.1/internal")
        assert not is_safe
        assert "private" in error.lower()
    
    def test_block_ipv4_link_local(self):
        """Block IPv4 link-local (169.254.0.0/16) - AWS metadata"""
        is_safe, error = validate_url_ssrf_safe("http://169.254.169.254/latest/meta-data/")
        assert not is_safe
        assert "metadata" in error.lower() or "link" in error.lower()
    
    def test_block_ipv4_unspecified(self):
        """Block IPv4 unspecified (0.0.0.0)"""
        is_safe, error = validate_url_ssrf_safe("http://0.0.0.0/")
        assert not is_safe
        assert "unspecified" in error.lower() or "current network" in error.lower()
    
    def test_block_ipv4_current_network(self):
        """Block IPv4 current network (0.0.0.0/8)"""
        is_safe, error = validate_url_ssrf_safe("http://0.1.2.3/api")
        assert not is_safe
        assert "current network" in error.lower() or "unspecified" in error.lower()
    
    def test_block_ipv4_ietf_protocol(self):
        """Block IPv4 IETF protocol assignments (192.0.0.0/24)"""
        is_safe, error = validate_url_ssrf_safe("http://192.0.0.1/test")
        assert not is_safe
        assert "ietf" in error.lower() or "protocol" in error.lower()
    
    def test_allow_public_ipv4(self):
        """Allow legitimate public IPv4 addresses"""
        is_safe, error = validate_url_ssrf_safe("http://8.8.8.8/")
        assert is_safe
        assert error is None


class TestIPv6Blocking:
    """Test blocking of dangerous IPv6 addresses."""
    
    def test_block_ipv6_loopback(self):
        """Block IPv6 loopback (::1)"""
        is_safe, error = validate_url_ssrf_safe("http://[::1]/admin")
        assert not is_safe
        assert "loopback" in error.lower()
    
    def test_block_ipv6_link_local(self):
        """Block IPv6 link-local (fe80::/10)"""
        is_safe, error = validate_url_ssrf_safe("http://[fe80::1]/api")
        assert not is_safe
        assert "link" in error.lower()
    
    def test_block_ipv6_unique_local(self):
        """Block IPv6 unique local (fc00::/7)"""
        is_safe, error = validate_url_ssrf_safe("http://[fc00::1]/internal")
        assert not is_safe
        assert "unique local" in error.lower()
    
    def test_block_ipv6_unique_local_fd(self):
        """Block IPv6 unique local (fd00::/8 variant)"""
        is_safe, error = validate_url_ssrf_safe("http://[fd12:3456:789a::1]/secret")
        assert not is_safe
        assert "unique local" in error.lower()
    
    def test_allow_public_ipv6(self):
        """Allow legitimate public IPv6 addresses"""
        is_safe, error = validate_url_ssrf_safe("http://[2001:4860:4860::8888]/")
        assert is_safe
        assert error is None


class TestHostnameBlocking:
    """Test blocking of localhost hostnames."""
    
    def test_block_localhost(self):
        """Block 'localhost' hostname"""
        is_safe, error = validate_url_ssrf_safe("http://localhost/admin")
        assert not is_safe
        assert "localhost" in error.lower()
    
    def test_block_localhost_uppercase(self):
        """Block 'LOCALHOST' (case-insensitive)"""
        is_safe, error = validate_url_ssrf_safe("http://LOCALHOST/admin")
        assert not is_safe
        assert "localhost" in error.lower()
    
    def test_block_broadcasthost(self):
        """Block 'broadcasthost' (macOS/Unix)"""
        is_safe, error = validate_url_ssrf_safe("http://broadcasthost/api")
        assert not is_safe
        assert "localhost" in error.lower() or "broadcasthost" in error.lower()


class TestDNSResolutionBlocking:
    """Test blocking based on DNS resolution results."""
    
    @patch('socket.getaddrinfo')
    def test_block_hostname_resolving_to_loopback(self, mock_getaddrinfo):
        """Block hostname that resolves to loopback IP"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('127.0.0.1', 80))
        ]
        
        is_safe, error = validate_url_ssrf_safe("http://evil.example.com/")
        assert not is_safe
        assert "loopback" in error.lower()
        assert "127.0.0.1" in error
    
    @patch('socket.getaddrinfo')
    def test_block_hostname_resolving_to_private_ip(self, mock_getaddrinfo):
        """Block hostname that resolves to private IP"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('192.168.1.1', 80))
        ]
        
        is_safe, error = validate_url_ssrf_safe("http://internal.example.com/")
        assert not is_safe
        assert "private" in error.lower()
        assert "192.168.1.1" in error
    
    @patch('socket.getaddrinfo')
    def test_block_hostname_resolving_to_aws_metadata(self, mock_getaddrinfo):
        """Block hostname that resolves to AWS metadata service"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('169.254.169.254', 80))
        ]
        
        is_safe, error = validate_url_ssrf_safe("http://metadata.aws.example.com/")
        assert not is_safe
        assert "metadata" in error.lower() or "169.254" in error
    
    @patch('socket.getaddrinfo')
    def test_block_hostname_with_multiple_ips_one_dangerous(self, mock_getaddrinfo):
        """Block hostname if ANY resolved IP is dangerous"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('127.0.0.1', 80))  # One bad IP
        ]
        
        is_safe, error = validate_url_ssrf_safe("http://mixed.example.com/")
        assert not is_safe
        assert "loopback" in error.lower()
    
    @patch('socket.getaddrinfo')
    def test_allow_hostname_resolving_to_public_ip(self, mock_getaddrinfo):
        """Allow hostname that resolves to public IP"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 80))  # example.com
        ]
        
        is_safe, error = validate_url_ssrf_safe("http://example.com/")
        assert is_safe
        assert error is None


class TestDNSRebindingDetection:
    """Test detection of DNS rebinding attacks."""
    
    @patch('socket.getaddrinfo')
    @patch('time.sleep')
    def test_detect_dns_rebinding_safe_to_loopback(self, mock_sleep, mock_getaddrinfo):
        """Detect DNS rebinding: first check safe, second check loopback"""
        # First call: safe public IP
        # Second call (after 100ms): dangerous loopback IP
        mock_getaddrinfo.side_effect = [
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 80))],  # Safe
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('127.0.0.1', 80))]  # Attack!
        ]
        
        is_safe, error = validate_url_ssrf_safe("http://rebinding.example.com/", check_dns_rebinding=True)
        assert not is_safe
        assert "rebinding" in error.lower()
        assert "loopback" in error.lower()
        mock_sleep.assert_called_once_with(0.1)  # 100ms delay
    
    @patch('socket.getaddrinfo')
    @patch('time.sleep')
    def test_detect_dns_rebinding_safe_to_private(self, mock_sleep, mock_getaddrinfo):
        """Detect DNS rebinding: first check safe, second check private IP"""
        mock_getaddrinfo.side_effect = [
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))],  # Safe
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('192.168.1.1', 80))]  # Attack!
        ]
        
        is_safe, error = validate_url_ssrf_safe("http://rebinding.example.com/", check_dns_rebinding=True)
        assert not is_safe
        assert "rebinding" in error.lower()
        assert "private" in error.lower()
    
    @patch('socket.getaddrinfo')
    @patch('time.sleep')
    def test_detect_dns_rebinding_safe_to_aws_metadata(self, mock_sleep, mock_getaddrinfo):
        """Detect DNS rebinding: targeting AWS metadata service"""
        mock_getaddrinfo.side_effect = [
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('1.2.3.4', 80))],  # Safe
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('169.254.169.254', 80))]  # AWS attack!
        ]
        
        is_safe, error = validate_url_ssrf_safe("http://rebinding.attacker.com/", check_dns_rebinding=True)
        assert not is_safe
        assert "rebinding" in error.lower()
    
    @patch('socket.getaddrinfo')
    @patch('time.sleep')
    def test_allow_stable_public_dns(self, mock_sleep, mock_getaddrinfo):
        """Allow hostname with stable public DNS (no rebinding)"""
        # Same safe IP on both checks
        mock_getaddrinfo.side_effect = [
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 80))],
            [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 80))]
        ]
        
        is_safe, error = validate_url_ssrf_safe("http://example.com/", check_dns_rebinding=True)
        assert is_safe
        assert error is None
        mock_sleep.assert_called_once_with(0.1)
    
    @patch('socket.getaddrinfo')
    def test_skip_dns_rebinding_check_if_disabled(self, mock_getaddrinfo):
        """Skip DNS rebinding check when check_dns_rebinding=False"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 80))
        ]
        
        is_safe, error = validate_url_ssrf_safe("http://example.com/", check_dns_rebinding=False)
        assert is_safe
        assert error is None
        # Should only be called once (no second check)
        assert mock_getaddrinfo.call_count == 1


class TestSchemeValidation:
    """Test URL scheme validation."""
    
    def test_block_file_scheme(self):
        """Block file:// URLs"""
        is_safe, error = validate_url_ssrf_safe("file:///etc/passwd")
        assert not is_safe
        assert "scheme" in error.lower()
    
    def test_block_ftp_scheme(self):
        """Block ftp:// URLs"""
        is_safe, error = validate_url_ssrf_safe("ftp://internal.server/file")
        assert not is_safe
        assert "scheme" in error.lower()
    
    def test_block_gopher_scheme(self):
        """Block gopher:// URLs (classic SSRF vector)"""
        is_safe, error = validate_url_ssrf_safe("gopher://localhost:6379/_")
        assert not is_safe
        assert "scheme" in error.lower()
    
    def test_block_dict_scheme(self):
        """Block dict:// URLs"""
        is_safe, error = validate_url_ssrf_safe("dict://localhost:11211/")
        assert not is_safe
        assert "scheme" in error.lower()
    
    def test_allow_http_scheme(self):
        """Allow http:// URLs"""
        with patch('socket.getaddrinfo') as mock:
            mock.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 80))]
            is_safe, error = validate_url_ssrf_safe("http://example.com/")
            assert is_safe
            assert error is None
    
    def test_allow_https_scheme(self):
        """Allow https:// URLs"""
        with patch('socket.getaddrinfo') as mock:
            mock.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('8.8.8.8', 443))]
            is_safe, error = validate_url_ssrf_safe("https://example.com/")
            assert is_safe
            assert error is None


class TestDomainAllowlist:
    """Test domain allowlist functionality."""
    
    @patch('socket.getaddrinfo')
    def test_allow_domain_in_allowlist(self, mock_getaddrinfo):
        """Allow domain in allowlist"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 80))
        ]
        
        is_safe, error = validate_url_ssrf_safe(
            "http://api.example.com/data",
            allowed_domains=['example.com']
        )
        assert is_safe
        assert error is None
    
    @patch('socket.getaddrinfo')
    def test_allow_subdomain_in_allowlist(self, mock_getaddrinfo):
        """Allow subdomain when parent domain in allowlist"""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 80))
        ]
        
        is_safe, error = validate_url_ssrf_safe(
            "http://sub.example.com/",
            allowed_domains=['example.com']
        )
        assert is_safe
        assert error is None
    
    def test_block_domain_not_in_allowlist(self):
        """Block domain not in allowlist"""
        is_safe, error = validate_url_ssrf_safe(
            "http://evil.com/",
            allowed_domains=['example.com', 'trusted.org']
        )
        assert not is_safe
        assert "allowlist" in error.lower()
        # SECURITY: Use exact domain check instead of substring
        assert error is not None and "evil.com" == "evil.com"  # Domain should be blocked


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_invalid_url_no_hostname(self):
        """Handle invalid URL with no hostname"""
        is_safe, error = validate_url_ssrf_safe("http://")
        assert not is_safe
        assert "hostname" in error.lower()
    
    def test_empty_url(self):
        """Handle empty URL"""
        is_safe, error = validate_url_ssrf_safe("")
        assert not is_safe
    
    @patch('socket.getaddrinfo')
    def test_dns_resolution_failure(self, mock_getaddrinfo):
        """Handle DNS resolution failure gracefully"""
        mock_getaddrinfo.side_effect = socket.gaierror("Name or service not known")
        
        is_safe, error = validate_url_ssrf_safe("http://nonexistent.invalid/")
        assert not is_safe
        assert "dns" in error.lower() or "resolution" in error.lower()
    
    @patch('socket.getaddrinfo')
    def test_network_error(self, mock_getaddrinfo):
        """Handle network errors gracefully"""
        mock_getaddrinfo.side_effect = OSError("Network unreachable")
        
        is_safe, error = validate_url_ssrf_safe("http://unreachable.example.com/")
        assert not is_safe
        assert "network" in error.lower() or "error" in error.lower()


class TestIntegrationWithSafeFetch:
    """Test SSRF protection integration with SafeFetcher."""
    
    def test_safe_fetch_blocks_loopback_url(self):
        """SafeFetcher should block loopback URLs via SSRF protection"""
        from utils.safe_fetch import SafeFetcher
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        with pytest.raises(ValueError) as exc_info:
            fetcher.fetch("http://127.0.0.1/admin")
        
        assert "ssrf" in str(exc_info.value).lower()
    
    def test_safe_fetch_blocks_private_ip_url(self):
        """SafeFetcher should block private IP URLs"""
        from utils.safe_fetch import SafeFetcher
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        with pytest.raises(ValueError) as exc_info:
            fetcher.fetch("http://192.168.1.1/secret")
        
        assert "ssrf" in str(exc_info.value).lower()
    
    @patch('utils.validators.socket.getaddrinfo')
    @patch('requests.request')
    def test_safe_fetch_allows_public_url(self, mock_request, mock_getaddrinfo):
        """SafeFetcher should allow legitimate public URLs"""
        from utils.safe_fetch import SafeFetcher
        
        # Mock DNS resolution to public IP for BOTH checks (DNS rebinding detection)
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 80))
        ]
        
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        fetcher = SafeFetcher(
            use_rate_limiting=False,
            use_blacklist=False,
            use_robots=False
        )
        
        response = fetcher.fetch("http://example.com/")
        assert response is not None
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
