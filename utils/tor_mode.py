"""Tor mode: route every outbound web request through a Tor SOCKS5 proxy.

When Tor mode is enabled (``TOR_MODE=1`` or the ``tor`` section in
``config.json``), all outbound HTTP(S) traffic — crawler, RAG/tool fetches,
OSINT lookups and cloud LLM calls — must go through the configured Tor
SOCKS proxy. Enforcement is layered (defense in depth):

1. Process environment: :func:`activate` exports ``HTTP_PROXY`` /
   ``HTTPS_PROXY`` / ``ALL_PROXY`` pointing at the Tor SOCKS proxy.
   ``requests`` (and every library built on it, e.g. ``wikipedia``) honors
   these for each call, so plain ``requests.get(...)`` call sites are covered
   without per-call wiring. ``NO_PROXY`` keeps loopback and private (RFC 1918)
   ranges direct: that traffic never leaves the machine or LAN — and Tor
   cannot reach it — so it is not an anonymity leak (Ollama stays usable).
2. Explicit wiring where environment variables cannot reach:
   aiohttp sessions use :func:`aiohttp_connector`, DDGS metasearch uses
   :func:`ddgs_proxy` (plus the ``DDGS_PROXY`` env var), cloud LLM SDKs use
   :func:`sdk_http_client`, and ``SafeFetcher`` passes
   :func:`requests_proxies` explicitly.
3. DNS: the proxy URL uses the ``socks5h`` scheme and SOCKS connectors use
   remote DNS, so hostnames resolve at the Tor exit, never locally. Code that
   would resolve locally (SSRF pre-resolution, reverse DNS) checks
   :func:`is_tor_enabled` and skips the local lookup.

The failure mode is closed: if SOCKS support is missing or Tor is
unreachable, requests fail — they never fall back to a direct connection.
"""
import ipaddress
import os
from dataclasses import dataclass

from utils.logger import Logger

logger = Logger.get(__name__)

# Environment variables (take precedence over config.json)
ENV_TOR_MODE = "TOR_MODE"
ENV_SOCKS_HOST = "TOR_SOCKS_HOST"
ENV_SOCKS_PORT = "TOR_SOCKS_PORT"

DEFAULT_SOCKS_HOST = "127.0.0.1"
DEFAULT_SOCKS_PORT = 9050

# Official Tor Project endpoint that reports whether the request arrived
# through a Tor exit node.
TOR_CHECK_URL = "https://check.torproject.org/api/ip"
TOR_CHECK_TIMEOUT = 30  # seconds; circuits can be slow to build

# Hosts/networks that stay direct: this traffic never leaves the machine or
# LAN, and Tor exits cannot route back into it anyway.
LOCAL_BYPASS_HOSTS = (
    "localhost",
    "127.0.0.1",
    "::1",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
)

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

# Proxy-related variables exported by activate() and restored by deactivate().
_MANAGED_ENV_VARS = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "DDGS_PROXY",
)


class TorError(Exception):
    """Base error for Tor mode."""


class TorConfigurationError(TorError):
    """Tor mode is misconfigured or a required dependency is missing."""


class TorUnavailableError(TorError):
    """Tor mode is enabled but the Tor network is not reachable."""


@dataclass(frozen=True)
class TorConfig:
    """Resolved Tor mode configuration."""

    enabled: bool = False
    socks_host: str = DEFAULT_SOCKS_HOST
    socks_port: int = DEFAULT_SOCKS_PORT

    @property
    def proxy_url(self) -> str:
        """SOCKS proxy URL with remote DNS (socks5h = resolve at the exit)."""
        return f"socks5h://{self.socks_host}:{self.socks_port}"


# Module state: the configuration applied by activate(), the precomputed
# proxy mapping (requests_proxies() runs on every fetch), plus the environment
# values activate() replaced (so deactivate() can restore them, mainly tests).
_active_config: TorConfig | None = None
_active_proxies: dict[str, str] = {}
_saved_env: dict[str, str | None] = {}


def _env_flag(name: str) -> bool | None:
    """Read a boolean env var; None if unset/empty."""
    value = os.getenv(name)
    if not (value and value.strip()):
        return None
    return value.strip().lower() in _TRUE_VALUES


def load_tor_config(app_config: dict | None = None) -> TorConfig:
    """Build a :class:`TorConfig` from environment variables and config.json.

    Environment variables (``TOR_MODE``, ``TOR_SOCKS_HOST``,
    ``TOR_SOCKS_PORT``) take precedence over the ``tor`` section of the
    application config.

    Raises:
        TorConfigurationError: If the SOCKS port is not a valid port number.
    """
    tor_section = (app_config or {}).get("tor", {})

    env_enabled = _env_flag(ENV_TOR_MODE)
    enabled = env_enabled if env_enabled is not None else bool(tor_section.get("enabled", False))

    host = os.getenv(ENV_SOCKS_HOST) or tor_section.get("socks_host") or DEFAULT_SOCKS_HOST
    raw_port = os.getenv(ENV_SOCKS_PORT) or tor_section.get("socks_port") or DEFAULT_SOCKS_PORT

    try:
        port = int(raw_port)
        if not 1 <= port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        raise TorConfigurationError(f"Invalid Tor SOCKS port: {raw_port!r}") from None

    return TorConfig(enabled=enabled, socks_host=host.strip(), socks_port=port)


def activate(config: TorConfig) -> None:
    """Enable Tor mode process-wide.

    Exports proxy environment variables so that every ``requests``-based call
    site (including third-party libraries) routes through Tor, and records the
    configuration for the explicit integration points (aiohttp, DDGS, SDKs).
    """
    global _active_config, _active_proxies

    if not config.enabled:
        raise TorConfigurationError("activate() called with a disabled TorConfig")

    _save_env()

    existing_no_proxy = [h.strip() for h in os.getenv("NO_PROXY", "").split(",") if h.strip()]
    no_proxy = ",".join(dict.fromkeys([*LOCAL_BYPASS_HOSTS, *existing_no_proxy]))

    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        os.environ[var] = config.proxy_url
        os.environ[var.lower()] = config.proxy_url
    os.environ["NO_PROXY"] = no_proxy
    os.environ["no_proxy"] = no_proxy
    os.environ["DDGS_PROXY"] = config.proxy_url

    _active_config = config
    _active_proxies = {"http": config.proxy_url, "https": config.proxy_url}
    logger.info(f"Tor mode ACTIVE: all web traffic routed via {config.proxy_url}")


def deactivate() -> None:
    """Disable Tor mode and restore the previous proxy environment."""
    global _active_config, _active_proxies
    _restore_env()
    _active_config = None
    _active_proxies = {}
    logger.info("Tor mode deactivated")


def _save_env() -> None:
    """Remember the proxy environment as it was before activation."""
    global _saved_env
    _saved_env = {var: os.environ.get(var) for var in _MANAGED_ENV_VARS}


def _restore_env() -> None:
    """Restore the proxy environment saved by :func:`_save_env`."""
    for var, value in _saved_env.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value
    _saved_env.clear()


def is_tor_enabled() -> bool:
    """Whether Tor mode is currently active in this process."""
    return _active_config is not None


def get_tor_config() -> TorConfig | None:
    """The active Tor configuration, or None when Tor mode is off."""
    return _active_config


def proxy_url() -> str | None:
    """The Tor SOCKS proxy URL, or None when Tor mode is off."""
    return _active_config.proxy_url if _active_config else None


def requests_proxies() -> dict[str, str]:
    """Proxy mapping for ``requests`` calls; empty when Tor mode is off.

    Returns the shared, precomputed mapping — treat it as read-only.
    """
    return _active_proxies


def ddgs_proxy() -> str | None:
    """Proxy URL for the DDGS metasearch client; None when Tor mode is off."""
    return proxy_url()


def aiohttp_connector():
    """SOCKS connector for ``aiohttp.ClientSession``; None when Tor mode is off.

    Uses remote DNS (rdns=True) so hostnames resolve at the Tor exit.

    Raises:
        TorConfigurationError: If aiohttp-socks is not installed.
    """
    if _active_config is None:
        return None
    try:
        from aiohttp_socks import ProxyConnector
    except ImportError:
        raise TorConfigurationError(
            "Tor mode requires the 'aiohttp-socks' package. Run: uv sync"
        ) from None
    return ProxyConnector.from_url(_active_config.proxy_url, rdns=True)


def sdk_http_client():
    """``httpx.Client`` routed through Tor for cloud LLM SDKs; None when off.

    OpenAI, Anthropic and Groq SDKs all accept an ``http_client`` argument.

    Raises:
        TorConfigurationError: If httpx SOCKS support is not installed.
    """
    if _active_config is None:
        return None
    try:
        import httpx
        import socksio  # noqa: F401  # httpx needs it for socks5 transports
    except ImportError:
        raise TorConfigurationError(
            "Tor mode with cloud LLM providers requires 'httpx[socks]'. "
            "Run: uv sync --extra <provider>"
        ) from None
    return httpx.Client(proxy=_active_config.proxy_url)


def is_local_bypass_host(hostname: str) -> bool:
    """Whether a hostname stays direct (loopback or private network) in Tor mode."""
    if hostname in ("localhost",):
        return True
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def verify_tor_connectivity(timeout: int = TOR_CHECK_TIMEOUT) -> str:
    """Verify that traffic actually exits through the Tor network.

    Fetches the Tor Project's check API through the configured proxy and
    requires it to confirm a Tor exit. Called on startup so a broken Tor
    setup fails fast instead of leaking traffic later.

    Returns:
        The observed Tor exit IP address.

    Raises:
        TorUnavailableError: If the proxy is unreachable or the response does
            not confirm a Tor exit.
        TorConfigurationError: If Tor mode is not active.
    """
    if _active_config is None:
        raise TorConfigurationError("verify_tor_connectivity() requires active Tor mode")

    import requests

    try:
        response = requests.get(
            TOR_CHECK_URL,
            proxies=requests_proxies(),
            timeout=timeout,
            headers={"User-Agent": "CrawlLama/1.0 Tor-Check"},
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as e:
        raise TorUnavailableError(
            f"Tor mode is enabled but the Tor network is unreachable via "
            f"{_active_config.proxy_url} ({type(e).__name__}). "
            f"Is the Tor service running?"
        ) from e
    except ValueError as e:
        raise TorUnavailableError("Tor check returned an invalid response") from e

    if not payload.get("IsTor"):
        raise TorUnavailableError(
            "Traffic through the configured SOCKS proxy does NOT exit via Tor. "
            "Refusing to start to prevent IP leaks."
        )

    exit_ip = str(payload.get("IP", "unknown"))
    logger.info(f"Tor circuit verified: exit IP {exit_ip}")
    return exit_ip


def initialize_tor_mode(app_config: dict | None = None) -> TorConfig:
    """Load, activate and verify Tor mode from configuration (startup hook).

    No-op when Tor mode is disabled. When enabled, activates process-wide
    routing and fails fast if the Tor network cannot be confirmed.

    Returns:
        The resolved TorConfig (``enabled`` tells whether Tor mode is on).

    Raises:
        TorConfigurationError: On invalid configuration.
        TorUnavailableError: If Tor is enabled but unreachable.
    """
    config = load_tor_config(app_config)
    if not config.enabled:
        return config

    activate(config)
    try:
        verify_tor_connectivity()
    except TorError:
        # Never leave half-activated proxy state behind on failure.
        deactivate()
        raise
    return config
