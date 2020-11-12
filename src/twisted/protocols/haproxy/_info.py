# -*- test-case-name: twisted.protocols.haproxy.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
IProxyInfo implementation.
"""

from zope.interface import implementer
import attr

from twisted.internet.interfaces import IAddress

from ._interfaces import IProxyInfo


@implementer(IProxyInfo)
@attr.s(slots=True)
class ProxyInfo:
    """
    A data container for parsed PROXY protocol information.

    @ivar header: The raw header bytes extracted from the connection.
    @type header: bytes
    @ivar source: The connection source address.
    @type source: L{twisted.internet.interfaces.IAddress}
    @ivar destination: The connection destination address.
    @type destination: L{twisted.internet.interfaces.IAddress}
    """

    header = attr.ib(type=bytes)
    source = attr.ib(type=IAddress)
    destination = attr.ib(type=IAddress)
