# Twisted, the Framework of Your Internet
# Copyright (C) 2002 Matthew W. Lefkowitz
# author: Bryce "Zooko" Wilcox-O'Hearn, 2002
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


import socket, types


class BindError(Exception):
    """An error occured binding to an interface."""


class CannotListenError(BindError):
    """This gets raised by a call to startListening, when the object cannot start listening."""
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
