"""Pytest tests for OSINT module - Category: osint"""
import pytest
from pathlib import Path
import sys
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.osint import (
    OSINTQueryParser,
    EmailIntelligence,
    PhoneIntelligence,
    DomainIntelligence,
    QueryEnhancer,
    OSINTCompliance
)
from core.llm_client import OllamaClient

class TestQueryParser:
    def test_parser_initialization(self):
        parser = OSINTQueryParser()
        assert parser is not None
    
    def test_parse_simple_query(self):
        parser = OSINTQueryParser()
        result = parser.parse("python programming")
        assert result is not None

class TestEmailIntelligence:
    def test_email_intel_initialization(self):
        email_intel = EmailIntelligence()
        assert email_intel is not None
    
    def test_valid_email_analysis(self):
        email_intel = EmailIntelligence()
        result = email_intel.analyze_email("test@example.com")
        assert result is not None
        assert isinstance(result, dict)
        assert "valid" in result
        # Email validation depends on DNS/MX records, so we just check structure
        assert "domain" in result
        assert "username" in result

class TestPhoneIntelligence:
    def test_phone_intel_initialization(self):
        phone_intel = PhoneIntelligence()
        assert phone_intel is not None
    
    def test_phone_analysis(self):
        phone_intel = PhoneIntelligence()
        result = phone_intel.analyze_phone("+49 151 12345678")
        assert result is not None
        assert isinstance(result, dict)

class TestDomainIntelligence:
    def test_domain_intel_initialization(self):
        domain_intel = DomainIntelligence()
        assert domain_intel is not None
    
    def test_domain_analysis(self):
        domain_intel = DomainIntelligence()
        result = domain_intel.analyze_domain("example.com")
        assert result is not None
        assert isinstance(result, dict)

class TestQueryEnhancer:
    def test_enhancer_initialization(self):
        # Mock LLM client for testing
        mock_llm = Mock(spec=OllamaClient)
        enhancer = QueryEnhancer(mock_llm)
        assert enhancer is not None
    
    def test_query_enhancement(self):
        # Mock LLM client
        mock_llm = Mock(spec=OllamaClient)
        # Mock the correct method name
        mock_llm.generate.return_value = "python development\npython coding\npython software"

        enhancer = QueryEnhancer(mock_llm)
        # Use an actual method that exists
        result = enhancer.generate_variations("python programming")
        assert result is not None
        assert isinstance(result, list)

class TestOSINTCompliance:
    def test_compliance_initialization(self):
        compliance = OSINTCompliance()
        assert compliance is not None
    
    def test_query_compliance_check(self):
        compliance = OSINTCompliance()
        result = compliance.check_query("site:github.com python")
        assert result is not None

class TestOSINTIntegration:
    def test_full_email_workflow(self):
        email_intel = EmailIntelligence()
        result = email_intel.analyze_email("test@example.com")
        assert result is not None

    def test_full_domain_workflow(self):
        domain_intel = DomainIntelligence()
        result = domain_intel.analyze_domain("example.com")
        assert result is not None
