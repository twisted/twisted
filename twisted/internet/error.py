# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Exceptions and errors for use in twisted.internet modules.

API Stability: semi-stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

import socket, types


class BindError(Exception):
    """An error occurred binding to an interface"""

    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '%s: %s' % (s, ' '.join(self.args))
        s = '%s.' % s
        return s

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
        return "Couldn't listen on %s:%s: %s." % (iface, self.port,
                                                 self.socketError)


class MulticastJoinError(Exception):
    """
    An attempt to join a multicast group failed.
    """


class MessageLengthError(Exception):
    """Message is too long to send"""

    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '%s: %s' % (s, ' '.join(self.args))
        s = '%s.' % s
        return s


class DNSLookupError(IOError):
    """DNS lookup failed"""

    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '%s: %s' % (s, ' '.join(self.args))
        s = '%s.' % s
        return s


class ConnectInProgressError(Exception):
    """A connect operation was started and isn't done yet."""


# connection errors

class ConnectError(Exception):
    """An error occurred while connecting"""

    def __init__(self, osError=None, string=""):
        self.osError = osError
        Exception.__init__(self, string)

    def __str__(self):
        s = self.__doc__ or self.__class__.__name__
        if self.osError:
            s = '%s: %s' % (s, self.osError)
        if self[0]:
            s = '%s: %s' % (s, self[0])
        s = '%s.' % s
        return s


class ConnectBindError(ConnectError):
    """Couldn't bind"""


class UnknownHostError(ConnectError):
    """Hostname couldn't be looked up"""


class NoRouteError(ConnectError):
    """No route to host"""


class ConnectionRefusedError(ConnectError):
    """Connection was refused by other side"""


class TCPTimedOutError(ConnectError):
    """TCP connection timed out"""


class BadFileError(ConnectError):
    """File used for UNIX socket is no good"""


class ServiceNameUnknownError(ConnectError):
    """Service name given as port is unknown"""


class UserError(ConnectError):
    """User aborted connection"""


class TimeoutError(UserError):
    """User timeout caused connection failure"""

class SSLError(ConnectError):
    """An SSL error occurred"""

try:
    import errno
    errnoMapping = {
        errno.ENETUNREACH: NoRouteError,
        errno.ECONNREFUSED: ConnectionRefusedError,
        errno.ETIMEDOUT: TCPTimedOutError,
        # for FreeBSD - might make other unices in certain cases
        # return wrong exception, alas
        errno.EINVAL: ConnectionRefusedError,
    }
    if hasattr(errno, "WSAECONNREFUSED"):
        errnoMapping[errno.WSAECONNREFUSED] = ConnectionRefusedError
        errnoMapping[errno.WSAENETUNREACH] = NoRouteError
except ImportError:
    errnoMapping = {}

def getConnectError(e):
    """Given a socket exception, return connection error."""
    try:
        number, string = e
    except ValueError:
        return ConnectError(string=e)

    if hasattr(socket, 'gaierror') and isinstance(e, socket.gaierror):
        # only works in 2.2
        klass = UnknownHostError
    else:
        klass = errnoMapping.get(number, ConnectError)
    return klass(number, string)


class ConnectionLost(Exception):
    """Connection to the other side was lost in a non-clean fashion"""

    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '%s: %s' % (s, ' '.join(self.args))
        s = '%s.' % s
        return s


class ConnectionDone(Exception):
    """Connection was closed cleanly"""

    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '%s: %s' % (s, ' '.join(self.args))
        s = '%s.' % s
        return s


class ConnectionFdescWentAway(ConnectionLost):
    """Uh""" #TODO


class AlreadyCalled(ValueError):
    """Tried to cancel an already-called event"""

    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '%s: %s' % (s, ' '.join(self.args))
        s = '%s.' % s
        return s


class AlreadyCancelled(ValueError):
    """Tried to cancel an already-cancelled event"""

    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '%s: %s' % (s, ' '.join(self.args))
        s = '%s.' % s
        return s

class ProcessDone(ConnectionDone):
    """A process has ended without apparent errors"""

    def __init__(self, status):
        Exception.__init__(self, "process finished with exit code 0")
        self.exitCode = 0
        self.signal = None
        self.status = status


class ProcessTerminated(ConnectionLost):
    """A process has ended with a probable error condition"""

    def __init__(self, exitCode=None, signal=None, status=None):
        self.exitCode = exitCode
        self.signal = signal
        self.status = status
        s = "process ended"
        if exitCode is not None: s = s + " with exit code %s" % exitCode
        if signal is not None: s = s + " by signal %s" % signal
        Exception.__init__(self, s)


class ProcessExitedAlready(Exception):
    """The process has already excited, and the operation requested can no longer be performed."""


class NotConnectingError(RuntimeError):
    """The Connector was not connecting when it was asked to stop connecting"""

    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '%s: %s' % (s, ' '.join(self.args))
        s = '%s.' % s
        return s

class NotListeningError(RuntimeError):
    """The Port was not listening when it was asked to stop listening"""

    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '%s: %s' % (s, ' '.join(self.args))
        s = '%s.' % s
        return s
