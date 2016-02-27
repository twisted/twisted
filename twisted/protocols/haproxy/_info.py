# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
IProxyInfo implementation.
"""

import zope.interface

from . import _interfaces


class ProxyInfo(object):
    """
    A data container for parsed PROXY protocol information.

    @ivar header: The raw header bytes extracted from the connection.
    @type header: bytes
    @ivar source: The connection source address.
    @type source: L{twisted.internet.interfaces.IAddress}
    @ivar destination: The connection destination address.
    @type destination: L{twisted.internet.interfaces.IAddress}
    """

    zope.interface.implements(_interfaces.IProxyInfo)

    __slots__ = (
        'header',
        'source',
        'destination',
    )

    def __init__(self, header, source, destination):
        self.header = header
        self.source = source
        self.destination = destination
