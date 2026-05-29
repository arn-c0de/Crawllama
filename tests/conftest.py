"""Shared pytest fixtures and test isolation.

Historically ``tests/integration/test_api.py`` set ``CRAWLLAMA_DEV_MODE=true``
at import time, which leaked process-wide and silently disabled
authentication/CSRF/RBAC enforcement in the security test suite (so those
tests could not actually validate the protections). This autouse fixture makes
each test start with enforcement ON by default; suites that genuinely need the
development bypass (e.g. integration) re-enable it via their own conftest.
"""
import os

import pytest


@pytest.fixture(autouse=True)
def _default_dev_mode_off():
    """Run each test with auth/CSRF/RBAC enforcement ON by default."""
    prev = os.environ.get("CRAWLLAMA_DEV_MODE")
    os.environ["CRAWLLAMA_DEV_MODE"] = "false"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("CRAWLLAMA_DEV_MODE", None)
        else:
            os.environ["CRAWLLAMA_DEV_MODE"] = prev
