# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the 'session' channel implementation in twisted.conch.ssh.session.

See also RFC 4254.
"""

import os, signal, sys, struct

from zope.interface import implements

from twisted.internet.address import IPv4Address
from twisted.internet.error import ProcessTerminated, ProcessDone
from twisted.python.failure import Failure
from twisted.conch.ssh import common, session, connection
from twisted.internet import defer, protocol, error
from twisted.python import components, failure
from twisted.trial import unittest



class SubsystemOnlyAvatar(object):
    """
    A stub class representing an avatar that is only useful for
    getting a subsystem.
    """


    def lookupSubsystem(self, name, data):
        """
        If the other side requests the 'subsystem' subsystem, allow it by
        returning a MockProtocol to implement it.  Otherwise, return
        None which is interpreted by SSHSession as a failure.
        """
        if name == 'subsystem':
            return MockProtocol()



class StubAvatar:
    """
    A stub class representing the avatar representing the authenticated user.
    It implements the I{ISession} interface.
    """


    def lookupSubsystem(self, name, data):
        """
        If the user requests the TestSubsystem subsystem, connect them to a
        MockProtocol.  If they request neither, then None is returned which is
        interpreted by SSHSession as a failure.
        """
        if name == 'TestSubsystem':
            self.subsystem = MockProtocol()
            self.subsystem.packetData = data
            return self.subsystem



class StubSessionForStubAvatar(object):
    """
    A stub ISession implementation for our StubAvatar.  The instance
    variables generally keep track of method invocations so that we can test
    that the methods were called.

    @ivar avatar: the L{StubAvatar} we are adapting.
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



components.registerAdapter(StubSessionForStubAvatar, StubAvatar,
        session.ISession)




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
        self.closed = False
        self.data = ''
        processProtocol.makeConnection(self)


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



class StubConnection(object):
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


    def __init__(self, transport=None):
        """
        Initialize our instance variables.
        """
        self.data = {}
        self.extData = {}
        self.requests = {}
        self.eofs = {}
        self.closes = {}
        self.transport = transport


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


    def getPeer(self):
        """
        Return an arbitrary L{IAddress}.
        """
        return IPv4Address('TCP', 'remotehost', 8888)


    def getHost(self):
        """
        Return an arbitrary L{IAddress}.
        """
        return IPv4Address('TCP', 'localhost', 9999)


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



class SessionInterfaceTestCase(unittest.TestCase):
    """
    Tests for the SSHSession class interface.  This interface is not ideal, but
    it is tested in order to maintain backwards compatibility.
    """


    def setUp(self):
        """
        Make an SSHSession object to test.  Give the channel some window
        so that it's allowed to send packets.  500 and 100 are arbitrary
        values.
        """
        self.session = session.SSHSession(remoteWindow=500,
                remoteMaxPacket=100, conn=StubConnection(),
                avatar=StubAvatar())


    def assertSessionIsStubSession(self):
        """
        Asserts that self.session.session is an instance of
        StubSessionForStubOldAvatar.
        """
        self.assertIsInstance(self.session.session,
                              StubSessionForStubAvatar)


    def test_init(self):
        """
        SSHSession initializes its buffer (buf), client, and ISession adapter.
        The avatar should not need to be adaptable to an ISession immediately.
        """
        s = session.SSHSession(avatar=object) # use object because it doesn't
                                              # have an adapter
        self.assertEqual(s.buf, '')
        self.assertIs(s.client, None)
        self.assertIs(s.session, None)


    def test_client_dataReceived(self):
        """
        SSHSession.dataReceived() passes data along to a client.  If the data
        comes before there is a client, the data should be discarded.
        """
        self.session.dataReceived('1')
        self.session.client = StubClient()
        self.session.dataReceived('2')
        self.assertEqual(self.session.client.transport.buf, '2')

    def test_client_extReceived(self):
        """
        SSHSession.extReceived() passed data of type EXTENDED_DATA_STDERR along
        to the client.  If the data comes before there is a client, or if the
        data is not of type EXTENDED_DATA_STDERR, it is discared.
        """
        self.session.extReceived(connection.EXTENDED_DATA_STDERR, '1')
        self.session.extReceived(255, '2') # 255 is arbitrary
        self.session.client = StubClient()
        self.session.extReceived(connection.EXTENDED_DATA_STDERR, '3')
        self.assertEqual(self.session.client.transport.err, '3')


    def test_client_extReceivedWithoutWriteErr(self):
        """
        SSHSession.extReceived() should handle the case where the transport
        on the client doesn't have a writeErr method.
        """
        client = self.session.client = StubClient()
        client.transport = StubTransport() # doesn't have writeErr

        # should not raise an error
        self.session.extReceived(connection.EXTENDED_DATA_STDERR, 'ignored')



    def test_client_closed(self):
        """
        SSHSession.closed() should tell the transport connected to the client
        that the connection was lost.
        """
        self.session.client = StubClient()
        self.session.closed()
        self.assertTrue(self.session.client.transport.close)
        self.session.client.transport.close = False


    def test_badSubsystemDoesNotCreateClient(self):
        """
        When a subsystem request fails, SSHSession.client should not be set.
        """
        ret = self.session.requestReceived(
            'subsystem', common.NS('BadSubsystem'))
        self.assertFalse(ret)
        self.assertIs(self.session.client, None)


    def test_lookupSubsystem(self):
        """
        When a client requests a subsystem, the SSHSession object should get
        the subsystem by calling avatar.lookupSubsystem, and attach it as
        the client.
        """
        ret = self.session.requestReceived(
            'subsystem', common.NS('TestSubsystem') + 'data')
        self.assertTrue(ret)
        self.assertIsInstance(self.session.client, protocol.ProcessProtocol)
        self.assertIs(self.session.client.transport.proto,
                      self.session.avatar.subsystem)



    def test_lookupSubsystemDoesNotNeedISession(self):
        """
        Previously, if one only wanted to implement a subsystem, an ISession
        adapter wasn't needed because subsystems were looked up using the
        lookupSubsystem method on the avatar.
        """
        s = session.SSHSession(avatar=SubsystemOnlyAvatar(),
                               conn=StubConnection())
        ret = s.request_subsystem(
            common.NS('subsystem') + 'data')
        self.assertTrue(ret)
        self.assertIsNot(s.client, None)
        self.assertIs(s.conn.closes.get(s), None)
        s.eofReceived()
        self.assertTrue(s.conn.closes.get(s))
        # these should not raise errors
        s.loseConnection()
        s.closed()


    def test_lookupSubsystem_data(self):
        """
        After having looked up a subsystem, data should be passed along to the
        client.  Additionally, subsystems were passed the entire request packet
        as data, instead of just the additional data.

        We check for the additional tidle to verify that the data passed
        through the client.
        """
        #self.session.dataReceived('1')
        # subsystems didn't get extended data
        #self.session.extReceived(connection.EXTENDED_DATA_STDERR, '2')

        self.session.requestReceived('subsystem',
                                     common.NS('TestSubsystem') + 'data')

        self.assertEqual(self.session.conn.data[self.session],
                ['\x00\x00\x00\x0dTestSubsystemdata~'])
        self.session.dataReceived('more data')
        self.assertEqual(self.session.conn.data[self.session][-1],
                'more data~')


    def test_lookupSubsystem_closeReceived(self):
        """
        SSHSession.closeReceived() should sent a close message to the remote
        side.
        """
        self.session.requestReceived('subsystem',
                                     common.NS('TestSubsystem') + 'data')

        self.session.closeReceived()
        self.assertTrue(self.session.conn.closes[self.session])


    def assertRequestRaisedRuntimeError(self):
        """
        Assert that the request we just made raised a RuntimeError (and only a
        RuntimeError).
        """
        errors = self.flushLoggedErrors(RuntimeError)
        self.assertEqual(len(errors), 1, "Multiple RuntimeErrors raised: %s" %
                          '\n'.join([repr(error) for error in errors]))
        errors[0].trap(RuntimeError)


    def test_requestShell(self):
        """
        When a client requests a shell, the SSHSession object should get
        the shell by getting an ISession adapter for the avatar, then
        calling openShell() with a ProcessProtocol to attach.
        """
        # gets a shell the first time
        ret = self.session.requestReceived('shell', '')
        self.assertTrue(ret)
        self.assertSessionIsStubSession()
        self.assertIsInstance(self.session.client,
                              session.SSHSessionProcessProtocol)
        self.assertIs(self.session.session.shellProtocol, self.session.client)
        # doesn't get a shell the second time
        self.assertFalse(self.session.requestReceived('shell', ''))
        self.assertRequestRaisedRuntimeError()


    def test_requestShellWithData(self):
        """
        When a client executes a shell, it should be able to give pass data
        back and forth between the local and the remote side.
        """
        ret = self.session.requestReceived('shell', '')
        self.assertTrue(ret)
        self.assertSessionIsStubSession()
        self.session.dataReceived('some data\x00')
        self.assertEqual(self.session.session.shellTransport.data,
                          'some data\x00')
        self.assertEqual(self.session.conn.data[self.session],
                          ['some data\x00', '\r\n'])
        self.assertTrue(self.session.session.shellTransport.closed)
        self.assertEqual(self.session.conn.requests[self.session],
                          [('exit-status', '\x00\x00\x00\x00', False)])


    def test_requestExec(self):
        """
        When a client requests a command, the SSHSession object should get
        the command by getting an ISession adapter for the avatar, then
        calling execCommand with a ProcessProtocol to attach and the
        command line.
        """
        ret = self.session.requestReceived('exec',
                                           common.NS('failure'))
        self.assertFalse(ret)
        self.assertRequestRaisedRuntimeError()
        self.assertIs(self.session.client, None)

        self.assertTrue(self.session.requestReceived('exec',
                                                     common.NS('success')))
        self.assertSessionIsStubSession()
        self.assertIsInstance(self.session.client,
                              session.SSHSessionProcessProtocol)
        self.assertIs(self.session.session.execProtocol, self.session.client)
        self.assertEqual(self.session.session.execCommandLine,
                'success')


    def test_requestExecWithData(self):
        """
        When a client executes a command, it should be able to give pass data
        back and forth.
        """
        ret = self.session.requestReceived('exec',
                                           common.NS('repeat hello'))
        self.assertTrue(ret)
        self.assertSessionIsStubSession()
        self.session.dataReceived('some data')
        self.assertEqual(self.session.session.execTransport.data, 'some data')
        self.assertEqual(self.session.conn.data[self.session],
                          ['hello', 'some data', '\r\n'])
        self.session.eofReceived()
        self.session.closeReceived()
        self.session.closed()
        self.assertTrue(self.session.session.execTransport.closed)
        self.assertEqual(self.session.conn.requests[self.session],
                          [('exit-status', '\x00\x00\x00\x00', False)])


    def test_requestPty(self):
        """
        When a client requests a PTY, the SSHSession object should make
        the request by getting an ISession adapter for the avatar, then
        calling getPty with the terminal type, the window size, and any modes
        the client gave us.
        """
        # 'bad' terminal type fails
        ret = self.session.requestReceived(
            'pty_req',  session.packRequest_pty_req(
                'bad', (1, 2, 3, 4), ''))
        self.assertFalse(ret)
        self.assertSessionIsStubSession()
        self.assertRequestRaisedRuntimeError()
        # 'good' terminal type succeeds
        self.assertTrue(self.session.requestReceived('pty_req',
            session.packRequest_pty_req('good', (1, 2, 3, 4), '')))
        self.assertEqual(self.session.session.ptyRequest,
                ('good', (1, 2, 3, 4), []))


    def test_requestWindowChange(self):
        """
        When the client requests to change the window size, the SSHSession
        object should make the request by getting an ISession adapter for the
        avatar, then calling windowChanged with the new window size.
        """
        ret = self.session.requestReceived(
            'window_change',
            session.packRequest_window_change((0, 0, 0, 0)))
        self.assertFalse(ret)
        self.assertRequestRaisedRuntimeError()
        self.assertSessionIsStubSession()
        self.assertTrue(self.session.requestReceived('window_change',
            session.packRequest_window_change((1, 2, 3, 4))))
        self.assertEqual(self.session.session.windowChange,
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
        ret = self.session.closeReceived()
        self.assertIs(ret, None)
        self.assertTrue(self.session.conn.closes[self.session])


    def test_closed(self):
        """
        When a close is received and a ISession adapter is present, it should
        be notified of the close message.
        """
        self.session.session = session.ISession(self.session.avatar)
        self.session.closed()
        self.assertTrue(self.session.session.gotClosed)



class SessionWithNoAvatarTestCase(unittest.TestCase):
    """
    Test for the SSHSession interface.  Several of the methods (request_shell,
    request_exec, request_pty_req, request_window_change) would create a
    'session' instance variable from the avatar if one didn't exist when they
    were called.
    """


    def setUp(self):
        self.session = session.SSHSession()
        self.session.avatar = StubAvatar()
        self.assertIs(self.session.session, None)


    def assertSessionProvidesISession(self):
        """
        self.session.session should provide I{ISession}.
        """
        self.assertTrue(session.ISession.providedBy(self.session.session),
                        "ISession not provided by %r" % self.session.session)


    def test_requestShellGetsSession(self):
        """
        If an ISession adapter isn't already present, request_shell should get
        one.
        """
        self.session.requestReceived('shell', '')
        self.assertSessionProvidesISession()


    def test_requestExecGetsSession(self):
        """
        If an ISession adapter isn't already present, request_exec should get
        one.
        """
        self.session.requestReceived('exec',
                                     common.NS('success'))
        self.assertSessionProvidesISession()


    def test_requestPtyReqGetsSession(self):
        """
        If an ISession adapter isn't already present, request_pty_req should
        get one.
        """
        self.session.requestReceived('pty_req',
                                     session.packRequest_pty_req(
                'term', (0, 0, 0, 0), ''))
        self.assertSessionProvidesISession()


    def test_requestWindowChangeGetsSession(self):
        """
        If an ISession adapter isn't already present, request_window_change
        should get one.
        """
        self.session.requestReceived(
            'window_change',
            session.packRequest_window_change(
                (1, 1, 1, 1)))
        self.assertSessionProvidesISession()



class WrappersTestCase(unittest.TestCase):
    """
    A test for the wrapProtocol and wrapProcessProtocol functions.
    """

    def test_wrapProtocol(self):
        """
        L{wrapProtocol}, when passed a L{Protocol} should return something that
        has write(), writeSequence(), loseConnection() methods which call the
        Protocol's dataReceived() and connectionLost() methods, respectively.
        """
        protocol = MockProtocol()
        protocol.transport = StubTransport()
        protocol.connectionMade()
        wrapped = session.wrapProtocol(protocol)
        wrapped.dataReceived('dataReceived')
        self.assertEqual(protocol.transport.buf, 'dataReceived')
        wrapped.write('data')
        wrapped.writeSequence(['1', '2'])
        wrapped.loseConnection()
        self.assertEqual(protocol.data, 'data12')
        protocol.reason.trap(error.ConnectionDone)

    def test_wrapProcessProtocol_Protocol(self):
        """
        L{wrapPRocessProtocol}, when passed a L{Protocol} should return
        something that follows the L{IProcessProtocol} interface, with
        connectionMade() mapping to connectionMade(), outReceived() mapping to
        dataReceived() and processEnded() mapping to connectionLost().
        """
        protocol = MockProtocol()
        protocol.transport = StubTransport()
        process_protocol = session.wrapProcessProtocol(protocol)
        process_protocol.connectionMade()
        process_protocol.outReceived('data')
        self.assertEqual(protocol.transport.buf, 'data~')
        process_protocol.processEnded(failure.Failure(
            error.ProcessTerminated(0, None, None)))
        protocol.reason.trap(error.ProcessTerminated)



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
        self.assertEqual(session.parseRequest_pty_req(common.NS('xterm') +
                                                       struct.pack('>4L',
                                                                   1, 2, 3, 4)
                                                       + common.NS(
                    struct.pack('>BL', 5, 6))),
                          ('xterm', (2, 1, 3, 4), [(5, 6)]))


    def test_packRequest_pty_req_old(self):
        """
        See test_parseRequest_pty_req for the payload format.
        """
        packed = session.packRequest_pty_req('xterm', (2, 1, 3, 4),
                                             '\x05\x00\x00\x00\x06')

        self.assertEqual(packed,
                          common.NS('xterm') + struct.pack('>4L', 1, 2, 3, 4) +
                          common.NS(struct.pack('>BL', 5, 6)))


    def test_packRequest_pty_req(self):
        """
        See test_parseRequest_pty_req for the payload format.
        """
        packed = session.packRequest_pty_req('xterm', (2, 1, 3, 4),
                                             '\x05\x00\x00\x00\x06')
        self.assertEqual(packed,
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
        self.assertEqual(session.parseRequest_window_change(
                struct.pack('>4L', 1, 2, 3, 4)), (2, 1, 3, 4))


    def test_packRequest_window_change(self):
        """
        See test_parseRequest_window_change for the payload format.
        """
        self.assertEqual(session.packRequest_window_change((2, 1, 3, 4)),
                          struct.pack('>4L', 1, 2, 3, 4))



class SSHSessionProcessProtocolTestCase(unittest.TestCase):
    """
    Tests for L{SSHSessionProcessProtocol}.
    """

    def setUp(self):
        self.transport = StubTransport()
        self.session = session.SSHSession(
            conn=StubConnection(self.transport), remoteWindow=500,
            remoteMaxPacket=100)
        self.pp = session.SSHSessionProcessProtocol(self.session)
        self.pp.makeConnection(self.transport)


    def assertSessionClosed(self):
        """
        Assert that C{self.session} is closed.
        """
        self.assertTrue(self.session.conn.closes[self.session])


    def assertRequestsEqual(self, expectedRequests):
        """
        Assert that C{self.session} has sent the C{expectedRequests}.
        """
        self.assertEqual(
            self.session.conn.requests[self.session],
            expectedRequests)


    def test_init(self):
        """
        SSHSessionProcessProtocol should set self.session to the session passed
        to the __init__ method.
        """
        self.assertEqual(self.pp.session, self.session)


    def test_getHost(self):
        """
        SSHSessionProcessProtocol.getHost() just delegates to its
        session.conn.transport.getHost().
        """
        self.assertEqual(
            self.session.conn.transport.getHost(), self.pp.getHost())


    def test_getPeer(self):
        """
        SSHSessionProcessProtocol.getPeer() just delegates to its
        session.conn.transport.getPeer().
        """
        self.assertEqual(
            self.session.conn.transport.getPeer(), self.pp.getPeer())


    def test_connectionMade(self):
        """
        SSHSessionProcessProtocol.connectionMade() should check if there's a
        'buf' attribute on its session and write it to the transport if so.
        """
        self.session.buf = 'buffer'
        self.pp.connectionMade()
        self.assertEqual(self.transport.buf, 'buffer')


    def test_getSignalName(self):
        """
        _getSignalName should return the name of a signal when given the
        signal number.
        """
        for signalName in session.SUPPORTED_SIGNALS:
            signalName = 'SIG' + signalName
            signalValue = getattr(signal, signalName)
            sshName = self.pp._getSignalName(signalValue)
            self.assertEqual(sshName, signalName,
                              "%i: %s != %s" % (signalValue, sshName,
                                                signalName))


    def test_getSignalNameWithLocalSignal(self):
        """
        If there are signals in the signal module which aren't in the SSH RFC,
        we map their name to [signal name]@[platform].
        """
        signal.SIGTwistedTest = signal.NSIG + 1 # value can't exist normally
        # Force reinitialization of signals
        self.pp._signalValuesToNames = None
        self.assertEqual(self.pp._getSignalName(signal.SIGTwistedTest),
                          'SIGTwistedTest@' + sys.platform)


    if getattr(signal, 'SIGALRM', None) is None:
        test_getSignalName.skip = test_getSignalNameWithLocalSignal.skip = \
            "Not all signals available"


    def test_outReceived(self):
        """
        When data is passed to the outReceived method, it should be sent to
        the session's write method.
        """
        self.pp.outReceived('test data')
        self.assertEqual(self.session.conn.data[self.session],
                ['test data'])


    def test_write(self):
        """
        When data is passed to the write method, it should be sent to the
        session channel's write method.
        """
        self.pp.write('test data')
        self.assertEqual(self.session.conn.data[self.session],
                ['test data'])

    def test_writeSequence(self):
        """
        When a sequence is passed to the writeSequence method, it should be
        joined together and sent to the session channel's write method.
        """
        self.pp.writeSequence(['test ', 'data'])
        self.assertEqual(self.session.conn.data[self.session],
                ['test data'])


    def test_errReceived(self):
        """
        When data is passed to the errReceived method, it should be sent to
        the session's writeExtended method.
        """
        self.pp.errReceived('test data')
        self.assertEqual(self.session.conn.extData[self.session],
                [(1, 'test data')])


    def test_outConnectionLost(self):
        """
        When outConnectionLost and errConnectionLost are both called, we should
        send an EOF message.
        """
        self.pp.outConnectionLost()
        self.assertFalse(self.session in self.session.conn.eofs)
        self.pp.errConnectionLost()
        self.assertTrue(self.session.conn.eofs[self.session])


    def test_errConnectionLost(self):
        """
        Make sure reverse ordering of events in test_outConnectionLost also
        sends EOF.
        """
        self.pp.errConnectionLost()
        self.assertFalse(self.session in self.session.conn.eofs)
        self.pp.outConnectionLost()
        self.assertTrue(self.session.conn.eofs[self.session])


    def test_loseConnection(self):
        """
        When loseConnection() is called, it should call loseConnection
        on the session channel.
        """
        self.pp.loseConnection()
        self.assertTrue(self.session.conn.closes[self.session])


    def test_connectionLost(self):
        """
        When connectionLost() is called, it should call loseConnection()
        on the session channel.
        """
        self.pp.connectionLost(failure.Failure(
                ProcessDone(0)))


    def test_processEndedWithExitCode(self):
        """
        When processEnded is called, if there is an exit code in the reason
        it should be sent in an exit-status method.  The connection should be
        closed.
        """
        self.pp.processEnded(Failure(ProcessDone(None)))
        self.assertRequestsEqual(
            [('exit-status', struct.pack('>I', 0) , False)])
        self.assertSessionClosed()


    def test_processEndedWithExitSignalCoreDump(self):
        """
        When processEnded is called, if there is an exit signal in the reason
        it should be sent in an exit-signal message.  The connection should be
        closed.
        """
        self.pp.processEnded(
            Failure(ProcessTerminated(1,
                signal.SIGTERM, 1 << 7))) # 7th bit means core dumped
        self.assertRequestsEqual(
            [('exit-signal',
              common.NS('TERM') # signal name
              + '\x01' # core dumped is true
              + common.NS('') # error message
              + common.NS(''), # language tag
              False)])
        self.assertSessionClosed()


    def test_processEndedWithExitSignalNoCoreDump(self):
        """
        When processEnded is called, if there is an exit signal in the
        reason it should be sent in an exit-signal message.  If no
        core was dumped, don't set the core-dump bit.
        """
        self.pp.processEnded(
            Failure(ProcessTerminated(1, signal.SIGTERM, 0)))
        # see comments in test_processEndedWithExitSignalCoreDump for the
        # meaning of the parts in the request
        self.assertRequestsEqual(
             [('exit-signal', common.NS('TERM') + '\x00' + common.NS('') +
               common.NS(''), False)])
        self.assertSessionClosed()


    if getattr(os, 'WCOREDUMP', None) is None:
        skipMsg = "can't run this w/o os.WCOREDUMP"
        test_processEndedWithExitSignalCoreDump.skip = skipMsg
        test_processEndedWithExitSignalNoCoreDump.skip = skipMsg



class SSHSessionClientTestCase(unittest.TestCase):
    """
    SSHSessionClient is an obsolete class used to connect standard IO to
    an SSHSession.
    """


    def test_dataReceived(self):
        """
        When data is received, it should be sent to the transport.
        """
        client = session.SSHSessionClient()
        client.transport = StubTransport()
        client.dataReceived('test data')
        self.assertEqual(client.transport.buf, 'test data')
