"""Tests for Tor mode (utils.tor_mode): config, activation, verification, leak guards."""
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from utils import tor_mode
from utils.tor_mode import (
    TorConfig,
    TorConfigurationError,
    TorUnavailableError,
    load_tor_config,
)

TOR_ENV_VARS = (
    tor_mode.ENV_TOR_MODE,
    tor_mode.ENV_SOCKS_HOST,
    tor_mode.ENV_SOCKS_PORT,
)


@pytest.fixture(autouse=True)
def _clean_tor_state():
    """Run each test with Tor mode off and a clean proxy environment."""
    saved = {var: os.environ.get(var) for var in (*TOR_ENV_VARS, *tor_mode._MANAGED_ENV_VARS)}
    for var in saved:
        os.environ.pop(var, None)
    yield
    if tor_mode.is_tor_enabled():
        tor_mode.deactivate()
    for var, value in saved.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value


def _activate(host: str = "127.0.0.1", port: int = 9050) -> TorConfig:
    config = TorConfig(enabled=True, socks_host=host, socks_port=port)
    tor_mode.activate(config)
    return config


class TestLoadTorConfig:
    def test_disabled_by_default(self):
        config = load_tor_config({})
        assert config.enabled is False
        assert config.socks_host == "127.0.0.1"
        assert config.socks_port == 9050

    def test_enabled_via_env_var(self):
        os.environ[tor_mode.ENV_TOR_MODE] = "1"
        assert load_tor_config({}).enabled is True

    def test_enabled_via_config_section(self):
        config = load_tor_config({"tor": {"enabled": True}})
        assert config.enabled is True

    def test_env_var_overrides_config_section(self):
        os.environ[tor_mode.ENV_TOR_MODE] = "0"
        config = load_tor_config({"tor": {"enabled": True}})
        assert config.enabled is False

    def test_empty_env_var_falls_back_to_config(self):
        os.environ[tor_mode.ENV_TOR_MODE] = ""
        config = load_tor_config({"tor": {"enabled": True}})
        assert config.enabled is True

    def test_custom_host_and_port(self):
        config = load_tor_config({"tor": {"socks_host": "10.0.0.5", "socks_port": 9150}})
        assert config.socks_host == "10.0.0.5"
        assert config.socks_port == 9150

    def test_env_host_port_override_config(self):
        os.environ[tor_mode.ENV_SOCKS_HOST] = "192.168.1.2"
        os.environ[tor_mode.ENV_SOCKS_PORT] = "9999"
        config = load_tor_config({"tor": {"socks_host": "10.0.0.5", "socks_port": 9150}})
        assert config.socks_host == "192.168.1.2"
        assert config.socks_port == 9999

    @pytest.mark.parametrize("bad_port", ["abc", "0", "70000", "-1"])
    def test_invalid_port_raises(self, bad_port):
        os.environ[tor_mode.ENV_SOCKS_PORT] = bad_port
        with pytest.raises(TorConfigurationError):
            load_tor_config({})

    def test_proxy_url_uses_remote_dns_scheme(self):
        config = TorConfig(enabled=True, socks_host="127.0.0.1", socks_port=9050)
        assert config.proxy_url == "socks5h://127.0.0.1:9050"


class TestActivation:
    def test_activate_sets_state_and_environment(self):
        config = _activate()

        assert tor_mode.is_tor_enabled() is True
        assert tor_mode.get_tor_config() == config
        assert tor_mode.proxy_url() == "socks5h://127.0.0.1:9050"
        for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "DDGS_PROXY"):
            assert os.environ[var] == "socks5h://127.0.0.1:9050"
        # Loopback and private ranges stay direct (Ollama, LAN services)
        assert "localhost" in os.environ["NO_PROXY"]
        assert "192.168.0.0/16" in os.environ["NO_PROXY"]

    def test_activate_preserves_existing_no_proxy_entries(self):
        os.environ["NO_PROXY"] = "internal.example"
        _activate()
        assert "internal.example" in os.environ["NO_PROXY"]

    def test_activate_rejects_disabled_config(self):
        with pytest.raises(TorConfigurationError):
            tor_mode.activate(TorConfig(enabled=False))

    def test_deactivate_restores_environment(self):
        os.environ["HTTPS_PROXY"] = "http://corp-proxy:8080"
        _activate()
        tor_mode.deactivate()

        assert tor_mode.is_tor_enabled() is False
        assert os.environ["HTTPS_PROXY"] == "http://corp-proxy:8080"
        assert "HTTP_PROXY" not in os.environ

    def test_helpers_inactive_when_off(self):
        assert tor_mode.is_tor_enabled() is False
        assert tor_mode.proxy_url() is None
        assert tor_mode.requests_proxies() == {}
        assert tor_mode.ddgs_proxy() is None
        assert tor_mode.aiohttp_connector() is None
        assert tor_mode.sdk_http_client() is None

    def test_requests_proxies_when_active(self):
        _activate(port=9150)
        assert tor_mode.requests_proxies() == {
            "http": "socks5h://127.0.0.1:9150",
            "https": "socks5h://127.0.0.1:9150",
        }


class TestLocalBypass:
    @pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", "192.168.178.100", "10.1.2.3"])
    def test_local_hosts_bypass(self, host):
        assert tor_mode.is_local_bypass_host(host) is True

    @pytest.mark.parametrize("host", ["example.com", "8.8.8.8", "1.1.1.1"])
    def test_public_hosts_do_not_bypass(self, host):
        assert tor_mode.is_local_bypass_host(host) is False


class TestVerifyTorConnectivity:
    def test_requires_active_tor_mode(self):
        with pytest.raises(TorConfigurationError):
            tor_mode.verify_tor_connectivity()

    def test_success_returns_exit_ip(self):
        _activate()
        response = MagicMock()
        response.json.return_value = {"IsTor": True, "IP": "185.220.101.5"}
        with patch("requests.get", return_value=response) as mock_get:
            exit_ip = tor_mode.verify_tor_connectivity()

        assert exit_ip == "185.220.101.5"
        _, kwargs = mock_get.call_args
        assert kwargs["proxies"]["https"] == "socks5h://127.0.0.1:9050"

    def test_non_tor_exit_fails(self):
        _activate()
        response = MagicMock()
        response.json.return_value = {"IsTor": False, "IP": "203.0.113.7"}
        with patch("requests.get", return_value=response):
            with pytest.raises(TorUnavailableError):
                tor_mode.verify_tor_connectivity()

    def test_unreachable_proxy_fails(self):
        _activate()
        with patch("requests.get", side_effect=requests.ConnectionError("refused")):
            with pytest.raises(TorUnavailableError, match="unreachable"):
                tor_mode.verify_tor_connectivity()


class TestInitializeTorMode:
    def test_noop_when_disabled(self):
        config = tor_mode.initialize_tor_mode({})
        assert config.enabled is False
        assert tor_mode.is_tor_enabled() is False

    def test_activates_and_verifies_when_enabled(self):
        response = MagicMock()
        response.json.return_value = {"IsTor": True, "IP": "185.220.101.5"}
        with patch("requests.get", return_value=response):
            config = tor_mode.initialize_tor_mode({"tor": {"enabled": True}})

        assert config.enabled is True
        assert tor_mode.is_tor_enabled() is True

    def test_failed_verification_deactivates_and_raises(self):
        with patch("requests.get", side_effect=requests.ConnectionError("refused")):
            with pytest.raises(TorUnavailableError):
                tor_mode.initialize_tor_mode({"tor": {"enabled": True}})

        # Fail fast must not leave a half-activated proxy environment behind
        assert tor_mode.is_tor_enabled() is False
        assert "HTTP_PROXY" not in os.environ


class TestLeakGuards:
    """Integration points must route through Tor / skip local DNS when active."""

    def test_safe_fetcher_uses_tor_proxies(self):
        from utils.safe_fetch import SafeFetcher

        fetcher = SafeFetcher(use_proxy=False)
        _activate()
        kwargs: dict = {}
        fetcher._prepare_headers_and_proxy("https://example.com", kwargs)
        assert kwargs["proxies"] == tor_mode.requests_proxies()

    def test_safe_fetcher_tor_overrides_configured_proxy(self):
        os.environ["HTTPS_PROXY"] = "http://corp-proxy:8080"
        from utils.safe_fetch import SafeFetcher

        fetcher = SafeFetcher(use_proxy=True)
        _activate()
        kwargs: dict = {}
        fetcher._prepare_headers_and_proxy("https://example.com", kwargs)
        assert kwargs["proxies"]["https"] == "socks5h://127.0.0.1:9050"

    def test_ssrf_validation_skips_local_dns_in_tor_mode(self):
        from utils.validators import validate_url_ssrf_safe

        _activate()
        with patch("utils.validators._resolve_hostname_with_timeout") as mock_resolve:
            is_safe, error = validate_url_ssrf_safe("https://example.com/page")

        assert is_safe is True
        assert error is None
        mock_resolve.assert_not_called()

    def test_ssrf_validation_still_blocks_dangerous_targets_in_tor_mode(self):
        from utils.validators import validate_url_ssrf_safe

        _activate()
        for url in (
            "ftp://example.com/file",        # non-HTTP scheme
            "http://localhost/admin",        # blocked hostname
            "http://127.0.0.1/admin",        # loopback IP literal
            "http://169.254.169.254/latest", # cloud metadata IP literal
            "http://192.168.1.1/router",     # private IP literal
        ):
            is_safe, _ = validate_url_ssrf_safe(url)
            assert is_safe is False, f"expected {url} to be blocked"

    def test_aiohttp_connector_uses_remote_dns(self):
        pytest.importorskip("aiohttp_socks")
        _activate()
        with patch("aiohttp_socks.ProxyConnector.from_url") as mock_from_url:
            tor_mode.aiohttp_connector()
        mock_from_url.assert_called_once_with("socks5h://127.0.0.1:9050", rdns=True)

    def test_email_intel_skips_local_dns(self):
        from core.osint.email_intel import EmailIntelligence

        _activate()
        intel = EmailIntelligence()
        with patch("socket.gethostbyname") as mock_resolve:
            result = intel.check_mx_records("example.com")
        mock_resolve.assert_not_called()
        assert "skipped" in result[0]

    def test_domain_intel_skips_local_address_resolution(self):
        from core.osint.domain_intel import DomainIntelligence

        _activate()
        intel = DomainIntelligence()
        with patch("socket.getaddrinfo") as mock_resolve:
            assert intel._resolve_a_records("example.com") == []
            assert intel._resolve_aaaa_records("example.com") == []
        mock_resolve.assert_not_called()

    def test_domain_intel_skips_dnspython_lookups(self):
        from core.osint.domain_intel import DomainIntelligence

        _activate()
        intel = DomainIntelligence()
        # Guard must short-circuit before dnspython is even imported
        assert intel._resolve_mx_records("example.com") == []
        assert intel._resolve_txt_records("example.com") == []
        assert intel._resolve_ns_records("example.com") == []
        assert intel._resolve_cname_records("example.com") == []

    def test_domain_intel_skips_reverse_dns(self):
        from core.osint.domain_intel import DomainIntelligence

        _activate()
        intel = DomainIntelligence()
        with patch("socket.gethostbyaddr") as mock_resolve:
            assert intel._reverse_dns_lookup("93.184.216.34") is None
        mock_resolve.assert_not_called()

    def test_domain_intel_skips_raw_socket_ssl_check(self):
        from core.osint.domain_intel import DomainIntelligence

        _activate()
        intel = DomainIntelligence()
        with patch("socket.socket") as mock_socket:
            ssl_info = intel._get_ssl_hints("example.com")
        mock_socket.assert_not_called()
        assert ssl_info["port_443_open"] is False
        assert "Tor mode" in ssl_info["note"]
