# Copyright (c) 2007-2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the 'session' channel implementation in twisted.conch.ssh.session.

See also RFC 4254.
"""

import os, signal, sys, struct

from zope.interface import implements

from twisted.conch.ssh import common, connection, session
from twisted.internet import defer, protocol, error
from twisted.python import components, failure
from twisted.python.versions import Version
from twisted.trial import unittest



class SubsystemOnlyAvatar(object):
    """
    A stub class representing an avatar that is only useful for
    getting a subsystem.
    """


    def lookupSubsystem(self, name, data):
        """
        If the other side requests the 'subsystem' subsystem, allow it by
        returning a MockProcessProtocol to implement it.  Otherwise, return
        None which is interpreted by SSHSession as a failure.
        """
        if name == 'subsystem':
            return MockProcessProtocol()



class StubOldAvatar:
    """
    A stub class representing the avata representing the authenticated user.
    It implements the old I{ISession} interface.
    """


    def lookupSubsystem(self, name, data):
        """
        If the user requests the TestSubsystem subsystem, connect them
        to our MockProcessProtocol.  If they request the protocol
        subsystem, connect them to a MockProtocol.  If they request neither,
        then None is returned which is interpreted by SSHSession as a failure.
        """
        if name == 'TestSubsystem':
            self.subsystem = MockProcessProtocol()
            self.subsystem.packetData = data
            return self.subsystem
        elif name == 'protocol':
            self.subsystem = MockProtocol()
            self.subsystem.packetData = data
            return self.subsystem



class StubSessionForStubOldAvatar(object):
    """
    A stub ISession implementation for our StubOldAvatar.  The instance
    variables generally keep track of method invocations so that we can test
    that the methods were called.

    @ivar avatar: the L{StubOldAvatar} we are adapting.
    @ivar ptyRequest: if present, the terminal, window size, and modes passed
        to the getPty method.
    @ivar windowChange: if present, the window size passed to the
        windowChangned method.
    @ivar shellProtocol: if present, the L{SSHSessionProcessProtocol} passed
        to the openShell method.
    @ivar shellTransport: if present, the L{EchoTransport} connected to
        shellProtocol.
    @ivar execProtocol: if present, the L{SSHSessionProcessProtocol} passed
        to the execCommand method.
    @ivar execTransport: if present, the L{EchoTransport} connected to
        execProtocol.
    @ivar execCommandLine: if present, the command line passed to the
        execCommand method.
    @ivar gotEOF: if present, an EOF message was received.
    @ivar gotClosed: if present, a closed message was received.
    """


    implements(session.ISession)


    def __init__(self, avatar):
        """
        Store the avatar we're adapting.
        """
        self.avatar = avatar
        self.shellProtocol = None


    def getPty(self, terminal, window, modes):
        """
        If the terminal is 'bad', fail.  Otherwise, store the information in
        the ptyRequest variable.
        """
        if terminal != 'bad':
            self.ptyRequest = (terminal, window, modes)
        else:
            raise RuntimeError('not getting a pty')


    def windowChanged(self, window):
        """
        If all the window sizes are 0, fail.  Otherwise, store the size in the
        windowChange variable.
        """
        if window == (0, 0, 0, 0):
            raise RuntimeError('not changing the window size')
        else:
            self.windowChange = window


    def openShell(self, pp):
        """
        If we have gotten a shell request before, fail.  Otherwise, store the
        process protocol in the shellProtocol variable, connect it to the
        EchoTransport and store that as shellTransport.
        """
        if self.shellProtocol is not None:
            raise RuntimeError('not getting a shell this time')
        else:
            self.shellProtocol = pp
            self.shellTransport = EchoTransport(pp)


    def execCommand(self, pp, command):
        """
        If the command is 'true', store the command, the process protocol, and
        the transport we connect to the process protocol.  Otherwise, just
        store the command and raise an error.
        """
        self.execCommandLine = command
        if command == 'success':
            self.execProtocol = pp
        elif command[:6] == 'repeat':
            self.execProtocol = pp
            self.execTransport = EchoTransport(pp)
            pp.outReceived(command[7:])
        else:
            raise RuntimeError('not getting a command')


    def eofReceived(self):
        """
        Note that EOF has been received.
        """
        self.gotEOF = True


    def closed(self):
        """
        Note that close has been received.
        """
        self.gotClosed = True



components.registerAdapter(StubSessionForStubOldAvatar, StubOldAvatar,
        session.ISession)



class StubNewAvatar(object):
    """
    A stub avatar.  It does not need any methods, as it is only used as the
    object StubSessionForStubNewAvatar adapts.
    """



class StubApplicationFactoryForStubNewAvatar:
    """
    A stub ISessionApplicationFactory implementation for our StubNewAvatar.
    The instance variables generally keep track of method calls so that the
    tests can verify that those methods were called.

    @ivar avatar: the L{StubOldAvatar} we are adapting.
    @ivar inConnectionOpen: C{True} if the input side is open.
    @ivar outConnectionOpen: C{True} if the output side is open.
    @ivar ended: C{True} if the session has ended.
    @ivar subsystem: if present, the L{MockApplication} that is the
        current subsystem.  It has a packetData ivar which is the C{str} of
        data passed in the subsystem request.
    @ivar term: if present, the terminal name passed to getPty
    @ivar windowSize: if present, the window size passed to getPty or
        windowChanged
    @ivar modes: if present, the terminal modes passed to getPty
    @ivar command: if present, the L{MockApplication} that is the
        current command.  It has a command ivar which is the C{str} giving
        the command's name.
    @ivar shell: if present, the L{MockApplication} that is the current
        shell.
    """


    implements(session.ISessionApplicationFactory)


    def __init__(self, avatar):
        self.avatar = avatar
        self.inConnectionOpen = True
        self.outConnectionOpen = True
        self.ended = False
        self.subsystem = None
        self.command = None
        self.shell = None


    def lookupSubsystem(self, subsystem, data):
        """
        Request a subsystem.  If one has been requested already, raise an
        exception.  Otherwise, set self.subsystem to a MockApplication and
        return it.
        """
        if self.subsystem is not None:
            raise ValueError('already opened a subsystem')
        if subsystem == 'repeat':
            self.subsystem = MockApplication()
            self.subsystem.packetData = data
            return self.subsystem


    def getPTY(self, term, windowSize, modes):
        """
        Request a pseudoterminal.  Store the data passed to us.
        """
        self.term = term
        self.windowSize = windowSize
        self.modes = modes


    def windowChanged(self, newSize):
        """
        The window size has changed.  Store the data.
        """
        self.windowSize = newSize


    def execCommand(self, command):
        """
        Request a command.  If one has been requested already, raise an
        exception.  Otherwise, set self.command to a MockApplication and
        return it.
        """

        if self.command is not None:
            raise RuntimeError('already executed a command')
        self.command = MockApplication()
        self.command.command = command
        return self.command


    def openShell(self):
        """
        Request a shell.  If one has been requested already, raise an
        exception.  Otherwise, set self.shell to a MockApplication and
        return it.
        """

        if self.shell is not None:
            raise RuntimeError('already opened a shell')
        self.shell = MockApplication()
        return self.shell


    def eofReceived(self):
        """
        Close the input side.
        """
        self.inConnectionOpen = False


    def closeReceived(self):
        """
        Close the output side.
        """
        self.outConnectionOpen = False


    def closed(self):
        """
        End the session.
        """
        self.ended = True



components.registerAdapter(StubApplicationFactoryForStubNewAvatar,
                           StubNewAvatar,
                           session.ISessionApplicationFactory)



class KeyboardInterruptApplicationFactory(object):
    """
    This is an application factory which doesn't actually create any
    applications.  It raises a KeyboardInterrupt exception to test the special
    handling of that exception in SSHSession.
    """


    def lookupSubsystem(self, subsystem, rest):
        raise KeyboardInterrupt


    def openShell(self):
        raise KeyboardInterrupt


    def execCommand(self, command):
        raise KeyboardInterrupt


    def getPTY(self, term, windowSize, modes):
        raise KeyboardInterrupt


    def windowChanged(self, winSize):
        raise KeyboardInterrupt



class MockApplication:
    """
    A mock ISessionApplication.  This is the new interface that
    clients of SSHSession should implement.

    @ivar data: a C{list} of C{str} passed to our dataReceived.
    @ivar extendedData: a C{list} of C{tuple} of (C{int}, C{str})
        passed to our extendedDataReceived.
    @ivar hasClosed: a C{bool} indicating whether the application is closed.
    @ivar gotEOF: if present, we have received an EOF from the other side.
    @ivar gotClose: if present, we have received a close message from the other
       side
    """


    implements(session.ISessionApplication)


    def makeConnection(self, channel):
        """
        Called when the application is connected to the other side.
        Initialize our instance variables.
        """
        self.channel = channel
        self.data = []
        self.extendedData = []
        self.hasClosed = False


    def dataReceived(self, data):
        """
        We got some data.  Store it, and echo it back with a tilde appended.
        The tilde is appended so that the tests can verify that this method
        was called by checking for the extra byte.
        """
        self.data.append(data)
        self.channel.write(data + '~')


    def extendedDataReceived(self, type, data):
        """
        We got some extended data.  Store it, and echo it back with an
        incremented data type and with a tilde appended to the data.  Also see
        the docstring for dataReceived().
        """
        self.extendedData.append((type, data))
        self.channel.writeExtended(type + 1, data + '~')


    def eofReceived(self):
        """
        Note that we received an EOF.
        """
        self.gotEOF = True


    def closeReceived(self):
        """
        Note that we received a close message.
        """
        self.gotClose = True


    def closed(self):
        """
        Note that this application is closed.
        """
        self.hasClosed = True



class MockApplicationSendingOnConnection(MockApplication):
    """
    This is a a simple subclass of MockApplication which sends some
    data when it is connected.
    """


    def connectionMade(self):
        """
        Write an introduction when we are connected.
        """
        MockApplication.connectionMade(self)
        self.channel.write('intro')



class MockProcessProtocol(protocol.ProcessProtocol):
    """
    A mock ProcessProtocol which echoes back data sent to it and
    appends a tilde.  The tilde is appended so the tests can verify that
    we received and processed the data.

    @ivar packetData: C{str} of data to be sent when the connection is made.
    @ivar data: a C{str} of data received.
    @ivar err: a C{str} of error data received.
    @ivar inConnectionOpen: True if the input side is open.
    @ivar outConnectionOpen: True if the output side is open.
    @ivar errConnectionOpen: True if the error side is open.
    @ivar ended: False if the protocol has not ended, a C{Failure} if the
        process has ended.
    """
    packetData = ''


    def connectionMade(self):
        """
        Set up variables.
        """
        self.data = ''
        self.err = ''
        self.inConnectionOpen = True
        self.outConnectionOpen = True
        self.errConnectionOpen = True
        self.ended = False
        if self.packetData:
            self.outReceived(self.packetData)


    def outReceived(self, data):
        """
        Data was received.  Store it and echo it back with a tilde.
        """
        self.data += data
        if self.transport is not None:
            self.transport.write(data + '~')


    def errReceived(self, data):
        """
        Error data was received.  Store it and echo it back backwards.
        """
        self.err += data
        self.transport.write(data[::-1])


    def inConnectionLost(self):
        """
        Close the input side.
        """
        self.inConnectionOpen = False


    def outConnectionLost(self):
        """
        Close the output side.
        """
        self.outConnectionOpen = False


    def errConnectionLost(self):
        """
        Close the error side.
        """
        self.errConnectionOpen = False


    def processEnded(self, reason):
        """
        End the process and store the reason.
        """
        self.ended = reason



class EchoTransport:
    """
    A transport for a ProcessProtocol which echos data that is sent to it with
    a Window newline (CR LF) appended to it.  If a null byte is in the data,
    disconnect.  When we are asked to disconnect, disconnect the
    C{ProcessProtocol} with a 0 exit code.

    @ivar proto: the C{ProcessProtocol} connected to us.
    @ivar data: a C{str} of data written to us.
    """


    def __init__(self, processProtocol):
        """
        Initialize our instance variables.

        @param processProtocol: a C{ProcessProtocol} to connect to ourself.
        """
        self.proto = processProtocol
        processProtocol.makeConnection(self)
        self.closed = False
        self.data = ''


    def write(self, data):
        """
        We got some data.  Give it back to our C{ProcessProtocol} with
        a newline attached.  Disconnect if there's a null byte.
        """
        self.data += data
        self.proto.outReceived(data)
        self.proto.outReceived('\r\n')
        if '\x00' in data: # mimic 'exit' for the shell test
            self.loseConnection()


    def loseConnection(self):
        """
        If we're asked to disconnect (and we haven't already) shut down
        the C{ProcessProtocol} with a 0 exit code.
        """
        if self.closed:
            return
        self.closed = 1
        self.proto.inConnectionLost()
        self.proto.outConnectionLost()
        self.proto.errConnectionLost()
        self.proto.processEnded(failure.Failure(
                error.ProcessTerminated(0, None, None)))



class MockProtocol(protocol.Protocol):
    """
    A sample Protocol which stores the data passed to it.

    @ivar packetData: a C{str} of data to be sent when the connection is made.
    @ivar data: a C{str} of the data passed to us.
    @ivar open: True if the channel is open.
    @ivar reason: if not None, the reason the protocol was closed.
    """
    packetData = ''


    def connectionMade(self):
        """
        Set up the instance variables.  If we have any packetData, send it
        along.
        """
        self.data = ''
        self.open = True
        self.reason = None
        if self.packetData:
            self.dataReceived(self.packetData)


    def dataReceived(self, data):
        """
        Store the received data and write it back with a tilde appended.
        The tilde is appended so that the tests can verify that we processed
        the data.
        """
        self.data += data
        if self.transport is not None:
            self.transport.write(data + '~')


    def connectionLost(self, reason):
        """
        Close the protocol and store the reason.
        """
        self.open = False
        self.reason = reason



class StubConnection:
    """
    A stub for twisted.conch.ssh.connection.SSHConnection.  Record the data
    that channels send, and when they try to close the connection.

    @ivar data: a C{dict} mapping C{SSHChannel}s to a C{list} of C{str} of data
       they sent.
    @ivar extData: a C{dict} mapping L{SSHChannel}s to a C{list} of C{tuple} of
       (C{int}, C{str}) of extended data they sent.
    @ivar requests: a C{dict} mapping L{SSHChannel}s to a C{list} of C{tuple}
        of (C{str}, C{str}) of channel requests they made.
    @ivar eofs: a C{dict} mapping L{SSHChannel}s to C{true} if they have sent
        an EOF.
    @ivar closes: a C{dict} mapping L{SSHChannel}s to C{true} if they have sent
        a close.
    """


    def __init__(self):
        """
        Initialize our instance variables.
        """
        self.data = {}
        self.extData = {}
        self.requests = {}
        self.eofs = {}
        self.closes = {}


    def logPrefix(self):
        """
        Return our logging prefix.
        """
        return "MockConnection"


    def sendData(self, channel, data):
        """
        Record the sent data.
        """
        self.data.setdefault(channel, []).append(data)


    def sendExtendedData(self, channel, type, data):
        """
        Record the sent extended data.
        """
        self.extData.setdefault(channel, []).append((type, data))


    def sendRequest(self, channel, request, data, wantReply=False):
        """
        Record the sent channel request.
        """
        self.requests.setdefault(channel, []).append((request, data,
            wantReply))
        if wantReply:
            return defer.succeed(None)


    def sendEOF(self, channel):
        """
        Record the sent EOF.
        """
        self.eofs[channel] = True


    def sendClose(self, channel):
        """
        Record the sent close.
        """
        self.closes[channel] = True



class StubTransport:
    """
    A stub transport which records the data written.

    @ivar buf: the data sent to the transport.
    @type buf: C{str}

    @ivar close: flags indicating if the transport has been closed.
    @type close: C{bool}
    """

    buf = ''
    close = False


    def write(self, data):
        """
        Record data in the buffer.
        """
        self.buf += data


    def loseConnection(self):
        """
        Note that the connection was closed.
        """
        self.close = True


class StubTransportWithWriteErr(StubTransport):
    """
    A version of StubTransport which records the error data sent to it.

    @ivar err: the extended data sent to the transport.
    @type err: C{str}
    """

    err = ''


    def writeErr(self, data):
        """
        Record the extended data in the buffer.  This was an old interface
        that allowed the Transports from ISession.openShell() or
        ISession.execCommand() to receive extended data from the client.
        """
        self.err += data



class StubClient(object):
    """
    A stub class representing the client to a SSHSession.

    @ivar transport: A L{StubTransport} object which keeps track of the data
        passed to it.
    """


    def __init__(self):
        self.transport = StubTransportWithWriteErr()


class OldSessionInterfaceTestCase(unittest.TestCase):
    """
    Tests for the old SSHSession class interface.  This interface is not ideal,
    but it is tested in order to maintain backwards compatibility.
    """


    def setUp(self):
        """
        Make an SSHSession object to test.  Give the channel some window
        so that it's allowed to send packets.  500 and 100 are arbitrary
        values.
        """
        self.session = session.SSHSession(remoteWindow=500,
                remoteMaxPacket=100, conn=StubConnection(),
                avatar=StubOldAvatar())


    def assertSessionIsStubSession(self):
        """
        Asserts that self.session.session is an instance of
        StubSessionForStubOldAvatar.
        """
        self.assertIsInstance(self.session.session,
                              StubSessionForStubOldAvatar)


    def _setSessionClient(self):
        """
        Setting self.session.client gives a DeprecationWarning.  We use this
        function to handle wrapping that assignment in assertWarns.
        """
        client = StubClient()
        def _assign():
            self.session.client = client
        self.assertWarns(DeprecationWarning, "Setting the client attribute "
                         "on an SSHSession is deprecated since Twisted 9.0.",
                         __file__, _assign)
        return client


    def _wrapWithAssertWarns(self, function, *args):
        """
        Some of the methods we test give a warning that using an old avatar
        (one that implements ISession instead of ISessionApplication) is
        deprecated.
        """
        return self.assertWarns(DeprecationWarning,
                                "Using an avatar that doesn't implement "
                                "ISessionApplicationFactory is deprecated "
                                "since Twisted 9.0.",
                                __file__, function, *args)


    def test_init(self):
        """
        SSHSession initializes its buffer (buf), client, and ISession adapter.
        The avatar should not need to be adaptable to an ISession immediately.
        """
        s = session.SSHSession(avatar=object) # use object because it doesn't
                                              # have an adapter
        self.assertEquals(s.buf, '')
        self.assertIdentical(s.client, None)
        self.assertIdentical(s.session, None)


    def test_client_dataReceived(self):
        """
        SSHSession.dataReceived() passes data along to a client.  If the data
        comes before there is a client, the data should be discarded.
        """
        self.session.dataReceived('1')
        self._setSessionClient()
        self.session.dataReceived('2')
        self.assertEquals(self.session.client.transport.buf, '2')

    def test_client_extReceived(self):
        """
        SSHSession.extReceived() passed data of type EXTENDED_DATA_STDERR along
        to the client.  If the data comes before there is a client, or if the
        data is not of type EXTENDED_DATA_STDERR, it is discared.
        """
        self.session.extReceived(connection.EXTENDED_DATA_STDERR, '1')
        self.session.extReceived(255, '2') # 255 is arbitrary
        self._setSessionClient()
        self.session.extReceived(connection.EXTENDED_DATA_STDERR, '3')
        self.assertEquals(self.session.client.transport.err, '3')


    def test_client_extReceivedWithoutWriteErr(self):
        """
        SSHSession.extReceived() should handle the case where the transport
        on the client doesn't have a writeErr method.
        """
        client = self._setSessionClient()
        client.transport = StubTransport() # doesn't have writeErr

        # should not raise an error
        self.session.extReceived(connection.EXTENDED_DATA_STDERR, 'ignored')


    def test_applicationFactoryWithoutAvatar(self):
        """
        If L{SSHSession} doesn't have an avatar, it can't give a proper
        application factory thus raises a C{RuntimeError}.
        """
        self.session.avatar = None
        self.assertRaises(
            RuntimeError, getattr, self.session, "applicationFactory")


    def test_client_eofReceived(self):
        """
        SSHSession.eofReceived() should send a close message to the remote
        side.
        """
        self._setSessionClient()
        self._wrapWithAssertWarns(self.session.eofReceived)
        self.assertTrue(self.session.conn.closes[self.session])


    def test_client_closed(self):
        """
        SSHSession.closed() should tell the transport connected to the client
        that the connection was lost.
        """
        self._setSessionClient()
        self._wrapWithAssertWarns(self.session.closed)
        self.assertTrue(self.session.client.transport.close)
        self.session.client.transport.close = False


    def test_badSubsystemDoesNotCreateClient(self):
        """
        When a subsystem request fails, SSHSession.client should not be set.
        """
        ret = self._wrapWithAssertWarns(self.session.requestReceived,
                'subsystem', common.NS('BadSubsystem'))
        self.assertFalse(ret)
        self.assertIdentical(self.session.client, None)


    def test_lookupSubsystem(self):
        """
        When a client requests a subsystem, the SSHSession object should get
        the subsystem by calling avatar.lookupSubsystem, and attach it as
        the client.
        """
        self.session.session = None # old SSHSession didn't have this attribute
        ret = self._wrapWithAssertWarns(self.session.requestReceived,
                'subsystem', common.NS('TestSubsystem') + 'data')
        self.assertTrue(ret)
        self.assertIsInstance(self.session.client, protocol.ProcessProtocol)
        self.assertIdentical(self.session.sessionApplication.processProtocol,
                             self.session.avatar.subsystem)


    def test_lookupSubsystemProtocol(self):
        """
        Test that lookupSubsystem handles being returned a Protocol by wrapping
        it in a ProcessProtocol.  The ProcessProtocol that wraps the Protocol
        should pass attributes along to the protocol.
        """
        self.session.session = None # old SSHSession didn't have this attribute

        ret = self._wrapWithAssertWarns(self.session.requestReceived,
                'subsystem', common.NS('protocol') + 'data')
        self.assertTrue(ret)
        self.assertIsInstance(self.session.client,
                              protocol.ProcessProtocol)
        processProtocol = self.session.sessionApplication.processProtocol
        self.assertIdentical(
            processProtocol.proto,
            self.session.avatar.subsystem)
        self.assertEquals(
            processProtocol.connectionLost,
            processProtocol.proto.connectionLost)
        processProtocol.foo = "foo"
        self.assertEquals(processProtocol.proto.foo, "foo")
        self.assertIdentical(
            processProtocol.transport.proto,
            processProtocol)
        processProtocol.transport.proto.data = ""
        processProtocol.outReceived("something")
        self.assertEquals(processProtocol.transport.proto.data, "something")
        reason = object()
        processProtocol.processEnded(reason)
        self.assertFalse(processProtocol.transport.proto.open)
        self.assertIdentical(processProtocol.transport.proto.reason, reason)


    def test_lookupSubsystemDoesNotNeedISession(self):
        """
        Previously, if one only wanted to implement a subsystem, an ISession
        adapter wasn't needed because subsystems were looked up using the
        lookupSubsystem method on the avatar.
        """
        s = session.SSHSession(avatar=SubsystemOnlyAvatar(),
                               conn=StubConnection())
        ret = self._wrapWithAssertWarns(s.request_subsystem,
                                        common.NS('subsystem') + 'data')
        self.assertTrue(ret)
        self.assertNotIdentical(s.applicationFactory, None)
        self.assertIdentical(s.conn.closes.get(s), None)
        s.eofReceived()
        self.assertTrue(s.conn.closes.get(s))
        # these should not raise errors
        s.closeReceived()
        s.closed()


    def test_lookupSubsystem_data(self):
        """
        After having looked up a subsystem, data should be passed along to the
        client.  Additionally, subsystems were passed the entire request packet
        as data, instead of just the additional data.

        We check for the additional tidle to verify that the data passed
        through the client.
        """
        self.session.session = None # old SSHSession didn't have this attribute
        self.session.dataReceived('1')
        # subsystems didn't get extended data
        self.session.extReceived(connection.EXTENDED_DATA_STDERR, '2')

        self._wrapWithAssertWarns(self.session.requestReceived, 'subsystem',
                                     common.NS('TestSubsystem') + 'data')

        self.assertEquals(self.session.conn.data[self.session],
                ['\x00\x00\x00\x0dTestSubsystemdata~'])
        self.session.dataReceived('more data')
        self.assertEquals(self.session.conn.data[self.session][-1],
                'more data~')


    def test_lookupSubsystem_closeReceived(self):
        """
        SSHSession.closeReceived() should sent a close message to the remote
        side.
        """
        self.session.session = None # old SSHSession didn't have this attribute

        self._wrapWithAssertWarns(self.session.requestReceived, 'subsystem',
                                     common.NS('TestSubsystem') + 'data')

        self.session.closeReceived()
        self.assertTrue(self.session.conn.closes[self.session])


    def assertRequestRaisedRuntimeError(self):
        """
        Assert that the request we just made raised a RuntimeError (and only a
        RuntimeError).
        """
        errors = self.flushLoggedErrors(RuntimeError)
        self.assertEquals(len(errors), 1, "Multiple RuntimeErrors raised: %s" %
                          '\n'.join([repr(error) for error in errors]))
        errors[0].trap(RuntimeError)


    def test_requestShell(self):
        """
        When a client requests a shell, the SSHSession object should get
        the shell by getting an ISession adapter for the avatar, then
        calling openShell() with a ProcessProtocol to attach.
        """
        # gets a shell the first time
        ret = self._wrapWithAssertWarns(self.session.requestReceived, 'shell',
                                        '')
        self.assertTrue(ret)
        self.assertSessionIsStubSession()
        self.assertIsInstance(self.session.client,
                              session.SSHSessionProcessProtocol)
        self.assertIdentical(self.session.session.shellProtocol,
                self.session.client)
        # doesn't get a shell the second time
        self.assertFalse(self.session.requestReceived('shell', ''))
        self.assertRequestRaisedRuntimeError()


    def test_requestShellWithData(self):
        """
        When a client executes a shell, it should be able to give pass data
        back and forth between the local and the remote side.
        """
        ret = self._wrapWithAssertWarns(self.session.requestReceived, 'shell',
                                        '')
        self.assertTrue(ret)
        self.assertSessionIsStubSession()
        self.session.dataReceived('some data\x00')
        self.assertEquals(self.session.session.shellTransport.data,
                          'some data\x00')
        self.assertEquals(self.session.conn.data[self.session],
                          ['some data\x00', '\r\n'])
        self.assertTrue(self.session.session.shellTransport.closed)
        self.assertEquals(self.session.conn.requests[self.session],
                          [('exit-status', '\x00\x00\x00\x00', False)])


    def test_requestExec(self):
        """
        When a client requests a command, the SSHSession object should get
        the command by getting an ISession adapter for the avatar, then
        calling execCommand with a ProcessProtocol to attach and the
        command line.
        """
        ret = self._wrapWithAssertWarns(self.session.requestReceived, 'exec',
                                                      common.NS('failure'))
        self.assertFalse(ret)
        self.assertRequestRaisedRuntimeError()
        self.assertIdentical(self.session.client, None)

        self.assertTrue(self.session.requestReceived('exec',
                                                     common.NS('success')))
        self.assertSessionIsStubSession()
        self.assertIsInstance(self.session.client,
                              session.SSHSessionProcessProtocol)
        self.assertIdentical(self.session.session.execProtocol,
                self.session.client)
        self.assertEquals(self.session.session.execCommandLine,
                'success')


    def test_requestExecWithData(self):
        """
        When a client executes a command, it should be able to give pass data
        back and forth.
        """
        ret = self._wrapWithAssertWarns(self.session.requestReceived, 'exec',
                                                     common.NS('repeat hello'))
        self.assertTrue(ret)
        self.assertSessionIsStubSession()
        self.session.dataReceived('some data')
        self.assertEquals(self.session.session.execTransport.data, 'some data')
        self.assertEquals(self.session.conn.data[self.session],
                          ['hello', 'some data', '\r\n'])
        self.session.eofReceived()
        self.session.closeReceived()
        self.session.closed()
        self.assertTrue(self.session.session.execTransport.closed)
        self.assertEquals(self.session.conn.requests[self.session],
                          [('exit-status', '\x00\x00\x00\x00', False)])


    def test_requestExecBuffering(self):
        """
        Channel buffering should not interfere with the buffering that
        SSHSession does.
        """
        self.session.remoteWindowLeft = 4 # arbitrary, to force channel
                                          # buffering
        self.session.dataReceived(' world')
        self._wrapWithAssertWarns(self.session.requestReceived, 'exec',
                                  common.NS('repeat hello'))
        self.assertEquals(self.session.conn.data[self.session],
                          ['hell'])
        self.session.dataReceived('another line')
        self.session.addWindowBytes(30)
        self.assertEquals(''.join(self.session.conn.data[self.session]),
                          'hello world\r\nanother line\r\n')


    def test_requestPty(self):
        """
        When a client requests a PTY, the SSHSession object should make
        the request by getting an ISession adapter for the avatar, then
        calling getPty with the terminal type, the window size, and any modes
        the client gave us.
        """
        # 'bad' terminal type fails
        ret = self._wrapWithAssertWarns(self.session.requestReceived, 'pty_req',
            session.packRequest_pty_req('bad', (1, 2, 3, 4), []))
        self.assertFalse(ret)
        self.assertSessionIsStubSession()
        self.assertRequestRaisedRuntimeError()
        # 'good' terminal type succeeds
        self.assertTrue(self.session.requestReceived('pty_req',
            session.packRequest_pty_req('good', (1, 2, 3, 4), [])))
        self.assertEquals(self.session.session.ptyRequest,
                ('good', (1, 2, 3, 4), []))


    def test_requestWindowChange(self):
        """
        When the client requests to change the window size, the SSHSession
        object should make the request by getting an ISession adapter for the
        avatar, then calling windowChanged with the new window size.
        """
        ret = self._wrapWithAssertWarns(self.session.requestReceived,
                                        'window_change',
            session.packRequest_window_change((0, 0, 0, 0)))
        self.assertFalse(ret)
        self.assertRequestRaisedRuntimeError()
        self.assertSessionIsStubSession()
        self.assertTrue(self.session.requestReceived('window_change',
            session.packRequest_window_change((1, 2, 3, 4))))
        self.assertEquals(self.session.session.windowChange,
                (1, 2, 3, 4))


    def test_eofReceived(self):
        """
        When an EOF is received and a ISession adapter is present, it should
        be notified of the EOF message.
        """
        self.session.session = session.ISession(self.session.avatar)
        self.session.eofReceived()
        self.assertTrue(self.session.session.gotEOF)


    def test_closeReceived(self):
        """
        When a close is received, the session should send a close message.
        """
        ret = self._wrapWithAssertWarns(self.session.closeReceived)
        self.assertIdentical(ret, None)
        self.assertTrue(self.session.conn.closes[self.session])


    def test_closed(self):
        """
        When a close is received and a ISession adapter is present, it should
        be notified of the close message.
        """
        self.session.session = session.ISession(self.session.avatar)
        self.session.closed()
        self.assertTrue(self.session.session.gotClosed)



class OldSessionWithNoAvatarTestCase(unittest.TestCase):
    """
    Test for the old SSHSession interface.  Several of the old methods
    (request_shell, request_exec, request_pty_req, request_window_change) would
    create a 'session' instance variable from the avatar if one didn't exist
    when they were called.
    """


    def setUp(self):
        self.session = session.SSHSession()
        self.session.avatar = StubOldAvatar()
        self.assertIdentical(self.session.session, None)


    def assertSessionProvidesISession(self):
        """
        self.session.session should provide I{ISession}.
        """
        self.assertTrue(session.ISession.providedBy(self.session.session),
                        "ISession not provided by %r" % self.session.session)


    def _wrapWithAssertWarns(self, function, *args):
        """
        All of the methods that we test give a warning that using an old avatar
        (one that implements ISession instead of ISessionApplication) is
        deprecated.
        """
        return self.assertWarns(DeprecationWarning,
                                "Using an avatar that doesn't implement "
                                "ISessionApplicationFactory is deprecated "
                                "since Twisted 9.0.",
                                __file__, function, *args)


    def test_requestShellGetsSession(self):
        """
        If an ISession adapter isn't already present, request_shell should get
        one.
        """
        self._wrapWithAssertWarns(self.session.requestReceived, 'shell', '')
        self.assertSessionProvidesISession()


    def test_requestExecGetsSession(self):
        """
        If an ISession adapter isn't already present, request_exec should get
        one.
        """
        self._wrapWithAssertWarns(self.session.requestReceived, 'exec',
                                  common.NS('success'))
        self.assertSessionProvidesISession()


    def test_requestPtyReqGetsSession(self):
        """
        If an ISession adapter isn't already present, request_pty_req should
        get one.
        """
        self._wrapWithAssertWarns(self.session.requestReceived, 'pty_req',
                                  session.packRequest_pty_req(
                'term', (0, 0, 0, 0), []))
        self.assertSessionProvidesISession()


    def test_requestWindowChangeGetsSession(self):
        """
        If an ISession adapter isn't already present, request_window_change
        should get one.
        """
        self._wrapWithAssertWarns(self.session.requestReceived,
                                  'window_change',
                                  session.packRequest_window_change(
                (1, 1, 1, 1)))
        self.assertSessionProvidesISession()



class WrapProtocolTestCase(unittest.TestCase):
    """
    A test for the deprecated wrapProtocol function.
    """

    def test_wrapProtocol_Protocol(self):
        """
        L{wrapProtocol}, when passed a L{Protocol} should return something that
        has write() and loseConnection() methods which call the Protocol's
        dataReceived() and connectionLost() methods, respectively.
        """
        protocol = MockProtocol()
        protocol.connectionMade()
        transport = self.callDeprecated(Version('Twisted', 9, 0, 0),
                                        session.wrapProtocol, protocol)
        transport.write('data')
        transport.loseConnection()
        self.assertEquals(protocol.data, 'data')
        protocol.reason.trap(error.ConnectionDone)


    def test_wrapProtocol_ProcessProtocol(self):
        """
        L{wrapProtocol}, when passed a L{ProcessProtocol} should return something that
        has write() and loseConnection() methods which call the ProcessProtocol's
        outReceived() and processEnded() methods, respectively.
        """
        protocol = MockProcessProtocol()
        protocol.connectionMade()
        transport = self.callDeprecated(Version('Twisted', 9, 0, 0),
                                        session.wrapProtocol, protocol)
        transport.write('data')
        transport.loseConnection()
        self.assertEquals(protocol.data, 'data')
        protocol.ended.trap(error.ConnectionDone)



class TestHelpers(unittest.TestCase):
    """
    Tests for the 4 helper functions: parseRequest_* and packRequest_*.
    """


    def test_parseRequest_pty_req(self):
        """
        The payload of a pty-req message is::
            string  terminal
            uint32  columns
            uint32  rows
            uint32  x pixels
            uint32  y pixels
            string  modes

        Modes are::
            byte    mode number
            uint32  mode value
        """
        self.assertEquals(session.parseRequest_pty_req(common.NS('xterm') +
                                                       struct.pack('>4L',
                                                                   1, 2, 3, 4)
                                                       + common.NS(
                    struct.pack('>BL', 5, 6))),
                          ('xterm', (2, 1, 3, 4), [(5, 6)]))


    def test_packRequest_pty_req_old(self):
        """
        See test_parseRequest_pty_req for the payload format.
        """
        def _():
            return session.packRequest_pty_req('xterm', (2, 1, 3, 4),
                                               '\x05\x00\x00\x00\x06')

        packed = self.assertWarns(DeprecationWarning,
                                  "packRequest_pty_req should be packing "
                                  "the modes.",
                                  __file__, _)
        self.assertEquals(packed,
                          common.NS('xterm') + struct.pack('>4L', 1, 2, 3, 4) +
                          common.NS(struct.pack('>BL', 5, 6)))


    def test_packRequest_pty_req(self):
        """
        See test_parseRequest_pty_req for the payload format.
        """
        packed = session.packRequest_pty_req('xterm', (2, 1, 3, 4), [(5, 6)])
        self.assertEquals(packed,
                          common.NS('xterm') + struct.pack('>4L', 1, 2, 3, 4) +
                          common.NS(struct.pack('>BL', 5, 6)))


    def test_parseRequest_window_change(self):
        """
        The payload of a window_change request is::
            uint32  columns
            uint32  rows
            uint32  x pixels
            uint32  y pixels

        parseRequest_window_change() returns (rows, columns, x pixels,
        y pixels).
        """
        self.assertEquals(session.parseRequest_window_change(
                struct.pack('>4L', 1, 2, 3, 4)), (2, 1, 3, 4))


    def test_packRequest_window_change(self):
        """
        See test_parseRequest_window_change for the payload format.
        """
        self.assertEquals(session.packRequest_window_change((2, 1, 3, 4)),
                          struct.pack('>4L', 1, 2, 3, 4))



class SSHSessionProcessProtocolTestCase(unittest.TestCase):
    """
    SSHSessionProcessProtocol is an obsolete class used as a ProcessProtocol
    for executed programs.  It has has a couple of transport methods, namely
    write() and loseConnection()
    """


    def setUp(self):
        self.session = session.SSHSession(conn=StubConnection(),
                remoteWindow=500, remoteMaxPacket=100)
        self.transport = StubTransport()
        self.pp = session.SSHSessionProcessProtocol(self.session)
        self.pp.makeConnection(self.transport)


    def test_init(self):
        """
        SSHSessionProcessProtocol should set self.session to the session passed
        to the __init__ method.
        """
        self.assertEquals(self.pp.session, self.session)


    def test_getSignalName(self):
        """
        _getSignalName should return the name of a signal when given the
        signal number.
        """
        for signalName in session.SUPPORTED_SIGNALS:
            signalName = 'SIG' + signalName
            signalValue = getattr(signal, signalName)
            sshName = self.pp._getSignalName(signalValue)
            self.assertEquals(sshName, signalName,
                              "%i: %s != %s" % (signalValue, sshName,
                                                signalName))


    def test_getSignalNameWithLocalSignal(self):
        """
        If there are signals in the signal module which aren't in the SSH RFC,
        we map their name to [signal name]@[platform].
        """
        signal.SIGTwistedTest = signal.NSIG + 1 # value can't exist normally
        # Force reinitialization of signals
        self.pp._signalNames = None
        self.assertEquals(self.pp._getSignalName(signal.SIGTwistedTest),
                          'SIGTwistedTest@' + sys.platform)


    if getattr(signal, 'SIGALRM', None) is None:
        test_getSignalName.skip = test_getSignalNameWithLocalSignal = \
            "Not all signals available"


    def test_outReceived(self):
        """
        When data is passed to the outReceived method, it should be sent to
        the session's write method.
        """
        self.pp.outReceived('test data')
        self.assertEquals(self.session.conn.data[self.session],
                ['test data'])


    def test_write(self):
        """
        When data is passed to the write method, it should be sent to the
        session channel's write method.
        """
        self.callDeprecated(Version('Twisted', 9, 0, 0), self.pp.write,
                            'test data')
        self.assertEquals(self.session.conn.data[self.session],
                ['test data'])


    def test_errReceived(self):
        """
        When data is passed to the errReceived method, it should be sent to
        the session's writeExtended method.
        """
        self.pp.errReceived('test data')
        self.assertEquals(self.session.conn.extData[self.session],
                [(1, 'test data')])


    def test_inConnectionLost(self):
        """
        When inConnectionLost is called, it should send an EOF message,
        """
        self.pp.inConnectionLost()
        self.assertTrue(self.session.conn.eofs[self.session])


    def test_outConnectionLost(self):
        """
        When outConnectionLost is called and there is no ISession adapter,
        the connection should be closed,
        """
        self.pp.outConnectionLost()
        self.assertTrue(self.session.conn.closes[self.session])


    def test_loseConnection(self):
        """
        When loseConnection() is called, it should call loseConnection
        on the session channel.
        """
        self.callDeprecated(Version('Twisted', 9, 0, 0),self.pp.loseConnection)
        self.assertTrue(self.session.conn.closes[self.session])


    def test_processEndedWithExitCode(self):
        """
        When processEnded is called, if there is an exit code in the reason
        it should be sent in an exit-status method.  The connection should be
        closed.
        """
        self.pp.processEnded(failure.Failure(error.ProcessDone(None)))
        self.assertEquals(self.session.conn.requests[self.session],
                [('exit-status', struct.pack('>I', 0) , False)])
        self.assertTrue(self.session.conn.closes[self.session])


    def test_processEndedWithExitSignalCoreDump(self):
        """
        When processEnded is called, if there is an exit signal in the reason
        it should be sent in an exit-signal message.  The connection should be
        closed.
        """
        self.pp.processEnded(failure.Failure(error.ProcessTerminated(1,
            signal.SIGTERM, 1 << 7))) # 7th bit means core dumped
        self.assertEqual(self.session.conn.requests[self.session],
                [('exit-signal',
                  common.NS('TERM') # signal name
                  + '\x01' # core dumped is true
                  + common.NS('') # error message
                  + common.NS(''), # language tag
                  False)])
        self.assertTrue(self.session.conn.closes[self.session])


    def test_processEndedWithExitSignalNoCoreDump(self):
        """
        When processEnded is called, if there is an exit signal in the
        reason it should be sent in an exit-signal message.  If no
        core was dumped, don't set the core-dump bit.
        """
        self.pp.processEnded(
            failure.Failure(error.ProcessTerminated(1, signal.SIGTERM, 0)))
        # see comments in test_processEndedWithExitSignalCoreDump for the
        # meaning of the parts in the request
        self.assertEqual(self.session.conn.requests[self.session],
                         [('exit-signal', common.NS('TERM') + '\x00' +
                           common.NS('') + common.NS(''), False)])
        self.assertTrue(self.session.conn.closes[self.session])

    if not hasattr(os, 'WCOREDUMP'):
        skipMsg = "can't run this w/o os.WCOREDUMP"
        test_processEndedWithExitSignalCoreDump.skip = skipMsg
        test_processEndedWithExitSignalNoCoreDump.skip = skipMsg



class SSHSessionProcessProtocolApplicationTestCase(unittest.TestCase):
    """
    SSHSessionProcessProtocolApplicationTestCase is an class used to
    connect to a SSHSessionProcessProtocol as an application.
    """


    def test_dataReceived(self):
        """
        When data is received, it should be sent to the transport.
        """
        client = StubClient()
        app = session.SSHSessionProcessProtocolApplication(client)
        app.dataReceived('test data')
        self.assertEquals(client.transport.buf, 'test data')


    def test_extendedDataReceived(self):
        """
        When extended data of the type EXTENDED_DATA_STDERR is
        received, it should be passed along to SSHSessionProcessProtocol's
        transport.writeErr.
        """
        transport = StubTransportWithWriteErr()
        pp = MockProcessProtocol()
        pp.makeConnection(transport)
        app = session.SSHSessionProcessProtocolApplication(pp)
        # 255 is an arbitrary value that's not EXTENDED_DATA_STDERR so the data
        # should be ignored.
        app.extendedDataReceived(255, "ignore this")
        app.extendedDataReceived(connection.EXTENDED_DATA_STDERR, "data")
        self.assertEquals(transport.err, "data")

    def test_extendedDataReceivedWithoutWrteErr(self):
        """
        If the transport doesn't support extended data by implementing
        writeErr, then the extended data should silently be dropped on the
        floor.
        """
        transport = StubTransport()
        pp = MockProcessProtocol()
        pp.makeConnection(transport)
        app = session.SSHSessionProcessProtocolApplication(pp)
        app.extendedDataReceived(connection.EXTENDED_DATA_STDERR, "more")



class SSHSessionClientTestCase(unittest.TestCase):
    """
    SSHSessionClient is an obsolete class used to connect standard IO to
    an SSHSession.
    """


    def test_dataReceived(self):
        """
        When data is received, it should be sent to the transport.
        """
        def _():
            return session.SSHSessionClient()
        client = self.assertWarns(DeprecationWarning,
                                  "twisted.conch.ssh.session.SSHSessionClient "
                                  "was deprecated in Twisted 9.0.0",
                                  __file__,
                                  _)
        client.transport = StubTransport()
        client.dataReceived('test data')
        self.assertEquals(client.transport.buf, 'test data')



class ServerSessionTestCase(unittest.TestCase):
    """
    Tests that verify server functionality of SSHSession.
    """


    def setUp(self):
        self.conn = StubConnection()
        self.avatar = StubNewAvatar()
        self.session = session.SSHSession(remoteWindow=131072,
                remoteMaxPacket=32768, conn=self.conn,
                avatar=self.avatar)


    def assertRequestRaisedError(self):
        """
        Assert that the request we just made raised an error (and only one
        error).
        """
        errors = self.flushLoggedErrors()
        self.assertEquals(len(errors), 1, "Multiple errors raised: %s" %
                          '\n'.join([repr(error) for error in errors]))


    def test_init(self):
        """
        After the session is created, self. client should be None, and
        self..applicationFactory should provide I{ISessionApplicationFactory}.
        """
        self.assertEquals(self.session.client, None)
        self.assertTrue(session.ISessionApplicationFactory.providedBy(
                self.session.applicationFactory),
                        str(self.session.applicationFactory))


    def test_client_data(self):
        """
        SSHSession should pass data and extended data to its client, buffering
        that data if the client isn't present at the time the data is received.
        The client should also be able to send data back to the remote side.
        """
        client = MockApplication()
        self.session.dataReceived('1')
        self.session.extReceived(connection.EXTENDED_DATA_STDERR, '2')
        self.session.extReceived(2, '3')
        self.session._setUpSession(client)
        self.session.dataReceived('out')

        self.assertEquals(client.data, ['1', 'out'])
        # the tilde means the data was sent by the client
        self.assertEquals(self.session.conn.data[self.session],
                          ['1~', 'out~'])

        self.session.extReceived(connection.EXTENDED_DATA_STDERR, 'err')

        self.assertEquals(client.extendedData,
                          [(connection.EXTENDED_DATA_STDERR, '2'),
                           (2, '3'),
                           (connection.EXTENDED_DATA_STDERR, 'err')])
        # the tilde and the incrementing of the data type means the extended
        # data was sent by the client
        self.assertEquals(self.session.conn.extData[self.session],
                          [(connection.EXTENDED_DATA_STDERR + 1, '2~'),
                           (2 + 1, '3~'),
                           (connection.EXTENDED_DATA_STDERR + 1, 'err~')])


    def test_client_closing(self):
        """
        SSHSession should notify the client of EOF and Close messages.
        """
        client = MockApplication()
        self.session._setUpSession(client)
        self.session.eofReceived()
        self.assertTrue(client.gotEOF)
        self.assertFalse(client.hasClosed, 'closed() called during EOF')
        self.session.closeReceived()
        self.assertTrue(client.gotClose)
        self.assertFalse(client.hasClosed,
                         'closed() called during closeReceived')
        self.session.closed()
        self.assertTrue(client.hasClosed, 'closed() not called')


    def test_applicationFactory(self):
        """
        SSHSession should notify the applicationFactory of EOF and close
        messages.
        """
        self.session.eofReceived()
        self.assertFalse(self.session.applicationFactory.inConnectionOpen)
        self.session.closeReceived()
        self.assertFalse(self.session.applicationFactory.outConnectionOpen)
        self.session.closed()
        self.assertTrue(self.session.applicationFactory.ended)


    def test_subsystem(self):
        """
        SSHSession should handle subsystem requests by dispatching to the
        application factory's requestSubsytem() method and connecting to the
        ISessionApplication returned by requestSubsytem().
        """
        ret = self.session.requestReceived('subsystem', common.NS('bad'))
        self.assertFalse(ret)
        self.assertEquals(self.session.client, None)
        ret = self.session.requestReceived('subsystem',
                common.NS('repeat') + 'abc')
        self.assertTrue(ret)
        self.assertTrue(session.ISessionApplication.providedBy(
                self.session.sessionApplication))
        self.assertIdentical(self.session.sessionApplication,
                self.session.applicationFactory.subsystem)
        self.assertFalse(self.session.sessionApplication.hasClosed)
        self.assertEquals(self.session.sessionApplication.packetData, 'abc')
        self.assertEquals(self.session.sessionApplication.channel,
                self.session)


    def test_subsystemError(self):
        """
        If an error is raised in L{SSHSession.request_subsystem}, it's caught
        and logged.
        """
        def raiseError(*args):
            raise RuntimeError("oops")
        self.session.applicationFactory.lookupSubsystem = raiseError
        ret = self.session.requestReceived('subsystem', common.NS('bad'))
        self.assertFalse(ret)
        self.assertRequestRaisedError()


    def test_shell(self):
        """
        Test that SSHSession handles shell requests by dispatching to the
        application factory's openShell() method and connecting itself to the
        ISessionApplication returned by openShell().
        """
        self.assertTrue(self.session.requestReceived('shell', ''))
        self.assertNotEquals(self.session.sessionApplication, None)
        self.assertIdentical(self.session.sessionApplication,
                self.session.applicationFactory.shell)
        self.assertEquals(self.session.sessionApplication.channel,
                self.session)
        self.assertFalse(self.session.sessionApplication.hasClosed)

        # fail if we have a shell already
        self.assertFalse(self.session.requestReceived('shell', ''))
        self.assertRequestRaisedError()


    def test_exec(self):
        """
        Test that SSHSession handles command requests by dispatching to the the
        application factory's execCommand method and connecting itself to the
        ISessionApplication returned by execCommand().
        """
        self.assertTrue(self.session.requestReceived('exec',
            common.NS('good')))
        self.assertNotEquals(self.session.sessionApplication, None)
        self.assertIdentical(self.session.sessionApplication,
                             self.session.applicationFactory.command)
        self.assertEquals(self.session.sessionApplication.channel,
                self.session)
        self.assertEquals(self.session.sessionApplication.command, 'good')
        self.assertFalse(self.session.sessionApplication.hasClosed)

        # fail if we already have a command
        self.assertFalse(self.session.requestReceived('exec',
            common.NS('good')))
        self.assertRequestRaisedError()


    def test_ptyRequest(self):
        """
        Test that SSHSession handles PTY requests by dispatching to the
        application factory's getPTY method.
        """
        term = 'conch'
        windowSize = (80, 25, 0, 0)
        modes = [(0, 1), (2, 3)]
        ret = self.session.requestReceived('pty_req',
                                           session.packRequest_pty_req(
                term, windowSize, modes))
        self.assertTrue(ret)
        self.assertEquals(self.session.applicationFactory.term, term)
        self.assertEquals(self.session.applicationFactory.windowSize,
                          windowSize)
        self.assertEquals(self.session.applicationFactory.modes, modes)


    def test_ptyRequestFailure(self):
        """
        If the PTY request can't be parsed, the request should fail.
        """
        self.assertFalse(self.session.requestReceived('pty_req', ''))
        self.assertRequestRaisedError()


    def test_windowChange(self):
        """
        Test that SSHSession handles window size change requests by dispatching
        to the application factory's windowChanged method.
        """
        windowSize = (1, 1, 1, 1)
        ret = self.session.requestReceived('window_change',
                                           session.packRequest_window_change(
                windowSize))
        self.assertTrue(ret)
        self.assertEquals(self.session.applicationFactory.windowSize, windowSize)

    def test_windowChangeFailure(self):
        """
        If the window change request can't be parsed, the request should fail.
        """
        self.assertFalse(self.session.requestReceived('window_change', ''))
        self.assertRequestRaisedError()



class ClientSessionTestCase(unittest.TestCase):
    """
    Test methods that use SSHSession as a client.
    """


    def setUp(self):
        self.conn = StubConnection()
        self.session = session.SSHSession(remoteWindow=131072,
                remoteMaxPacket=32768, conn=self.conn)


    def test_getPty(self):
        """
        Test that getPty sends a correctly formatted request.  See the
        TestHelpers class for a description of this packet.
        """
        terminalType = 'term'
        windowSize = (80, 25, 0, 0)
        modes = [(0, 1), (2, 3)]
        d = self.session.getPty('term', (80, 25, 0, 0), [(0, 1), (2, 3)],
                True)
        def check(value):
            self.assertEquals(self.conn.requests[self.session],
                              [('pty-req', session.packRequest_pty_req(
                            terminalType,
                            windowSize,
                            modes), True)])
            self.assertEquals(self.session.getPty('term', (80, 25, 0, 0), []),
                              None)

        return d.addCallback(check)


    def test_changeWindowSize(self):
        """
        Test that windowChange sends the correct request.  See the TestHelpers
        class for a description of this packet.
        """
        size = (80, 25, 0, 0)
        d = self.session.changeWindowSize(size, True)
        def check(value):
            self.assertEquals(self.conn.requests[self.session],
                              [('window-change',
                                session.packRequest_window_change(size),
                                True)])

            self.assertEquals(self.session.changeWindowSize(size),
                    None)
        return d.addCallback(check)


    def test_openSubsystem(self):
        """
        Test that openSubsystem sends the correct request.  Format::

            string subsystem type
            [any other packet data]
        """
        d = self.session.openSubsystem('repeat', 'data', True)
        def check(value):
            self.assertEquals(self.conn.requests[self.session],
                    [('subsystem', common.NS('repeat') + 'data', True)])
            self.assertEquals(self.session.openSubsystem('repeat', 'data'),
                    None)
        return d.addCallback(check)


    def test_openShell(self):
        """
        Test that openShell sends the correct request.  No data.
        """
        d = self.session.openShell(True)
        def check(value):
            self.assertEquals(self.conn.requests[self.session],
                    [('shell', '', True)])
            self.assertEquals(self.session.openShell(), None)
        d.addCallback(check)
        return d


    def test_execCommand(self):
        """
        Test that execCommand sends the correct request.  Format::

            string command line
        """
        d = self.session.execCommand('true', True)
        def check(value):
            self.assertEquals(self.conn.requests[self.session],
                    [('exec', common.NS('true'), True)])
            self.assertEquals(self.session.execCommand('true'), None)
        d.addCallback(check)
        return d



class KeyboardInterruptTestCase(unittest.TestCase):
    """
    Tests for the special handling of KeyboardInterrupt in SSHSession.
    """


    def setUp(self):
        self.session = session.SSHSession()
        self.session.applicationFactory = KeyboardInterruptApplicationFactory()


    def test_lookupSubsystem(self):
        """
        A KeyboardInterrupt raised during lookupSubsystem should be re-raised.
        """
        self.assertRaises(KeyboardInterrupt,
                          self.session.request_subsystem,
                          common.NS('ignored'))


    def test_openShell(self):
        """
        A KeyboardInterrupt raised during openShell should be re-raised.
        """
        self.assertRaises(KeyboardInterrupt,
                          self.session.request_shell,
                          common.NS('ignored'))


    def test_execCommand(self):
        """
        A KeyboardInterrupt raised during execCommand should be re-raised.
        """
        self.assertRaises(KeyboardInterrupt,
                          self.session.request_exec,
                          common.NS('ignored'))


    def test_getPTY(self):
        """
        A KeyboardInterrupt raised during getPTY should be re-raised.
        """
        self.assertRaises(KeyboardInterrupt,
                          self.session.request_pty_req,
                          session.packRequest_pty_req('ignored',
                                                      (0, 0, 0, 0), ()))


    def test_windowChanged(self):
        """
        A KeyboardInterrupt raised during windowChanged should be re-raised.
        """
        self.assertRaises(KeyboardInterrupt,
                          self.session.request_window_change,
                          session.packRequest_window_change((0, 0, 0, 0)))
>>>>>>> .merge-right.r27072
