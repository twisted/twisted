# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Address objects for network connections."""

import warnings, os
from twisted.internet.interfaces import IAddress


class IPv4Address(object):
    """
    Object representing an IPv4 socket endpoint.

    @ivar type: A string describing the type of transport, either 'TCP' or 'UDP'.
    @ivar host: A string containing the dotted-quad IP address.
    @ivar port: An integer representing the port number.
    """

    __implements__ = IAddress,
    
    def __init__(self, type, host, port, _bwHack = None):
        assert type in ('TCP', 'UDP')
        self.type = type
        self.host = host
        self.port = port
        self._bwHack = _bwHack

    def __getitem__(self, index):
        warnings.warn("IPv4Address.__getitem__ is deprecated.  Use attributes instead.",
                      category=DeprecationWarning, stacklevel=2)
        return (self._bwHack or self.type, self.host, self.port).__getitem__(index)

    def __getslice__(self, start, stop):
        warnings.warn("IPv4Address.__getitem__ is deprecated.  Use attributes instead.",
                      category=DeprecationWarning, stacklevel=2)
        return (self._bwHack or self.type, self.host, self.port)[start:stop]

    def __eq__(self, other):
        if isinstance(other, tuple):
            return tuple(self) == other
        elif isinstance(other, IPv4Address):
            a = (self.type, self.host, self.port)
            b = (other.type, other.host, other.port)
            return a == b
        return False

    def __str__(self):
        return 'IPv4Address(%s, %r, %d)' % (self.type, self.host, self.port)


class UNIXAddress(object):
    """
    Object representing a UNIX socket endpoint.

    @ivar name: The filename associated with this socket.
    @type name: C{str}
    """

    __implements__ = IAddress,
    
    def __init__(self, name, _bwHack='UNIX'):
        self.name = name
        self._bwHack = _bwHack
    
    def __getitem__(self, index):
        warnings.warn("UNIXAddress.__getitem__ is deprecated.  Use attributes instead.",
                      category=DeprecationWarning, stacklevel=2)
        return (self._bwHack, self.name).__getitem__(index)

    def __getslice__(self, start, stop):
        warnings.warn("UNIXAddress.__getitem__ is deprecated.  Use attributes instead.",
                      category=DeprecationWarning, stacklevel=2)
        return (self._bwHack, self.name)[start:stop]

    def __eq__(self, other):
        if isinstance(other, tuple):
            return tuple(self) == other
        elif isinstance(other, UNIXAddress):
            try:
                return os.path.samefile(self.name, other.name)
            except OSError:
                pass
        return False

    def __str__(self):
        return 'UNIXSocket(%r)' % (self.name,)


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
