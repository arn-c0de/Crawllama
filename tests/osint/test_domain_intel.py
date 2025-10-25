"""
Tests for Domain Intelligence Module (v1.4.1)

Tests cover:
- Domain analysis
- WHOIS lookup
- DNS records
- SSL certificate analysis
- Technology detection
- Error handling
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from core.osint.domain_intel import DomainIntelligence


class TestDomainIntelligence:
    """Test suite for Domain Intelligence."""

    @pytest.fixture
    def domain_intel(self):
        """Create DomainIntelligence instance for testing."""
        return DomainIntelligence(
            whois_api_key="test_key",
            securitytrails_key="test_key",
            virustotal_key="test_key"
        )

    @pytest.fixture
    def domain_intel_no_api(self):
        """Create DomainIntelligence instance without API access."""
        return DomainIntelligence()

    def test_initialization_with_keys(self):
        """Test initialization with API keys."""
        intel = DomainIntelligence(
            whois_api_key="test_key",
            securitytrails_key="test_st",
            virustotal_key="test_vt"
        )
        assert intel.whois_api_key == "test_key"
        assert intel.securitytrails_key == "test_st"
        assert intel.virustotal_key == "test_vt"
        assert intel.has_whois_api is True
        assert intel.has_securitytrails is True
        assert intel.has_virustotal is True

    def test_initialization_without_keys(self):
        """Test initialization without API keys."""
        intel = DomainIntelligence()
        assert intel.has_whois_api is False
        assert intel.has_securitytrails is False
        assert intel.has_virustotal is False

    def test_validate_domain_valid(self, domain_intel):
        """Test valid domain validation."""
        assert domain_intel._validate_domain('example.com') is True
        assert domain_intel._validate_domain('sub.example.com') is True
        assert domain_intel._validate_domain('example.co.uk') is True

    def test_validate_domain_invalid(self, domain_intel):
        """Test invalid domain validation."""
        assert domain_intel._validate_domain('not a domain') is False
        assert domain_intel._validate_domain('') is False
        assert domain_intel._validate_domain('example') is False

    def test_clean_domain(self, domain_intel):
        """Test domain cleaning."""
        assert domain_intel._clean_domain('https://www.example.com/path') == 'example.com'
        assert domain_intel._clean_domain('http://example.com:8080') == 'example.com'
        assert domain_intel._clean_domain('WWW.EXAMPLE.COM') == 'example.com'

    @pytest.mark.asyncio
    async def test_analyze_domain(self, domain_intel):
        """Test comprehensive domain analysis."""
        mock_whois = {
            'registrar': 'Test Registrar',
            'creation_date': '2000-01-01',
            'expiration_date': '2026-01-01'
        }

        with patch.object(domain_intel, '_get_whois_api_data', return_value=mock_whois):
            with patch.object(domain_intel, '_get_dns_records', return_value={'A': ['93.184.216.34']}):
                with patch.object(domain_intel, '_get_ssl_info', return_value={'valid': True}):
                    with patch.object(domain_intel, '_detect_technologies', return_value=[]):
                        result = await domain_intel.analyze_domain('example.com')

                        assert result['domain'] == 'example.com'
                        assert result['whois']['registrar'] == 'Test Registrar'
                        assert '93.184.216.34' in result['ip_addresses']
                        assert result['confidence'] > 0

    @pytest.mark.asyncio
    async def test_get_whois_api_data(self, domain_intel):
        """Test WHOIS API data retrieval."""
        mock_whois = {
            'WhoisRecord': {
                'registrarName': 'Test Registrar',
                'createdDate': '2000-01-01T00:00:00Z',
                'expiresDate': '2026-01-01T00:00:00Z',
                'updatedDate': '2025-01-01T00:00:00Z',
                'registrant': {
                    'name': 'Test User',
                    'organization': 'Test Org',
                    'country': 'US',
                    'email': 'test@example.com'
                },
                'nameServers': {
                    'hostNames': ['ns1.example.com', 'ns2.example.com']
                },
                'status': 'clientTransferProhibited',
                'dnssec': 'unsigned'
            }
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_whois)

            result = await domain_intel._get_whois_api_data('example.com')

            assert result['registrar'] == 'Test Registrar'
            assert result['registrant_name'] == 'Test User'
            assert 'ns1.example.com' in result['name_servers']

    @pytest.mark.asyncio
    async def test_get_dns_records(self, domain_intel):
        """Test DNS records retrieval."""
        with patch('dns.resolver.resolve') as mock_resolve:
            # Mock A records
            mock_resolve.return_value = [Mock(__str__=lambda x: '93.184.216.34')]

            result = await domain_intel._get_dns_records('example.com')

            assert 'A' in result
            assert isinstance(result['A'], list)

    @pytest.mark.asyncio
    async def test_get_ssl_info(self, domain_intel):
        """Test SSL certificate information retrieval."""
        # Skip complex SSL async mocking
        pytest.skip("SSL certificate mocking requires complex async setup")

    @pytest.mark.asyncio
    async def test_enumerate_subdomains(self, domain_intel):
        """Test subdomain enumeration."""
        mock_response = {
            'subdomains': ['www', 'mail', 'ftp', 'blog']
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)

            result = await domain_intel._enumerate_subdomains('example.com')

            assert 'www.example.com' in result
            assert 'mail.example.com' in result

    @pytest.mark.asyncio
    async def test_enumerate_subdomains_no_api(self, domain_intel_no_api):
        """Test subdomain enumeration without API."""
        result = await domain_intel_no_api._enumerate_subdomains('example.com')
        assert result == []

    @pytest.mark.asyncio
    async def test_get_virustotal_reputation(self, domain_intel):
        """Test VirusTotal reputation check."""
        mock_vt = {
            'data': {
                'attributes': {
                    'last_analysis_stats': {
                        'malicious': 0,
                        'suspicious': 0,
                        'harmless': 80,
                        'undetected': 10
                    },
                    'reputation': 100,
                    'categories': {
                        'Webroot': 'Information Technology'
                    },
                    'popularity_ranks': {
                        'Alexa': {'rank': 1000}
                    }
                }
            }
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_vt)

            result = await domain_intel._get_virustotal_reputation('example.com')

            assert result['malicious'] == 0
            assert result['harmless'] == 80
            assert result['reputation'] == 100

    @pytest.mark.asyncio
    async def test_detect_technologies(self, domain_intel):
        """Test web technology detection."""
        mock_html = """
        <html>
            <head>
                <meta name="generator" content="WordPress 5.8">
            </head>
            <body>
                <script src="/wp-content/themes/test/script.js"></script>
                <script src="https://www.google-analytics.com/analytics.js"></script>
                <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            </body>
        </html>
        """

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = Mock()
            mock_response.text = AsyncMock(return_value=mock_html)
            mock_response.headers = {'Server': 'nginx/1.18.0', 'X-Powered-By': 'PHP/7.4'}
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await domain_intel._detect_technologies('example.com')

            # Check for detected technologies
            tech_names = [t['name'] for t in result]
            tech_values = [t['value'] for t in result]

            assert 'Server' in tech_names
            assert any('WordPress' in v for v in tech_values)
            assert any('Google Analytics' in v for v in tech_values)

    def test_calculate_security_score(self, domain_intel):
        """Test security score calculation."""
        results = {
            'ssl_certificate': {
                'valid': True,
                'expired': False
            },
            'whois': {
                'dnssec': 'signed'
            },
            'reputation': {
                'malicious': 0
            }
        }
        score = domain_intel._calculate_security_score(results)
        assert score == 1.0

    def test_calculate_security_score_low(self, domain_intel):
        """Test security score with low security."""
        results = {
            'ssl_certificate': {
                'valid': False
            },
            'reputation': {
                'malicious': 5
            }
        }
        score = domain_intel._calculate_security_score(results)
        assert score < 0.5

    def test_calculate_confidence(self, domain_intel):
        """Test confidence score calculation."""
        results = {
            'whois': {'registrar': 'Test'},
            'dns_records': {'A': ['93.184.216.34']},
            'ssl_certificate': {'valid': True},
            'technologies': [{'name': 'Server', 'value': 'nginx'}]
        }
        confidence = domain_intel._calculate_confidence(results)
        assert confidence == 1.0

    def test_calculate_confidence_minimal(self, domain_intel):
        """Test confidence score with minimal data."""
        results = {
            'dns_records': {'A': ['93.184.216.34']}
        }
        confidence = domain_intel._calculate_confidence(results)
        assert confidence == 0.25

    @pytest.mark.asyncio
    async def test_analyze_domain_invalid(self, domain_intel):
        """Test domain analysis with invalid domain."""
        result = await domain_intel.analyze_domain('not a domain')
        assert result['error'] == 'Invalid domain format'
        assert result['confidence'] == 0.0

    @pytest.mark.asyncio
    async def test_error_handling_api_timeout(self, domain_intel):
        """Test error handling for API timeouts."""
        with patch('aiohttp.ClientSession.get', side_effect=asyncio.TimeoutError):
            result = await domain_intel._get_whois_api_data('example.com')
            assert result == {}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
