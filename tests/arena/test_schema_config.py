"""Schema strictness and config fingerprinting."""

import pytest
from pydantic import ValidationError

from arena.config import config_hash, redact_secrets
from arena.schema import Scenario


def test_scenario_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Scenario.model_validate(
            {"id": "x", "driver": "mock", "typo_field": True}
        )


def test_scenario_rejects_unknown_driver():
    with pytest.raises(ValidationError):
        Scenario.model_validate({"id": "x", "driver": "not-a-driver"})


def test_scenario_roundtrip_json():
    s = Scenario.model_validate({"id": "x", "driver": "mock", "input": {"answer": "hi"}})
    again = Scenario.model_validate_json(s.model_dump_json())
    assert again == s


def test_redact_secrets_masks_secret_keys():
    red = redact_secrets({"OPENAI_API_KEY": "sk-real", "model": "qwen", "nested": {"token": ""}})
    assert red["OPENAI_API_KEY"] == "present"
    assert red["model"] == "qwen"
    assert red["nested"]["token"] == "absent"


def test_config_hash_is_stable_and_secret_independent():
    a = config_hash({"model": "qwen", "OPENAI_API_KEY": "sk-aaa"})
    b = config_hash({"model": "qwen", "OPENAI_API_KEY": "sk-bbb-different"})
    c = config_hash({"model": "llama", "OPENAI_API_KEY": "sk-aaa"})
    assert a == b  # secret value does not affect the hash
    assert a != c  # behaviour-relevant value does
    assert a.startswith("sha256:")
