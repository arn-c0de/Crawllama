"""Integration-test isolation overrides.

The integration API tests mock the heavy agent components and exercise the
endpoints without supplying credentials, so they intentionally run with the
development bypass enabled. This autouse fixture scopes that bypass to the
integration suite (overriding the repo-wide default of enforcement ON) and
restores the previous value afterwards.
"""
import os

import pytest


@pytest.fixture(autouse=True)
def _integration_dev_mode_on():
    prev = os.environ.get("CRAWLLAMA_DEV_MODE")
    os.environ["CRAWLLAMA_DEV_MODE"] = "true"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("CRAWLLAMA_DEV_MODE", None)
        else:
            os.environ["CRAWLLAMA_DEV_MODE"] = prev
