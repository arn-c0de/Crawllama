"""Test API query input sanitization for HTML/event-handler payloads."""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app import QueryRequest, OSINTRequest


@pytest.mark.parametrize(
    "payload",
    [
        '<img src=x onerror="alert(1)">',
        "<svg/onload=alert(1)>",
        "<iframe src=javascript:alert(1)></iframe>",
    ],
)
def test_query_request_rejects_html_payloads(payload):
    """QueryRequest should reject HTML/XSS-like payloads."""
    with pytest.raises(ValidationError):
        QueryRequest(query=payload)


@pytest.mark.parametrize(
    "payload",
    [
        '<img src=x onerror="alert(1)">',
        "<svg/onload=alert(1)>",
    ],
)
def test_osint_request_rejects_html_payloads(payload):
    """OSINTRequest should reject HTML/XSS-like payloads."""
    with pytest.raises(ValidationError):
        OSINTRequest(query=payload)
