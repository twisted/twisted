# -*- test-case-name: twisted.conch.test.test_session -*-
# Copyright (c) 2001-2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module contains the implementation of SSHSession, which (by default)
allows access to a shell and a python interpreter over SSH.

For more information see RFC 4254.

Maintainer: Paul Swartz
"""

import struct, warnings, signal, os, sys
import signal
import sys
import os

from zope.interface import implements

from twisted.internet import protocol
from twisted.python import components, log
from twisted.python.failure import Failure
from twisted.python.deprecate import deprecated
from twisted.python.versions import Version
from twisted.conch.interfaces import ISessionApplication
from twisted.conch.interfaces import ISessionApplicationFactory, ISession
from twisted.conch.ssh import common, channel, connection



__all__ = ['SSHSession', 'packRequest_window_change', 'packRequest_pty_req',
           'parseRequest_window_change', 'parseRequest_pty_req']



# SUPPORTED_SIGNALS is a list of signals that every session channel is supposed
# to accept.  See RFC 4254
SUPPORTED_SIGNALS = ["ABRT", "ALRM", "FPE", "HUP", "ILL", "INT", "KILL",
                     "PIPE", "QUIT", "SEGV", "TERM", "USR1", "USR2"]



class SSHSession(channel.SSHChannel):
    """
    A channel implementing the server side of the 'session' channel.  This is
    the channel that a client requests when it wants a subsystem, shell, or
    command.

    @ivar earlyData: data sent to this channel before a client is present.
    @type earlyData: C{list} of C{str}
    @ivar earlyExtended: extended data sent to this channel before a client is
    present.
    @type earlyExtended: C{list}
    @ivar applicationFactory: an object to which requests for shells and such
        are dispatched.  It implements L{ISessionApplicationFactory}.
    @ivar sessionApplication: an object which handles interacting with the
        Lther side of the channel.  It implements I{ISessionApplication}.
    @ivar client: a C{ProcessProtocol} to which data sent to this channel is
        sent.  This variable is deprecated.
    @type client: L{protocol.ProcessProtocol}
    @ivar session: an object implementing L{ISession} to which requests for
        shells or commands are dispatched.  This variable is deprecated.
    """


    # set so that this object can be used as a client channel.
    name = 'session'


    def __setattr__(self, k, v):
        """
        Trap the 'client' attribute, what used to be the old name (roughly) for
        'sessionApplication', and 'session', which triggers setting up
        _DeprecatedSSHSession as our application factory.

        This is implemented as a __setattr__ hook instead of a property because
        the setter isn't called for properties on old-style classes.
        """
        if k == 'client':
            # Someone is trying to inform us of an old-style client.  Clear the
            # buffers (because this would not have previously delivered any
            # data, only delivered subsequent data) and set the old-style
            # "client" object up as a new-style processProtocol.
            warnings.warn("Setting the client attribute on an SSHSession is "
                          "deprecated since Twisted 9.0.",
                          DeprecationWarning,
                          stacklevel=2)
            self.earlyData = []
            self.earlyExtended = []
            self._setUpSession(_TransportToProcessProtocol(v.transport))
        if k == 'session' and v is not None:
            # Someone is trying to inform us of an old-style session.  Wrap it
            # in a _DeprecatedSSHSession.
            self.applicationFactory = _DeprecatedSSHSession(self, v)
        self.__dict__[k] = v


    def applicationFactory(self):
        """
        Produce an applicationFactory dynamically if one does not yet exist.
        We set self.applicationFactory when we have created the application
        factory because old-style classes don't support getters for
        properties.
        """
        if self.avatar is not None:
            factoryCandidate = ISessionApplicationFactory(self.avatar, None)
            if factoryCandidate is None:
                warnings.warn("Using an avatar that doesn't implement "
                              "ISessionApplicationFactory is deprecated since "
                              "Twisted 9.0.",
                              DeprecationWarning,
                              stacklevel=6)

                # Maybe it implements the old version.
                oldStyle = ISession(self.avatar, None)
                if oldStyle is not None:
                    # See __setattr__ above.
                    self.session = oldStyle
                else:
                    # Maybe it doesn't implement either.  The test
                    # SFTP server doesn't implement a session, because
                    # subsystems were just looked up in the avatar.
                    # Use a _SubsystemOnlyApplicationFactory.
                    self.applicationFactory = _SubsystemOnlyApplicationFactory(
                        self)
            else:
                self.applicationFactory = factoryCandidate
            return self.applicationFactory
        else:
            raise RuntimeError('Cannot get an application factory without an '
                               'avatar')
    applicationFactory = property(applicationFactory)


    def client(self):
        """
        Before Twisted 9.0, C{client} was the L{ProcessProtocol} that was
        connected to this L{SSHSession}. Since it's not connected to a
        C{ProcessProtocol} anymore, we fake it.

        Also, see the ivar documentation for this in L{SSHSession}.
        """
        if isinstance(self.sessionApplication,
                      (_ProcessProtocolToSessionApplication,
                        SSHSessionProcessProtocolApplication)):
            return self.sessionApplication.processProtocol
    client = property(client)


    # This used to be set in the older SSHSession implementation.
    # We set it when we create an application factory (see
    # applicationFactory() above.
    session = None


    def __init__(self, *args, **kw):
        channel.SSHChannel.__init__(self, *args, **kw)
        self.earlyData = []
        self.earlyExtended = []
        self.sessionApplication = None


    def _setUpSession(self, sessionApplication):
        """
        Connect us to the application.  We set ourselves as its channel
        instance variable, and the application becomes our sessionApplication.
        If any data was sent early, send it now.
        """
        # make sure we have an ISessionApplication
        sessionApplication = ISessionApplication(sessionApplication)
        sessionApplication.makeConnection(self)
        self.sessionApplication = sessionApplication
        if self.earlyData:
            bytes, self.earlyData = self.earlyData, None
            self.dataReceived(''.join(bytes))
        if self.earlyExtended:
            bytes, self.earlyExtended = self.earlyExtended, None
            for dataType, data in bytes:
                self.extReceived(dataType, data)


    def request_subsystem(self, data):
        """
        The remote side has requested a subsystem.  Payload::
            string  subsystem name

        Try to get a subsystem object by calling our adapter's lookupSubsystem
        method.  If that method returns a subsystem, then connect it to
        ourself and return True.  Otherwise, return False.
        """
        subsystem, rest = common.getNS(data)
        log.msg('asking for subsystem "%s"' % subsystem)
        try:
            client = self.applicationFactory.lookupSubsystem(subsystem, rest)
            if client:
                self._setUpSession(client)
                return True
        except KeyboardInterrupt:
            raise
        except:
            log.err(Failure(), "Exception while client requested a %r subsystem" % subsystem)
        return False


    def request_shell(self, data):
        """
        The remote side has requested a shell.  No payload.  Call the
        application factory's openShell() method; it returns something
        implementing I{ISessionApplication} that will become our
        application.  If there's no exception, return True.
        Otherwise, return False.
        """
        log.msg('getting shell')
        try:
            self._setUpSession(self.applicationFactory.openShell())
        except KeyboardInterrupt:
            raise
        except:
            log.err(Failure(), "Exception while client requested a shell")
            return False
        else:
            return True


    def request_exec(self, data):
        """
        The remote side has requested to execute a command.  Payload::
            string  command line

        Call the application factory's execCommand method with the
        command line.  It should return something implementing
        I{ISessionApplication} that becomes our client.  If there's no
        exception, return True.  Otherwise, return False.
        """
        command, data = common.getNS(data)
        log.msg('executing command "%s"' % command)
        try:
            self._setUpSession(self.applicationFactory.execCommand(command))
        except KeyboardInterrupt:
            raise
        except:
            log.err(Failure(), "Exception while client requested command %r" % command)
            return False
        else:
            return True


    def request_pty_req(self, data):
        """
        The remote side has requested a psuedoterminal (PTY).  Payload::
            string  terminal name
            uint32  columns
            uint32  rows
            uint32  xpixels
            uint32  ypixels
            string  modes

        Modes is::
            0 or more of::
                byte    mode number
                uint32  mode value

        Call the application factory's getPTY method.  If no exception
        is raised, return True.  Otherwise, return False.
        """
        try:
            term, windowSize, modes = parseRequest_pty_req(data)
            log.msg('pty request: %s %s' % (term, windowSize))
            self.applicationFactory.getPTY(term, windowSize, modes)
        except KeyboardInterrupt:
            raise
        except:
            log.err()
            return False
        else:
            return True


    def request_window_change(self, data):
        """
        The remote side has changed the window size.  Payload::
            uint32  columns
            uint32  rows
            uint32  xpixels
            uint32  ypixels


        Call the application factory's windowChanged method.  If no
        exception is raised, return True.  Otherwise, return False.
        """
        try:
            winSize = parseRequest_window_change(data)
            self.applicationFactory.windowChanged(winSize)
        except KeyboardInterrupt:
            raise
        except:
            log.msg('error changing window size')
            log.err()
            return False
        else:
            return True


    def dataReceived(self, data):
        """
        We got data from the remote side.  If we have an application,
        send the data to it.  Otherwise, buffer the data.

        @type data: C{str}
        """
        if self.sessionApplication is None:
            self.earlyData.append(data)
            return
        self.sessionApplication.dataReceived(data)


    def extReceived(self, dataType, data):
        """
        We got extended data from the remote side.  If we have an
        application, send the data to it.  Otherwise, buffer the data.

        @type dataType: C{int}
        @type data: C{str}
        """
        if self.sessionApplication is not None:
            self.sessionApplication.extendedDataReceived(dataType, data)
        else:
            self.earlyExtended.append((dataType, data))


    def eofReceived(self):
        """
        The remote side has closed its write side.  If we have an
        application factory, notify it.  If we have an application,
        notify it.
        """
        if self.applicationFactory is not None:
            self.applicationFactory.eofReceived()
        if self.sessionApplication is not None:
            self.sessionApplication.eofReceived()


    def closed(self):
        """
        The channel is closed.  If we have an application factory,
        notify it.  If we have an application, tell it the connection
        is lost.

        Note: closing the channel is separate from closing the connection
        to the client.  To do that, call self.conn.transport.loseConnection().
        """
        if self.applicationFactory is not None:
            self.applicationFactory.closed()
        if self.sessionApplication is not None:
            self.sessionApplication.closed()


    def closeReceived(self):
        """
        The remote side has requested that we no longer send data.  If
        we have an application factory, notify it.  If we have an
        application, notify it.
        """

        if self.applicationFactory is not None:
            self.applicationFactory.closeReceived()
        if self.sessionApplication is not None:
            self.sessionApplication.closeReceived()


    # Below are methods that are used by client implementations of the
    # 'session' channel.


    def getPty(self, term, windowSize, modes, wantReply=False):
        """
        Request a PTY from the other side.

        @param term: the type of terminal (e.g. xterm)
        @type term: C{str}
        @param windowSize: the size of the window: (rows, cols, xpixels,
                           ypixels)
        @type windowSize: C{tuple}
        @param modes: terminal modes; a list of (modeNumber, modeValue) pairs.
        @type modes: C{list}
        @param wantReply: True if we want a reply to this request.x
        @type wantReply: C{bool}

        @returns: if wantReply, a Deferred that will be called back when the
                  request has succeeded or failed; else, None.
        @rtype: C{Deferred}/C{None}
        """
        data = packRequest_pty_req(term, windowSize, modes)
        return self.conn.sendRequest(self, 'pty-req', data,
                wantReply=wantReply)


    def openSubsystem(self, subsystem, data='', wantReply=False):
        """
        Request that a subsystem be opened on the other side.

        @param subsystem: the name of the subsystem
        @type subsystem: C{str}
        @param data: any extra data to send with the request
        @type data: C{str}
        @param wantReply: True if we want a reply to this request.
        @type wantReply: C{bool}

        @returns: if wantReply, a Deferred that will be called back when
                  the request has succeeded or failed; else, None.
        @rtype: C{Deferred}/C{None}
        """
        return self.conn.sendRequest(self, 'subsystem', common.NS(subsystem) +
                data, wantReply=wantReply)


    def openShell(self, wantReply=False):
        """
        Request that a shell be opened on the other side.

        @param wantReply: True if we want a reply to this request.
        @type wantReply: C{bool}

        @returns: if wantReply, a Deferred that will be called back when
                  the request has succeeded or failed; else, None.
        @rtype: C{Deferred}/C{None}
        """
        return self.conn.sendRequest(self, 'shell', '', wantReply=wantReply)


    def execCommand(self, command, wantReply=False):
        """
        Request that a command be executed on the other side.

        @param command: the command to execute
        @type command: C{str}
        @param wantReply: True if we want a reply to this request.
        @type wantReply: C{bool}

        @returns: if wantReply, a Deferred that will be called back when
                  the request has succeeded or failed; else, None.
        @rtype: C{Deferred}/C{None}
        """
        return self.conn.sendRequest(self, 'exec', common.NS(command),
                wantReply=wantReply)


    def changeWindowSize(self, windowSize, wantReply=False):
        """
        Inform the other side that the local terminal size has changed.

        @param windowSize: the new size of the window: (rows, cols, xpixels,
                           ypixels)
        @type windowSize: C{tuple}
        @param wantReply: True if we want a reply to this request.
        @type wantReply: C{bool}

        @returns: if wantReply, a Deferred that will be called back when
                  the request has succeeded or fails; else, None.
        @rtype: C{Deferred}/C{None}
        """
        data = packRequest_window_change(windowSize)
        return self.conn.sendRequest(self, 'window-change', data,
                wantReply=wantReply)



class _SubsystemOnlyApplicationFactory(object):
    """
    An application factory which which is only good for looking up a
    subsystem.  It is used when there is not an ISession adapter
    defined for the avatar.  Its use is deprecated.
    """
    implements(ISessionApplicationFactory)


    def __init__(self, sessionChannel):
        self.sessionChannel = sessionChannel


    def lookupSubsystem(self, subsystem, data):
        """
        The previous ConchUser avatar had subsystems looked up through
        the avatar instead of through the ISession adapter.  To be backwards
        compatible, try to look up the subsystem through the avatar.
        """
        self.sessionChannel.earlyData = []
        self.sessionChannel.earlyExtended = []
        client = self.sessionChannel.avatar.lookupSubsystem(subsystem,
                                                            common.NS(subsystem)
                                                            + data)
        return wrapProcessProtocol(client)


    def eofReceived(self):
        self.sessionChannel.loseConnection()


    def closeReceived(self):
        """
        The old closeReceived method did not exist, so we dispatch to our
        parent's method.
        """
        channel.SSHChannel.closeReceived(self.sessionChannel)


    def closed(self):
        """
        The old implementation of this method didn't do anything, so we
        don't do anything either.
        """



class _DeprecatedSSHSession(_SubsystemOnlyApplicationFactory):
    """
    This class brings the deprecated functionality of the old SSHSession
    into a single place.
    """


    def __init__(self, sessionChannel, oldISessionProvider):
        _SubsystemOnlyApplicationFactory.__init__(self, sessionChannel)
        self.oldISessionProvider = oldISessionProvider


    def getPTY(self, term, windowSize, modes):
        """
        The name of this method used to be getPty.
        """
        return self.oldISessionProvider.getPty(term, windowSize, modes)


    def openShell(self):
        """
        The old openShell interface passed in a ProcessProtocol which would be
        connected to the shell.
        """
        pp = SSHSessionProcessProtocol(self.sessionChannel)
        self.oldISessionProvider.openShell(pp)
        return SSHSessionProcessProtocolApplication(pp)


    def execCommand(self, command):
        """
        The old execCommand interface passed in a ProcessProtocol which would
        be connected to the command.
        """
        pp = SSHSessionProcessProtocol(self.sessionChannel)
        self.oldISessionProvider.execCommand(pp, command)
        return SSHSessionProcessProtocolApplication(pp)


    def eofReceived(self):
        """
        The old eofReceived method closed the session connection.
        """
        self.oldISessionProvider.eofReceived()
        self.sessionChannel.conn.sendClose(self.sessionChannel)


    def closed(self):
        """
        The old closed method closed the client's transport.
        """
        if self.sessionChannel.sessionApplication is not None:
            self.sessionChannel.sessionApplication.processProtocol.transport.loseConnection()
        self.oldISessionProvider.closed()


    def windowChanged(self, newWindowSize):
        """
        Just pass this method through.
        """
        self.oldISessionProvider.windowChanged(newWindowSize)



class _ProtocolToProcessProtocol(protocol.ProcessProtocol):
    """
    This class wraps a L{Protocol} instance in a L{ProcessProtocol} instance.

    XXX: This belongs in twisted.internet, not twisted.conch. - jml 2008-04-06

    @ivar proto: the C{Protocol} we're wrapping.
    """


    def __init__(self, proto):
        self.proto = proto


    def __getattr__(self, attr):
        """
        This class did not previously exist, so some uses expect this object
        to implement the Protocol interface.  To handle this case, we pass
        requests through to the wrapped object.
        """
        return getattr(self.proto, attr)


    def __setattr__(self, attr, value):
        """
        See the documentation for __getattr__.
        """
        if attr in ('proto', 'transport'):
            self.__dict__[attr] = value
        else:
            setattr(self.proto, attr, value)


    def connectionMade(self):
        """
        Connect our C{Protocol} to our transport.
        """
        self.proto.makeConnection(self.transport)
        self.transport.proto = self


    def outReceived(self, data):
        """
        Give the data to the C{Protocol}s dataReceived method.
        """
        self.proto.dataReceived(data)


    def processEnded(self, reason):
        """
        Give the C{Failure} to the C{Protocol}s connectionLost method.
        """
        self.proto.connectionLost(reason)



def wrapProcessProtocol(inst):
    """
    If we're passed a C{Protocol}, wrap it in a C{ProcessProtocol}.
    Otherwise, just return what we were passed.
    """
    if isinstance(inst, protocol.Protocol):
        return _ProtocolToProcessProtocol(inst)
    else:
        return inst



class _TransportToProcessProtocol(protocol.ProcessProtocol):
    """
    This wraps something implementing L{ITransport} in a C{ProcessProtocol}.
    Some old implementations directly set L{SSHSession}.client to a transport,
    and this wrapper supports that obscure use of L{SSHSession}.  We wrap it in
    a C{ProcessProtocol} instead of directly in an L{ISessionApplication}
    because L{_DeprecatedSSHSession} expects the client to be a
    C{ProcessProtocol}.

    @ivar applicationTransport: the L{ITransport} we're wrapping.

    @since: 9.0
    """


    def __init__(self, applicationTransport):
        self.applicationTransport = applicationTransport


    def outReceived(self, data):
        """
        When we get data, write it to our transport.
        """
        self.applicationTransport.write(data)


    def errReceived(self, data):
        """
        When we get extended data, give it to the writeErr method of our
        transport if it exists.  writeErr was a non-interface method that
        transports could implement in order to see data sent to standard error.
        The correct way to have this behavior is to implement an
        L{ISessionApplication}.
        """
        if getattr(self.applicationTransport, 'writeErr', None) is not None:
            self.applicationTransport.writeErr(data)


    def processEnded(self, reason):
        """
        When we're told the process ended, tell the transport to drop
        the connection.  Yes, this loses data.
        """
        self.applicationTransport.loseConnection()



class _ProcessProtocolToSessionApplication:
    """
    This adapts a C{ProcessProtocol} to an C{ISessionApplication.}  The old
    I{ISession} interface returned C{ProcessProtocol}s from lookupSubsystem().
    We wrap those objects with this class in order to provide the new
    I{ISessionApplication} interface.

    @ivar processProtocol: the C{ProcessProtocol} we're adapting.

    @since: 9.0
    """


    implements(ISessionApplication)


    def __init__(self, processProtocol):
        self.processProtocol = processProtocol


    def makeConnection(self, channel):
        """
        Connect the C{ProcessProtocol} to the channel.
        """
        self.channel = channel
        self.processProtocol.makeConnection(channel)


    def dataReceived(self, data):
        """
        Give the data to the C{ProcessProtocol}
        """
        self.processProtocol.outReceived(data)


    def extendedDataReceived(self, type, data):
        """
        If the extended data came from standard error, give it to the
        C{ProcessProtocol}.  Otherwise drop it on the floor.
        """
        if type == connection.EXTENDED_DATA_STDERR:
            self.processProtocol.errReceived(data)


    def eofReceived(self):
        """
        Tell the C{ProcessProtocol} that no more data will be sent to
        standard input.
        """
        self.processProtocol.inConnectionLost()


    def closeReceived(self):
        """
        Tell the C{ProcessProtocol} that it shouldn't send any more data.
        """
        self.processProtocol.outConnectionLost()
        self.processProtocol.errConnectionLost()


    def closed(self):
        """
        Tell the C{ProcessProtocol} that the process ended.

        TODO: catch request_exit_status to give a better error message.
        """
        self.processProtocol.processEnded(protocol.connectionDone)



components.registerAdapter(_ProcessProtocolToSessionApplication,
                           protocol.ProcessProtocol, ISessionApplication)



class SSHSessionProcessProtocol(protocol.ProcessProtocol):
    """
    This is a C{ProcessProtocol} that is used to connect to old-style
    ISession implementations.  An instance of this is passed to
    openShell() and execCommand(), and then it's wrapped using
    SSHSessionProcessProtocolApplication.
    """


    # once initialized, a dictionary mapping signal values to strings
    # that follow RFC 4254.
    _signalNames = None


    def __init__(self, session):
        self.session = session


    def _getSignalName(self, signum):
        """
        Get a signal name given a signal number.
        """
        if self._signalNames is None:
            self._signalNames = {}
            # make sure that the POSIX ones are the defaults
            for signame in SUPPORTED_SIGNALS:
                signame = 'SIG' + signame
                sigvalue = getattr(signal, signame, None)
                if sigvalue is not None:
                    self._signalNames[sigvalue] = signame
            for k, v in signal.__dict__.items():
                if k.startswith('SIG') and not k.startswith('SIG_'):
                    if v not in self._signalNames:
                        self._signalNames[v] = k + '@' + sys.platform
        return self._signalNames[signum]


    def outReceived(self, data):
        """
        Sent data from standard out over the channel.
        """
        self.session.write(data)


    def errReceived(self, err):
        """
        Send data from standard error as extended data of type
        EXTENDED_DATA_STDERR.
        """
        self.session.writeExtended(connection.EXTENDED_DATA_STDERR, err)


    def inConnectionLost(self):
        """
        If we're told the incoming connection has been lost, send an EOF
        over the channel.
        """
        self.session.conn.sendEOF(self.session)


    def outConnectionLost(self):
        """
        If we're running as an subsystem, close the connection.
        """
        if self.session.session is None: # we're running as an old-style
                                         # subsystem
            self.session.loseConnection()


    def processEnded(self, reason=None):
        """
        When we are told the process ended, try to notify the other side about
        how the process ended using the exit-signal or exit-status requests.
        Also, close the channel.
        """
        if (reason is not None and
            getattr(reason.value, 'exitCode', None) is not None):
            err = reason.value
            if err.signal is not None:
                signame = self._getSignalName(err.signal)
                if (getattr(os, 'WCOREDUMP', None) is not None and
                    os.WCOREDUMP(err.status)):
                    log.msg('exitSignal: %s (core dumped)' % (signame,))
                    coreDumped = 1
                else:
                    log.msg('exitSignal: %s' % (signame,))
                    coreDumped = 0
                self.session.conn.sendRequest(self.session, 'exit-signal',
                        common.NS(signame[3:]) + chr(coreDumped) +
                        common.NS('') + common.NS(''))
            elif err.exitCode is not None:
                log.msg('exitCode: %r' % (err.exitCode,))
                self.session.conn.sendRequest(self.session, 'exit-status',
                        struct.pack('>L', err.exitCode))
        self.session.loseConnection()


    # also a transport :( Some old code used SSHSessionProcessProtocol() like a
    # transport, so we have to continue to support this interface.
    def write(self, data):
        """
        If we're used like a transport, just send the data to the channel.
        """
        self.session.write(data)


    def loseConnection(self):
        """
        If we're used like a transport, send the close message.
        """
        self.session.loseConnection()


SSHSessionProcessProtocol.write = deprecated(Version("Twisted", 9, 0, 0))(SSHSessionProcessProtocol.write)
SSHSessionProcessProtocol.loseConnection = deprecated(Version("Twisted", 9, 0, 0))(SSHSessionProcessProtocol.loseConnection)



class SSHSessionProcessProtocolApplication:
    """
    Another layer of wrapping to make the old-style ISession
    implemention work.  This adapts SSHSessionProcessProtocol to
    ISessionApplication.

    @ivar processProtocol: the C{SSHSessionProcessProtocol} we're adapting.
    """


    implements(ISessionApplication)


    def __init__(self, processProtocol):
        self.processProtocol = processProtocol


    def makeConnection(self, channel):
        """
        Don't need to do anything because SSHSessionProcessProtocol's
        transport doesn't do anything with this.
        """
        self.channel = channel


    def dataReceived(self, data):
        """
        When we get data, write it to the SSHSessionProcessProtocol's
        transport.
        """
        self.processProtocol.transport.write(data)


    def extendedDataReceived(self, dataType, data):
        """
        If we get extended data from standard error and the transport
        has a writeErr method, pass the data along.
        """
        if getattr(self.processProtocol.transport, 'writeErr', None) is None:
            return
        if dataType == connection.EXTENDED_DATA_STDERR:
            self.processProtocol.transport.writeErr(data)


    def eofReceived(self):
        """
        Don't need to implement this because
        SSHSessionProcessProtocol's transport doesn't do anything with
        this.
        """


    def closeReceived(self):
        """
        Don't need to implement this because
        SSHSessionProcessProtocol's transport doesn't do anything with
        this.
        """


    def closed(self):
        """
        Don't need to implement this because
        SSHSessionProcessProtocol's transport doesn't do anything with
        this.
        """



class SSHSessionClient(protocol.Protocol):
    """
    A class the conch command-line client uses to connect the channel
    to standard output.  Deprecated.
    """

    def __init__(self):
        warnings.warn(
            "twisted.conch.ssh.session.SSHSessionClient was deprecated "
            "in Twisted 9.0.0", DeprecationWarning, stacklevel=2)


    def dataReceived(self, data):
        """
        Send data to the transport.
        """
        self.transport.write(data)



class _DummyTransport:
    """
    This is only used by L{wrapProtocol} to adapt a L{Protocol} to a
    L{Transport} for L{SSHSessionProcessProtocol}.
    """
    def __init__(self, proto):
        self.proto = proto

    def write(self, data):
        self.proto.outReceived(data)

    def loseConnection(self):
        self.proto.processEnded(protocol.connectionDone)



def wrapProtocol(proto):
    """
    A deprecated function used to wrap a L{Protocol} or L{ProcessProtocol} into
    a L{Transport}.
    """
    return _DummyTransport(wrapProcessProtocol(proto))

wrapProtocol = deprecated(Version("Twisted", 9, 0, 0))(wrapProtocol)



# methods factored out to make live easier on server writers
def parseRequest_pty_req(data):
    """
    Parse the data from a pty-req request into usable data.  See RFC 4254 6.2
    and 8.

    @returns: a tuple of (terminal type, (rows, cols, xpixel, ypixel), modes)
    """
    term, rest = common.getNS(data)
    cols, rows, xpixel, ypixel = struct.unpack('>4L', rest[:16])
    modes, ignored= common.getNS(rest[16:])
    winSize = (rows, cols, xpixel, ypixel)
    modes = [(ord(modes[i]), struct.unpack('>L', modes[i+1:i+5])[0]) for i in
            range(0, len(modes) - 1, 5)]
    return term, winSize, modes



def packRequest_pty_req(term, (rows, cols, xpixel, ypixel), modes):
    """
    Pack a pty-req request so that it is suitable for sending.  See RFC 4254
    6.2 and 8.
    """
    termPacked = common.NS(term)
    winSizePacked = struct.pack('>4L', cols, rows, xpixel, ypixel)
    if not isinstance(modes, str):
        modes = ''.join([chr(m[0]) + struct.pack('>L', m[1]) for m in modes])
    else:
        warnings.warn("packRequest_pty_req should be packing the modes.",
                      DeprecationWarning, stacklevel=2)
    modesPacked = common.NS(modes)
    return termPacked + winSizePacked + modesPacked



def parseRequest_window_change(data):
    """
    Parse the data from a window-change request into usuable data.

    @returns: a tuple of (rows, cols, xpixel, ypixel)
    """
    cols, rows, xpixel, ypixel = struct.unpack('>4L', data)
    return rows, cols, xpixel, ypixel



def packRequest_window_change((rows, cols, xpixel, ypixel)):
    """
    Pack a window-change request so that it is suitable for sending.
    """
    return struct.pack('>4L', cols, rows, xpixel, ypixel)

