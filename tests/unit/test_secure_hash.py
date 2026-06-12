from utils.secure_hash import hmac_sha256_hex


def test_hmac_deterministic():
    key = b"\x01" * 32
    val = "user@example.com"
    h1 = hmac_sha256_hex(val, key=key)
    h2 = hmac_sha256_hex(val, key=key)
    assert h1 == h2
    assert len(h1) == 64


def test_hmac_truncate():
    key = b"\x02" * 32
    val = "+15551234567"
    h = hmac_sha256_hex(val, key=key, length=8)
    assert len(h) == 8


def test_env_key_override(monkeypatch):
    monkeypatch.setenv("HMAC_KEY", "env-secret-key")
    val = "some-value"
    h = hmac_sha256_hex(val)
    assert isinstance(h, str)
    assert len(h) == 64
