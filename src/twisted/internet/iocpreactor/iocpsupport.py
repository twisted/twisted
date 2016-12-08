# -*- test-case-name: twisted.internet.test.test_iocp -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A shim to the underlying IOCP support code.

See U{https://github.com/twisted/twisted-platform-support}.
"""

from _twisted_platform_support._iocp import (
    Event, CompletionPort,
    connect, accept, have_connectex,
    recv, recvfrom, send,
    maxAddrLen, get_accept_addrs, makesockaddr)

__all__ = [
    "Event", "CompletionPort", "connect", "accept", "have_connectex", "recv",
    "recvfrom", "send", "maxAddrLen", "get_accept_addrs", "makesockaddr"
]
