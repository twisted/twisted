# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Address objects for network connections.
"""

import warnings, os

from zope.interface import implements

from twisted.internet.interfaces import IAddress
from twisted.python import util


class IPv4Address(object, util.FancyEqMixin):
    """
    Object representing an IPv4 socket endpoint.

    @ivar type: A string describing the type of transport, either 'TCP' or
        'UDP'.
    @ivar host: A string containing the dotted-quad IP address.
    @ivar port: An integer representing the port number.
    """

    implements(IAddress)

    compareAttributes = ('type', 'host', 'port')

    def __init__(self, type, host, port, _bwHack = None):
        assert type in ('TCP', 'UDP')
        self.type = type
        self.host = host
        self.port = port
        if _bwHack is not None:
            warnings.warn("twisted.internet.address.IPv4Address._bwHack is deprecated since Twisted 11.0",
                    DeprecationWarning, stacklevel=2)

    def __repr__(self):
        return 'IPv4Address(%s, %r, %d)' % (self.type, self.host, self.port)


    def __hash__(self):
        return hash((self.type, self.host, self.port))



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
            overriding L{util.FancyEqMixin} to ensure the os level samefile check
            is done if the name attributes do not match.
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
