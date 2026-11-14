"""Unit/integration suite with all outbound socket connects prohibited."""

import asyncio
import socket
import unittest
from contextvars import ContextVar
from unittest.mock import patch

_internal_pair = ContextVar("internal_socketpair", default=False)
_connect = socket.socket.connect
_socketpair = socket.socketpair


def blocked(sock, address):
    # Windows implements asyncio's wake-up pipe with a local TCP socketpair.
    # Allow only that synchronous stdlib operation, never arbitrary loopback.
    if _internal_pair.get() and address[0] in ("127.0.0.1", "::1"):
        return _connect(sock, address)
    raise RuntimeError("Network connections are forbidden during automated trading tests")


def internal_socketpair(*args, **kwargs):
    token = _internal_pair.set(True)
    try:
        return _socketpair(*args, **kwargs)
    finally:
        _internal_pair.reset(token)


async def blocked_connection(*args, **kwargs):
    raise RuntimeError("Async network connections are forbidden during automated trading tests")


def main():
    with (
        patch.object(socket.socket, "connect", blocked),
        patch.object(socket.socket, "connect_ex", blocked),
        patch.object(socket, "socketpair", internal_socketpair),
        patch.object(asyncio.BaseEventLoop, "create_connection", blocked_connection),
        patch.object(asyncio.BaseEventLoop, "create_datagram_endpoint", blocked_connection),
    ):
        suite = unittest.defaultTestLoader.discover("tests")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
