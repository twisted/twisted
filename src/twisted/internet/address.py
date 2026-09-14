# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Address objects for network connections.
"""


import os
from typing import Literal

from zope.interface import implementer

import attr

from twisted.internet.interfaces import IAddress
from twisted.python.filepath import _asFilesystemBytes, _coerceToFilesystemEncoding
from twisted.python.runtime import platform


@implementer(IAddress)
@attr.s(unsafe_hash=True, auto_attribs=True)
class IPv4Address:
    """
    An L{IPv4Address} represents the address of an IPv4 socket endpoint.

    @ivar type: A string describing the type of transport, either 'TCP' or
        'UDP'.

    @ivar host: A string containing a dotted-quad IPv4 address; for example,
        "127.0.0.1".

    @ivar port: An integer representing the port number.
    """

    type: Literal["TCP"] | Literal["UDP"] = attr.ib(
        validator=attr.validators.in_(["TCP", "UDP"])
    )
    host: str
    port: int


@implementer(IAddress)
@attr.s(unsafe_hash=True, auto_attribs=True)
class IPv6Address:
    """
    An L{IPv6Address} represents the address of an IPv6 socket endpoint.

    @ivar type: A string describing the type of transport, either 'TCP' or
        'UDP'.

    @ivar host: A string containing a colon-separated, hexadecimal formatted
        IPv6 address; for example, "::1".

    @ivar port: An integer representing the port number.

    @ivar flowInfo: the IPv6 flow label.  This can be used by QoS routers to
        identify flows of traffic; you may generally safely ignore it.

    @ivar scopeID: the IPv6 scope identifier - roughly analagous to what
        interface traffic destined for this address must be transmitted over.
    """

    type: Literal["TCP"] | Literal["UDP"] = attr.ib(
        validator=attr.validators.in_(["TCP", "UDP"])
    )
    host: str
    port: int
    flowInfo: int = 0
    scopeID: str | int = 0


@implementer(IAddress)
class _ProcessAddress:
    """
    An L{interfaces.IAddress} provider for process transports.
    """


@attr.s(unsafe_hash=True, auto_attribs=True)
@implementer(IAddress)
class HostnameAddress:
    """
    A L{HostnameAddress} represents the address of a L{HostnameEndpoint}.

    @ivar hostname: A hostname byte string; for example, b"example.com".

    @ivar port: An integer representing the port number.
    """

    hostname: bytes
    port: int


@attr.s(unsafe_hash=False, repr=False, eq=False, auto_attribs=True)
@implementer(IAddress)
class UNIXAddress:
    """
    Object representing a UNIX socket endpoint.

    @ivar name: The filename associated with this socket.
    """

    name: bytes | None = attr.ib(converter=attr.converters.optional(_asFilesystemBytes))

    def __eq__(self, other: object) -> bool:
        """
        Overriding C{attrs} to ensure the os level samefile
        check is done if the name attributes do not match.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented
        res = self.name == other.name
        if not res and self.name and other.name:
            try:
                return os.path.samefile(self.name, other.name)
            except OSError:
                pass
            except (TypeError, ValueError) as e:
                # On Linux, abstract namespace UNIX sockets start with a
                # \0, which os.path doesn't like.
                if not platform.isLinux():
                    raise e
        return res

    def __repr__(self) -> str:
        name = self.name
        show = _coerceToFilesystemEncoding("", name) if name is not None else None
        return f"UNIXAddress({show!r})"

    def __hash__(self) -> int:
        if self.name is None:
            return hash((self.__class__, None))
        try:
            s1 = os.stat(self.name)
            return hash((s1.st_ino, s1.st_dev))
        except OSError:
            return hash(self.name)
