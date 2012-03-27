# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Address objects for network connections.
"""

import warnings, os

from zope.interface import implements

from twisted.internet.interfaces import IAddress
from twisted.python import util


class _IPAddress(object, util.FancyEqMixin):
    """
    An L{_IPAddress} represents the address of an IP socket endpoint, providing
    common behavior for IPv4 and IPv6.

    @ivar type: A string describing the type of transport, either 'TCP' or
        'UDP'.

    @ivar host: A string containing the presentation format of the IP address;
        for example, "127.0.0.1" or "::1".
    @type host: C{str}

    @ivar port: An integer representing the port number.
    @type port: C{int}
    """

    implements(IAddress)

    compareAttributes = ('type', 'host', 'port')

    def __init__(self, type, host, port):
        assert type in ('TCP', 'UDP')
        self.type = type
        self.host = host
        self.port = port


    def __repr__(self):
        return '%s(%s, %r, %d)' % (
            self.__class__.__name__, self.type, self.host, self.port)


    def __hash__(self):
        return hash((self.type, self.host, self.port))



class IPv4Address(_IPAddress):
    """
    An L{IPv4Address} represents the address of an IPv4 socket endpoint.

    @ivar host: A string containing a dotted-quad IPv4 address; for example,
        "127.0.0.1".
    @type host: C{str}
    """

    def __init__(self, type, host, port, _bwHack=None):
        _IPAddress.__init__(self, type, host, port)
        if _bwHack is not None:
            warnings.warn("twisted.internet.address.IPv4Address._bwHack "
                          "is deprecated since Twisted 11.0",
                          DeprecationWarning, stacklevel=2)



class IPv6Address(_IPAddress):
    """
    An L{IPv6Address} represents the address of an IPv6 socket endpoint.

    @ivar host: A string containing a colon-separated, hexadecimal formatted
        IPv6 address; for example, "::1".
    @type host: C{str}
    """



class UNIXAddress(object, util.FancyEqMixin):
    """
    Object representing a UNIX socket endpoint.

    @ivar name: The filename associated with this socket.
    @type name: C{str}
    """

    implements(IAddress)

    compareAttributes = ('name', )

    def __init__(self, name, _bwHack = None):
        self.name = name
        if _bwHack is not None:
            warnings.warn("twisted.internet.address.UNIXAddress._bwHack is deprecated since Twisted 11.0",
                    DeprecationWarning, stacklevel=2)


    if getattr(os.path, 'samefile', None) is not None:
        def __eq__(self, other):
            """
            overriding L{util.FancyEqMixin} to ensure the os level samefile
            check is done if the name attributes do not match.
            """
            res = super(UNIXAddress, self).__eq__(other)
            if res == False:
                try:
                    return os.path.samefile(self.name, other.name)
                except OSError:
                    pass
            return res


    def __repr__(self):
        return 'UNIXAddress(%r)' % (self.name,)


    def __hash__(self):
        try:
            s1 = os.stat(self.name)
            return hash((s1.st_ino, s1.st_dev))
        except OSError:
            return hash(self.name)



# These are for buildFactory backwards compatability due to
# stupidity-induced inconsistency.

class _ServerFactoryIPv4Address(IPv4Address):
    """Backwards compatability hack. Just like IPv4Address in practice."""

    def __eq__(self, other):
        if isinstance(other, tuple):
            warnings.warn("IPv4Address.__getitem__ is deprecated.  Use attributes instead.",
                          category=DeprecationWarning, stacklevel=2)
            return (self.host, self.port) == other
        elif isinstance(other, IPv4Address):
            a = (self.type, self.host, self.port)
            b = (other.type, other.host, other.port)
            return a == b
        return False
