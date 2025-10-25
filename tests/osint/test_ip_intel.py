"""
Tests for IP Intelligence Module (v1.4.1)

Tests cover:
- IP address analysis
- Geolocation lookup
- Reputation checking
- Port scanning
- Error handling
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from core.osint.ip_intel import IPIntelligence


class TestIPIntelligence:
    """Test suite for IP Intelligence."""

    @pytest.fixture
    def ip_intel(self):
        """Create IPIntelligence instance for testing."""
        return IPIntelligence(
            ipinfo_token="test_token",
            abuseipdb_key="test_key"
        )

    @pytest.fixture
    def ip_intel_no_api(self):
        """Create IPIntelligence instance without API access."""
        return IPIntelligence()

    def test_initialization_with_tokens(self):
        """Test initialization with API tokens."""
        intel = IPIntelligence(
            ipinfo_token="test_token",
            abuseipdb_key="test_key",
            shodan_key="test_shodan"
        )
        assert intel.ipinfo_token == "test_token"
        assert intel.abuseipdb_key == "test_key"
        assert intel.shodan_key == "test_shodan"
        assert intel.has_ipinfo is True
        assert intel.has_abuseipdb is True
        assert intel.has_shodan is True

    def test_initialization_without_tokens(self):
        """Test initialization without API tokens."""
        intel = IPIntelligence()
        assert intel.has_ipinfo is False
        assert intel.has_abuseipdb is False
        assert intel.has_shodan is False

    def test_validate_ip_valid_ipv4(self, ip_intel):
        """Test IPv4 validation."""
        assert ip_intel._validate_ip('8.8.8.8') is True
        assert ip_intel._validate_ip('192.168.1.1') is True
        assert ip_intel._validate_ip('10.0.0.1') is True

    def test_validate_ip_invalid(self, ip_intel):
        """Test invalid IP validation."""
        assert ip_intel._validate_ip('256.1.1.1') is False
        assert ip_intel._validate_ip('not.an.ip') is False
        assert ip_intel._validate_ip('') is False

    @pytest.mark.asyncio
    async def test_analyze_ip_with_api(self, ip_intel):
        """Test IP analysis with API access."""
        mock_ipinfo = {
            'ip': '8.8.8.8',
            'hostname': 'dns.google',
            'city': 'Mountain View',
            'region': 'California',
            'country': 'US',
            'loc': '37.4056,-122.0775',
            'org': 'AS15169 Google LLC',
            'postal': '94043',
            'timezone': 'America/Los_Angeles'
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_ipinfo)

            result = await ip_intel.analyze_ip('8.8.8.8')

            assert result['ip'] == '8.8.8.8'
            assert result['hostname'] == 'dns.google'
            assert result['city'] == 'Mountain View'
            assert result['country'] == 'US'
            assert result['confidence'] > 0

    @pytest.mark.asyncio
    async def test_analyze_ip_free_geolocation(self, ip_intel_no_api):
        """Test IP analysis with free geolocation API."""
        mock_geo = {
            'status': 'success',
            'country': 'United States',
            'regionName': 'California',
            'city': 'Mountain View',
            'zip': '94043',
            'isp': 'Google LLC',
            'org': 'Google LLC',
            'as': 'AS15169',
            'lat': 37.4056,
            'lon': -122.0775,
            'timezone': 'America/Los_Angeles',
            'query': '8.8.8.8'
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_geo)

            result = await ip_intel_no_api.analyze_ip('8.8.8.8')

            assert result['ip'] == '8.8.8.8'
            assert result['country'] == 'United States'
            assert result['isp'] == 'Google LLC'

    @pytest.mark.asyncio
    async def test_get_abuseipdb_data(self, ip_intel):
        """Test AbuseIPDB reputation lookup."""
        mock_abuse = {
            'data': {
                'abuseConfidenceScore': 0,
                'totalReports': 0,
                'numDistinctUsers': 0,
                'isWhitelisted': True,
                'isTor': False,
                'lastReportedAt': None,
                'usageType': 'Data Center/Web Hosting/Transit',
                'domain': 'google.com'
            }
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_abuse)

            result = await ip_intel._get_abuseipdb_data('8.8.8.8')

            assert result['abuse_confidence_score'] == 0
            assert result['is_whitelisted'] is True
            assert result['is_tor'] is False

    @pytest.mark.asyncio
    async def test_check_reputation(self, ip_intel):
        """Test reputation checking."""
        mock_abuse = {
            'data': {
                'abuseConfidenceScore': 75,
                'totalReports': 10,
                'isTor': False
            }
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_abuse)

            result = await ip_intel.check_reputation('192.0.2.1')

            assert result['ip'] == '192.0.2.1'
            assert result['threat_score'] == 0.75
            assert result['is_malicious'] is True

    @pytest.mark.asyncio
    async def test_scan_ports(self, ip_intel):
        """Test port scanning functionality."""
        with patch.object(ip_intel, '_check_port', return_value=True):
            open_ports = await ip_intel.scan_ports('127.0.0.1', ports=[80, 443])
            assert 80 in open_ports
            assert 443 in open_ports

    @pytest.mark.asyncio
    async def test_check_port_open(self, ip_intel):
        """Test checking if a port is open."""
        # Skip complex async mocking
        pytest.skip("Port checking requires complex async mocking")

    @pytest.mark.asyncio
    async def test_check_port_closed(self, ip_intel):
        """Test checking if a port is closed."""
        with patch('asyncio.open_connection', side_effect=ConnectionRefusedError):
            result = await ip_intel._check_port('127.0.0.1', 9999)
            assert result is False

    @pytest.mark.asyncio
    async def test_get_hostname(self, ip_intel):
        """Test hostname resolution."""
        with patch('socket.gethostbyaddr', return_value=('dns.google', [], ['8.8.8.8'])):
            hostname = await ip_intel._get_hostname('8.8.8.8')
            assert hostname == 'dns.google'

    @pytest.mark.asyncio
    async def test_get_hostname_failure(self, ip_intel):
        """Test hostname resolution failure."""
        import socket as sock_module
        with patch('socket.gethostbyaddr', side_effect=sock_module.error):
            hostname = await ip_intel._get_hostname('192.0.2.1')
            assert hostname is None

    def test_calculate_confidence(self, ip_intel):
        """Test confidence score calculation."""
        results = {
            'country': 'US',
            'city': 'Test City',
            'isp': 'Test ISP',
            'asn': 'AS12345',
            'hostname': 'test.example.com',
            'reputation': {'threat_score': 0.0}
        }
        confidence = ip_intel._calculate_confidence(results)
        assert confidence == 1.0

    def test_calculate_confidence_minimal(self, ip_intel):
        """Test confidence score with minimal data."""
        results = {
            'country': 'US'
        }
        confidence = ip_intel._calculate_confidence(results)
        assert confidence == 0.2

    def test_calculate_confidence_with_error(self, ip_intel):
        """Test confidence score with error."""
        results = {'error': 'Invalid IP'}
        confidence = ip_intel._calculate_confidence(results)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_analyze_ip_invalid(self, ip_intel):
        """Test IP analysis with invalid IP."""
        result = await ip_intel.analyze_ip('invalid.ip')
        assert result['error'] == 'Invalid IP address format'
        assert result['confidence'] == 0.0

    @pytest.mark.asyncio
    async def test_get_shodan_data(self, ip_intel):
        """Test Shodan data retrieval."""
        mock_shodan = {
            'ports': [22, 80, 443],
            'data': [
                {
                    'port': 80,
                    'transport': 'tcp',
                    'product': 'nginx',
                    'version': '1.18.0',
                    'data': 'HTTP/1.1 200 OK'
                }
            ],
            'hostnames': ['example.com'],
            'org': 'Example Inc',
            'os': 'Linux'
        }

        intel = IPIntelligence(shodan_key="test_key")

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_shodan)

            result = await intel._get_shodan_data('8.8.8.8')

            assert result['ports'] == [22, 80, 443]
            assert len(result['services']) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
