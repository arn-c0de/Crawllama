"""Network guard for deterministic (``pure``/``replay``) runs.

In these fixture modes an unexpected outbound connection is a hard failure — the
web must be frozen so that only code+model vary (plan §7, §20). :func:`block_network`
patches the socket layer to raise :class:`NetworkAccessError` on any connect,
optionally allowing an explicit host allowlist (e.g. a local replay server).

Loopback is *not* allowed by default: a deterministic arena scenario should not
be talking to a local Ollama either. Pass ``allow_hosts={"127.0.0.1"}`` if a
scenario legitimately needs a local fixture server.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from contextlib import contextmanager


class NetworkAccessError(RuntimeError):
    """Raised when code attempts a network connection under :func:`block_network`."""


def _host_of(address: object) -> str:
    if isinstance(address, tuple) and address:
        return str(address[0])
    return str(address)


@contextmanager
def block_network(allow_hosts: set[str] | None = None) -> Iterator[None]:
    """Block all outbound socket connections for the duration of the block."""
    allow = allow_hosts or set()
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create_connection = socket.create_connection

    def guarded_connect(self, address, *args, **kwargs):
        host = _host_of(address)
        if host not in allow:
            raise NetworkAccessError(f"network access to {address!r} blocked in replay/pure mode")
        return real_connect(self, address, *args, **kwargs)

    def guarded_connect_ex(self, address, *args, **kwargs):
        host = _host_of(address)
        if host not in allow:
            raise NetworkAccessError(f"network access to {address!r} blocked in replay/pure mode")
        return real_connect_ex(self, address, *args, **kwargs)

    def guarded_create_connection(address, *args, **kwargs):
        host = _host_of(address)
        if host not in allow:
            raise NetworkAccessError(f"network access to {address!r} blocked in replay/pure mode")
        return real_create_connection(address, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.create_connection = guarded_create_connection
    try:
        yield
    finally:
        socket.socket.connect = real_connect
        socket.socket.connect_ex = real_connect_ex
        socket.create_connection = real_create_connection
