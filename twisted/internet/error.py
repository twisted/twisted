# Twisted, the Framework of Your Internet
# Copyright (C) 2002 Matthew W. Lefkowitz
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

"""Exceptions and errors for use in twisted.internet modules.

API Stability: semi-stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

import socket, types


class BindError(Exception):
    """An error occured binding to an interface."""


class CannotListenError(BindError):
    """This gets raised by a call to startListening, when the object cannot start listening.

    @ivar interface: the interface I tried to listen on
    @ivar port: the port I tried to listen on
    @ivar socketError: the exception I got when I tried to listen
    @type socketError: L{socket.error}
    """
    def __init__(self, interface, port, socketError):
        BindError.__init__(self, interface, port, socketError)
        self.interface = interface
        self.port = port
        self.socketError = socketError

    def __str__(self):
        iface = self.interface or 'any'
        return "Couldn't listen on %s:%s: %s" % (iface, self.port,
                                                 self.socketError)

class MessageLengthError(Exception):
    """Message is too long to send."""
    pass


class DNSLookupError(IOError):
    """DNS lookup failed."""
    pass


# connection errors

class ConnectError(Exception):
    """An error that occured while connecting."""

    def __init__(self, osError=None, string=""):
        self.osError = osError
        Exception.__init__(self, string)


class ConnectBindError(ConnectError):
    """Couldn't bind."""


class UnknownHostError(ConnectError):
    """Hostname couldn't be looked up."""


class NoRouteError(ConnectError):
    """No route to host."""


class ConnectionRefusedError(ConnectError):
    """Connection was refused by other side."""


class TCPTimedOutError(ConnectError):
    """TCP connection timed out."""


class BadFileError(ConnectError):
    """File used for UNIX socket is no good."""


class ServiceNameUnknownError(ConnectError):
    """Service name given as port is unknown."""


class UserError(ConnectError):
    """User aborted connection."""


class TimeoutError(UserError):
    """User timeout caused connection failure."""


class SSLError(ConnectError):
    """An SSL error occured."""

try:
    import errno
    errnoMapping = {
        errno.ENETUNREACH: NoRouteError,
        errno.ECONNREFUSED: ConnectionRefusedError,
        errno.ETIMEDOUT: TCPTimedOutError,
    }
except ImportError:
    errnoMapping = {}

def getConnectError(e):
    """Given a socket exception, return connection error."""
    try:
        number, string = e
    except ValueError:
        return ConnectError(string=e)

    number, string = e
    if hasattr(socket, 'gaierror') and isinstance(e, socket.gaierror):
        # only works in 2.2
        klass = UnknownHostError
    else:
        klass = errnoMapping.get(number, ConnectError)
    return klass(number, string)


class ConnectionLost(Exception):
    """Connection to the other side was lost in a non-clean fashion."""


class ConnectionDone(Exception):
    """Connection was closed cleanly."""


class ConnectionFdescWentAway(ConnectionLost):
    """Uh."""


class AlreadyCalled(ValueError):
    """Tried to cancel an already-called event."""


class AlreadyCancelled(ValueError):
    """Tried to cancel an already-cancelled event."""


class ProcessDone(ConnectionDone):
    """A process has ended without apparent errors."""

    def __init__(self, status):
        Exception.__init__(self, "process finished with exit code 0")
        self.exitCode = 0
        self.status = status


class ProcessTerminated(ConnectionLost):
    """A process has ended with a probable error condition."""

    def __init__(self, exitCode=None, status=None):
        self.exitCode = exitCode
        self.status = status
        s = "process ended"
        if exitCode is not None: s = s + " with exit code %s" % exitCode
        Exception.__init__(self, s)

class NotConnectingError(RuntimeError):
    """The Connector was not connecting when it was asked to stop connecting."""
