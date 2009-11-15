# -*- test-case-name: twisted.conch.test.test_ssh -*-
# Copyright (c) 2001-2009 Twisted Matrix Laboratories.
# See LICENSE for details.

import struct

try:
    import Crypto.Cipher.DES3
except ImportError:
    Crypto = None

try:
    import pyasn1
except ImportError:
    pyasn1 = None

from twisted.conch.ssh import common, session, forwarding
from twisted.conch import avatar, error
from twisted.conch.test.keydata import publicRSA_openssh, privateRSA_openssh
from twisted.conch.test.keydata import publicDSA_openssh, privateDSA_openssh
from twisted.cred import portal
from twisted.internet import defer, protocol, reactor
from twisted.internet.error import ProcessTerminated
from twisted.python import failure, log
from twisted.trial import unittest
from twisted.protocols.loopback import loopbackAsync

from zope.interface import implements



class ConchTestRealm:
    """
    Realm generating avatars for an authenticated users.
    """
    implements(portal.IRealm)

    def __init__(self, avatar=None):
        """
        Initialize class with a avatar.
        @param avatar: an instance of C{avatar.ConchUser}.
        """
        if avatar is None:
            avatar = ConchTestAvatar()
        self.avatar = avatar


    def requestAvatar(self, avatarID, mind, *interfaces):
        """
        Return a new avatar. If avatar implements a C{logout} method it'll be
        invoked at the end of avatar's existence.
        """
        unittest.assertEquals(avatarID, 'testuser')
        logout = getattr(self.avatar, 'logout', lambda: None)
        if not callable(logout):
            logout = lambda: None
        return interfaces[0], self.avatar, logout



class ConchTestBaseAvatar(avatar.ConchUser):
    """
    Base class for creating avatars.
    """


    def __init__(self):
        """
        Add C{session.SSHSession} to avaliable channels.
        """
        avatar.ConchUser.__init__(self)
        self.channelLookup.update({'session': session.SSHSession})



class ConchTestAvatar(ConchTestBaseAvatar):
    loggedOut = False

    def __init__(self):
        ConchTestBaseAvatar.__init__(self)
        self.listeners = {}
        self.channelLookup.update({'direct-tcpip':
                                   forwarding.openConnectForwardingClient})
        self.subsystemLookup.update({'crazy': CrazySubsystem,
            'test_connectionLost': TestConnectionLostSubsystem})


    def global_foo(self, data):
        unittest.assertEquals(data, 'bar')
        return 1


    def global_foo_2(self, data):
        unittest.assertEquals(data, 'bar2')
        return 1, 'data'


    def global_tcpip_forward(self, data):
        host, port = forwarding.unpackGlobal_tcpip_forward(data)
        try: listener = reactor.listenTCP(port,
                forwarding.SSHListenForwardingFactory(self.conn,
                    (host, port),
                    forwarding.SSHListenServerForwardingChannel),
                interface = host)
        except:
            log.err()
            unittest.fail("something went wrong with remote->local forwarding")
            return 0
        else:
            self.listeners[(host, port)] = listener
            return 1


    def global_cancel_tcpip_forward(self, data):
        host, port = forwarding.unpackGlobal_tcpip_forward(data)
        listener = self.listeners.get((host, port), None)
        if not listener:
            return 0
        del self.listeners[(host, port)]
        listener.stopListening()
        return 1


    def logout(self):
        self.loggedOut = True
        for listener in self.listeners.values():
            log.msg('stopListening %s' % listener)
            listener.stopListening()



class ConchSessionForTestAvatar:
    implements(session.ISession)

    def __init__(self, avatar):
        unittest.assert_(isinstance(avatar, ConchTestAvatar))
        self.avatar = avatar
        self.cmd = None
        self.proto = None
        self.ptyReq = False
        self.eof = 0


    def getPty(self, term, windowSize, attrs):
        log.msg('pty req')
        unittest.assertEquals(term, 'conch-test-term')
        unittest.assertEquals(windowSize, (24, 80, 0, 0))
        self.ptyReq = True


    def openShell(self, proto):
        log.msg('openning shell')
        unittest.assertEquals(self.ptyReq, True)
        self.proto = proto
        EchoTransport(proto)
        self.cmd = 'shell'


    def execCommand(self, proto, cmd):
        self.cmd = cmd
        unittest.assert_(cmd.split()[0] in ['false', 'echo', 'secho', 'eecho','jumboliah'],
                'invalid command: %s' % cmd.split()[0])
        if cmd == 'jumboliah':
            raise error.ConchError('bad exec')
        self.proto = proto
        f = cmd.split()[0]
        if f == 'false':
            FalseTransport(proto)
        elif f == 'echo':
            t = EchoTransport(proto)
            t.write(cmd[5:])
            t.loseConnection()
        elif f == 'secho':
            t = SuperEchoTransport(proto)
            t.write(cmd[6:])
            t.loseConnection()
        elif f == 'eecho':
            t = ErrEchoTransport(proto)
            t.write(cmd[6:])
            t.loseConnection()
        self.avatar.conn.transport.expectedLoseConnection = 1


    def eofReceived(self):
        self.eof = 1


    def closed(self):
        log.msg('closed cmd "%s"' % self.cmd)
        if self.cmd == 'echo hello':
            rwl = self.proto.session.remoteWindowLeft
            unittest.assertEquals(rwl, 4)
        elif self.cmd == 'eecho hello':
            rwl = self.proto.session.remoteWindowLeft
            unittest.assertEquals(rwl, 4)
        elif self.cmd == 'shell':
            unittest.assert_(self.eof)


class ConchSessionTestLoseConnection:
    """
    Test if closing client's session is raising an exception.
    """
    implements(session.ISession)

    def __init__(self, avatar):
        """
        Initialize class with a avatar.
        """
        self.avatar = avatar


    def execCommand(self, proto, cmd):
        """
        Try to close client's side connection.
        """
        proto.loseConnection()


    def closed(self):
        pass



from twisted.python import components
components.registerAdapter(ConchSessionForTestAvatar, ConchTestAvatar, session.ISession)
components.registerAdapter(ConchSessionTestLoseConnection, ConchTestBaseAvatar, session.ISession)



class CrazySubsystem(protocol.Protocol):

    def __init__(self, *args, **kw):
        pass


    def connectionMade(self):
        """
        good ... good
        """



class TestConnectionLostSubsystem(protocol.Protocol):
    """
    A SSH subsystem that disconnects at first received data. It also records
    the number of times C{connectionLost} is called with the
    C{connectionLostCount} of the session transport.
    """

    def __init__(self, *args, **kw):
        """
        Ignore arguments.
        """


    def connectionLost(self, reason):
        """
        Record call on the C{connectionLostCount} attribute on the session
        transport.
        """
        self.transport.session.conn.transport.connectionLostCount += 1


    def dataReceived(self, data):
        """
        Disconnect the tranport once some data is received.
        """
        self.transport.loseConnection()



class FalseTransport:

    def __init__(self, p):
        p.makeConnection(self)
        p.processEnded(failure.Failure(ProcessTerminated(255, None, None)))


    def loseConnection(self):
        pass



class EchoTransport:

    def __init__(self, p):
        self.proto = p
        p.makeConnection(self)
        self.closed = 0


    def write(self, data):
        log.msg(repr(data))
        self.proto.outReceived(data)
        self.proto.outReceived('\r\n')
        if '\x00' in data: # mimic 'exit' for the shell test
            self.loseConnection()


    def loseConnection(self):
        if self.closed: return
        self.closed = 1
        self.proto.inConnectionLost()
        self.proto.outConnectionLost()
        self.proto.errConnectionLost()
        self.proto.processEnded(failure.Failure(ProcessTerminated(0, None, None)))



class ErrEchoTransport:

    def __init__(self, p):
        self.proto = p
        p.makeConnection(self)
        self.closed = 0


    def write(self, data):
        self.proto.errReceived(data)
        self.proto.errReceived('\r\n')


    def loseConnection(self):
        if self.closed: return
        self.closed = 1
        self.proto.inConnectionLost()
        self.proto.outConnectionLost()
        self.proto.errConnectionLost()
        self.proto.processEnded(failure.Failure(ProcessTerminated(0, None, None)))



class SuperEchoTransport:

    def __init__(self, p):
        self.proto = p
        p.makeConnection(self)
        self.closed = 0


    def write(self, data):
        self.proto.outReceived(data)
        self.proto.outReceived('\r\n')
        self.proto.errReceived(data)
        self.proto.errReceived('\r\n')


    def loseConnection(self):
        if self.closed: return
        self.closed = 1
        self.proto.inConnectionLost()
        self.proto.outConnectionLost()
        self.proto.errConnectionLost()
        self.proto.processEnded(failure.Failure(ProcessTerminated(0, None, None)))


if Crypto is not None and pyasn1 is not None:
    from twisted.conch import checkers
    from twisted.conch.ssh import channel, connection, factory, keys
    from twisted.conch.ssh import transport, userauth



    class UtilityTestCase(unittest.TestCase):

        def testCounter(self):
            c = transport._Counter('\x00\x00', 2)
            for i in xrange(256 * 256):
                self.assertEquals(c(), struct.pack('!H', (i + 1) % (2 ** 16)))
            # It should wrap around, too.
            for i in xrange(256 * 256):
                self.assertEquals(c(), struct.pack('!H', (i + 1) % (2 ** 16)))



    class ConchTestPublicKeyChecker(checkers.SSHPublicKeyDatabase):

        def checkKey(self, credentials):
            unittest.assertEquals(credentials.username, 'testuser', 'bad username')
            unittest.assertEquals(credentials.blob,
                                  keys.Key.fromString(publicDSA_openssh).blob())
            return 1



    class ConchTestPasswordChecker:
        credentialInterfaces = checkers.IUsernamePassword,

        def requestAvatarId(self, credentials):
            unittest.assertEquals(credentials.username, 'testuser', 'bad username')
            unittest.assertEquals(credentials.password, 'testpass', 'bad password')
            return defer.succeed(credentials.username)



    class ConchTestSSHChecker(checkers.SSHProtocolChecker):

        def areDone(self, avatarId):
            unittest.assertEquals(avatarId, 'testuser')
            if len(self.successfulCredentials[avatarId]) < 2:
                return 0
            else:
                return 1



    class ConchTestServerFactory(factory.SSHFactory):
        noisy = 0

        services = {
            'ssh-userauth':userauth.SSHUserAuthServer,
            'ssh-connection':connection.SSHConnection
        }

        def buildProtocol(self, addr):
            proto = ConchTestServer()
            proto.supportedPublicKeys = self.privateKeys.keys()
            proto.factory = self

            if hasattr(self, 'expectedLoseConnection'):
                proto.expectedLoseConnection = self.expectedLoseConnection

            self.proto = proto
            return proto


        def getPublicKeys(self):
            return {
                'ssh-rsa': keys.Key.fromString(publicRSA_openssh),
                'ssh-dss': keys.Key.fromString(publicDSA_openssh)
            }


        def getPrivateKeys(self):
            return {
                'ssh-rsa': keys.Key.fromString(privateRSA_openssh),
                'ssh-dss': keys.Key.fromString(privateDSA_openssh)
            }


        def getPrimes(self):
            return {
                2048: [(transport.DH_GENERATOR, transport.DH_PRIME)]
            }


        def getService(self, trans, name):
            return factory.SSHFactory.getService(self, trans, name)



    class ConchTestBase:

        done = 0

        def connectionLost(self, reason):
            if self.done:
                return
            if not hasattr(self, 'expectedLoseConnection'):
                unittest.fail('unexpectedly lost connection %s\n%s' % (self, reason))
            self.done = 1


        def receiveError(self, reasonCode, desc):
            self.expectedLoseConnection = 1
            if reasonCode != transport.DISCONNECT_CONNECTION_LOST:
                raise RuntimeError(
                    "Unexpected disconnection: reason %s, desc %s" % (
                   (reasonCode, desc)))
            self.loseConnection()


        def receiveUnimplemented(self, seqID):
            unittest.fail('got unimplemented: seqid %s'  % seqID)
            self.expectedLoseConnection = 1
            self.loseConnection()



    class ConchTestServer(ConchTestBase, transport.SSHServerTransport):
        connectionLostCount = 0

        def connectionLost(self, reason):
            ConchTestBase.connectionLost(self, reason)
            transport.SSHServerTransport.connectionLost(self, reason)



    class ConchTestClient(ConchTestBase, transport.SSHClientTransport):

        def __init__(self, auth):
            """
            @type auth: C{SSHUserAuthClient}
            @param auth: an instance of SSHUserAuthClient used for a user
                authentication.
            """
            self.auth = auth


        def connectionLost(self, reason):
            ConchTestBase.connectionLost(self, reason)
            transport.SSHClientTransport.connectionLost(self, reason)


        def verifyHostKey(self, key, fp):
            unittest.assertEquals(key,
                    keys.Key.fromString(publicRSA_openssh).blob())
            unittest.assertEquals(fp,
                '3d:13:5f:cb:c9:79:8a:93:06:27:65:bc:3d:0b:8f:af')
            return defer.succeed(1)


        def connectionSecure(self):
            self.requestService(self.auth)



    class ConchTestClientAuth(userauth.SSHUserAuthClient):

        hasTriedNone = 0 # have we tried the 'none' auth yet?
        canSucceedPublicKey = 0 # can we succed with this yet?
        canSucceedPassword = 0

        def ssh_USERAUTH_SUCCESS(self, packet):
            if not self.canSucceedPassword and self.canSucceedPublicKey:
                unittest.fail('got USERAUTH_SUCESS before password and publickey')
            userauth.SSHUserAuthClient.ssh_USERAUTH_SUCCESS(self, packet)


        def getPassword(self):
            self.canSucceedPassword = 1
            return defer.succeed('testpass')


        def getPrivateKey(self):
            self.canSucceedPublicKey = 1
            return defer.succeed(keys.Key.fromString(privateDSA_openssh).keyObject)


        def getPublicKey(self):
            return keys.Key.fromString(publicDSA_openssh).blob()


    class ConchTestClientBaseConnection(connection.SSHConnection):
        """
        Base class for opening channels.
        """
        name = 'ssh-connection'

        def __init__(self, testChannels=[]):
            """
            @type testChannels: C{list}
            @param testChannels: list of double tuples: C{SSHChannel} class and
                dictionary where keys and values are later used as named
                instantiation arguments for this class. By default the C{conn}
                argument passed to create the C{SSHChannel} instances is set to
                C{self}.
            """
            connection.SSHConnection.__init__(self)
            self.testChannels = testChannels


        def serviceStarted(self):
            """
            Create and open every C{SSHChannel} passed at init.
            """
            for ch in self.testChannels:
                chan, kwargs = ch
                kwargs['conn'] = self
                self.openChannel(chan(**kwargs))



    class ConchTestClientConnection(ConchTestClientBaseConnection):

        results = 0
        totalResults = 8

        def serviceStarted(self):
            self.testChannels = [
                (SSHTestFailExecChannel, {}),
                (SSHTestFalseChannel, {}),
                (SSHTestEchoChannel, {'localWindow': 4, 'localMaxPacket': 5}),
                (SSHTestErrChannel, {'localWindow': 4, 'localMaxPacket': 5}),
                (SSHTestMaxPacketChannel,
                    {'localWindow': 12, 'localMaxPacket': 1}),
                (SSHTestShellChannel, {}),
                (SSHTestSubsystemChannel, {}),
                (SSHUnknownChannel, {})
            ]
            ConchTestClientBaseConnection.serviceStarted(self)


        def addResult(self):
            self.results += 1
            log.msg('got %s of %s results' % (self.results, self.totalResults))
            if self.results == self.totalResults:
                self.transport.expectedLoseConnection = 1
                self.serviceStopped()
                self.transport.loseConnection()



    class SSHUnknownChannel(channel.SSHChannel):

        name = 'crazy-unknown-channel'

        def openFailed(self, reason):
            """
            good .... good
            """
            log.msg('unknown open failed')
            self.conn.addResult()


        def channelOpen(self, ignored):
            unittest.fail("opened unknown channel")



    class SSHTestFailExecChannel(channel.SSHChannel):

        name = 'session'

        def openFailed(self, reason):
            unittest.fail('fail exec open failed: %s' % reason)


        def channelOpen(self, ignore):
            d = self.conn.sendRequest(self, 'exec', common.NS('jumboliah'), 1)
            d.addCallback(self._cbRequestWorked)
            d.addErrback(self._ebRequestWorked)
            log.msg('opened fail exec')


        def _cbRequestWorked(self, ignored):
            unittest.fail('fail exec succeeded')


        def _ebRequestWorked(self, ignored):
            log.msg('fail exec finished')
            self.conn.addResult()
            self.loseConnection()



    class SSHTestFalseChannel(channel.SSHChannel):

        name = 'session'

        def openFailed(self, reason):
            unittest.fail('false open failed: %s' % reason)


        def channelOpen(self, ignored):
            d = self.conn.sendRequest(self, 'exec', common.NS('false'), 1)
            d.addCallback(self._cbRequestWorked)
            d.addErrback(self._ebRequestFailed)
            log.msg('opened false')


        def _cbRequestWorked(self, ignored):
            pass


        def _ebRequestFailed(self, reason):
            unittest.fail('false exec failed: %s' % reason)


        def dataReceived(self, data):
            unittest.fail('got data when using false')


        def request_exit_status(self, status):
            status, = struct.unpack('>L', status)
            if status == 0:
                unittest.fail('false exit status was 0')
            log.msg('finished false')
            self.conn.addResult()
            return 1



    class SSHTestEchoChannel(channel.SSHChannel):

        name = 'session'
        testBuf = ''
        eofCalled = 0

        def openFailed(self, reason):
            unittest.fail('echo open failed: %s' % reason)


        def channelOpen(self, ignore):
            d = self.conn.sendRequest(self, 'exec', common.NS('echo hello'), 1)
            d.addErrback(self._ebRequestFailed)
            log.msg('opened echo')


        def _ebRequestFailed(self, reason):
            unittest.fail('echo exec failed: %s' % reason)


        def dataReceived(self, data):
            self.testBuf += data


        def errReceived(self, dataType, data):
            unittest.fail('echo channel got extended data')


        def request_exit_status(self, status):
            self.status ,= struct.unpack('>L', status)


        def eofReceived(self):
            log.msg('eof received')
            self.eofCalled = 1


        def closed(self):
            if self.status != 0:
                unittest.fail('echo exit status was not 0: %i' % self.status)
            if self.testBuf != "hello\r\n":
                unittest.fail('echo did not return hello: %s' % repr(self.testBuf))
            unittest.assertEquals(self.localWindowLeft, 4)
            unittest.assert_(self.eofCalled)
            log.msg('finished echo')
            self.conn.addResult()
            return 1



    class SSHTestErrChannel(channel.SSHChannel):

        name = 'session'
        testBuf = ''
        eofCalled = 0

        def openFailed(self, reason):
            unittest.fail('err open failed: %s' % reason)


        def channelOpen(self, ignore):
            d = self.conn.sendRequest(self, 'exec', common.NS('eecho hello'), 1)
            d.addErrback(self._ebRequestFailed)
            log.msg('opened err')


        def _ebRequestFailed(self, reason):
            unittest.fail('err exec failed: %s' % reason)


        def dataReceived(self, data):
            unittest.fail('err channel got regular data: %s' % repr(data))


        def extReceived(self, dataType, data):
            unittest.assertEquals(dataType, connection.EXTENDED_DATA_STDERR)
            self.testBuf += data


        def request_exit_status(self, status):
            self.status ,= struct.unpack('>L', status)


        def eofReceived(self):
            log.msg('eof received')
            self.eofCalled = 1


        def closed(self):
            if self.status != 0:
                unittest.fail('err exit status was not 0: %i' % self.status)
            if self.testBuf != "hello\r\n":
                unittest.fail('err did not return hello: %s' % repr(self.testBuf))
            unittest.assertEquals(self.localWindowLeft, 4)
            unittest.assert_(self.eofCalled)
            log.msg('finished err')
            self.conn.addResult()
            return 1



    class SSHTestMaxPacketChannel(channel.SSHChannel):

        name = 'session'
        testBuf = ''
        testExtBuf = ''
        eofCalled = 0

        def openFailed(self, reason):
            unittest.fail('max packet open failed: %s' % reason)


        def channelOpen(self, ignore):
            d = self.conn.sendRequest(self, 'exec', common.NS('secho hello'), 1)
            d.addErrback(self._ebRequestFailed)
            log.msg('opened max packet')


        def _ebRequestFailed(self, reason):
            unittest.fail('max packet exec failed: %s' % reason)


        def dataReceived(self, data):
            self.testBuf += data


        def extReceived(self, dataType, data):
            unittest.assertEquals(dataType, connection.EXTENDED_DATA_STDERR)
            self.testExtBuf += data


        def request_exit_status(self, status):
            self.status ,= struct.unpack('>L', status)


        def eofReceived(self):
            log.msg('eof received')
            self.eofCalled = 1


        def closed(self):
            if self.status != 0:
                unittest.fail('echo exit status was not 0: %i' % self.status)
            unittest.assertEquals(self.testBuf, 'hello\r\n')
            unittest.assertEquals(self.testExtBuf, 'hello\r\n')
            unittest.assertEquals(self.localWindowLeft, 12)
            unittest.assert_(self.eofCalled)
            log.msg('finished max packet')
            self.conn.addResult()
            return 1



    class SSHTestShellChannel(channel.SSHChannel):

        name = 'session'
        testBuf = ''
        eofCalled = 0
        closeCalled = 0

        def openFailed(self, reason):
            unittest.fail('shell open failed: %s' % reason)


        def channelOpen(self, ignored):
            data = session.packRequest_pty_req('conch-test-term', (24, 80, 0, 0), '')
            d = self.conn.sendRequest(self, 'pty-req', data, 1)
            d.addCallback(self._cbPtyReq)
            d.addErrback(self._ebPtyReq)
            log.msg('opened shell')


        def _cbPtyReq(self, ignored):
            d = self.conn.sendRequest(self, 'shell', '', 1)
            d.addCallback(self._cbShellOpen)
            d.addErrback(self._ebShellOpen)


        def _ebPtyReq(self, reason):
            unittest.fail('pty request failed: %s' % reason)


        def _cbShellOpen(self, ignored):
            self.write('testing the shell!\x00')
            self.conn.sendEOF(self)


        def _ebShellOpen(self, reason):
            unittest.fail('shell request failed: %s' % reason)


        def dataReceived(self, data):
            self.testBuf += data


        def request_exit_status(self, status):
            self.status ,= struct.unpack('>L', status)


        def eofReceived(self):
            self.eofCalled = 1


        def closed(self):
            log.msg('calling shell closed')
            if self.status != 0:
                log.msg('shell exit status was not 0: %i' % self.status)
            unittest.assertEquals(self.testBuf, 'testing the shell!\x00\r\n')
            unittest.assert_(self.eofCalled)
            log.msg('finished shell')
            self.conn.addResult()



    class SSHTestSubsystemChannel(channel.SSHChannel):

        name = 'session'

        def openFailed(self, reason):
            unittest.fail('subsystem open failed: %s' % reason)


        def channelOpen(self, ignore):
            d = self.conn.sendRequest(self, 'subsystem', common.NS('not-crazy'), 1)
            d.addCallback(self._cbRequestWorked)
            d.addErrback(self._ebRequestFailed)


        def _cbRequestWorked(self, ignored):
            unittest.fail('opened non-crazy subsystem')


        def _ebRequestFailed(self, ignored):
            d = self.conn.sendRequest(self, 'subsystem', common.NS('crazy'), 1)
            d.addCallback(self._cbRealRequestWorked)
            d.addErrback(self._ebRealRequestFailed)


        def _cbRealRequestWorked(self, ignored):
            d1 = self.conn.sendGlobalRequest('foo', 'bar', 1)
            d1.addErrback(self._ebFirstGlobal)

            d2 = self.conn.sendGlobalRequest('foo-2', 'bar2', 1)
            d2.addCallback(lambda x: unittest.assertEquals(x, 'data'))
            d2.addErrback(self._ebSecondGlobal)

            d3 = self.conn.sendGlobalRequest('bar', 'foo', 1)
            d3.addCallback(self._cbThirdGlobal)
            d3.addErrback(lambda x,s=self: log.msg('subsystem finished') or s.conn.addResult() or s.loseConnection())


        def _ebRealRequestFailed(self, reason):
            unittest.fail('opening crazy subsystem failed: %s' % reason)


        def _ebFirstGlobal(self, reason):
            unittest.fail('first global request failed: %s' % reason)


        def _ebSecondGlobal(self, reason):
            unittest.fail('second global request failed: %s' % reason)


        def _cbThirdGlobal(self, ignored):
            unittest.fail('second global request succeeded')



    class SSHTestSubsystemConnectionLostChannel(channel.SSHChannel):
        """
        Open test_connectionLost subsystem and send something to the server.
        """
        name = 'session'

        def channelOpen(self, data):
            """
            Open the test_connectionLost subsystem.
            """
            d = self.conn.sendRequest(self, 'subsystem',
                common.NS('test_connectionLost'), wantReply=True)
            d.addCallback(self._cbRequestWorked)


        def _cbRequestWorked(self, ignored):
            """
            Write some data to trigger the disconnection on the server.
            """
            self.write('Hello server')


        def closeReceived(self):
            channel.SSHChannel.closeReceived(self)
            self.conn.transport.loseConnection()


    class SSHExecChannel(channel.SSHChannel):
        """
        Execute a comand on a server.
        """
        name = 'session'

        def channelOpen(self, data):
            self.conn.sendRequest(self, 'exec',
                common.NS('some_command'), wantReply=False)


        def closeReceived(self):
            channel.SSHChannel.closeReceived(self)
            self.conn.transport.loseConnection()



class SSHProtocolTestCase(unittest.TestCase):

    if not Crypto:
        skip = "can't run w/o PyCrypto"

    if not pyasn1:
        skip = "can't run w/o PyASN1"


    def _setUp(self, avatar=None, clientConnection=None):
        """
        Create Conch client and server protocols and loopback transports for
        them.Should be run at the beggining of each test.

        @paran: avatar: an instance of C{avatar.ConchUser}.
        """
        if clientConnection is None:
            clientConnection = ConchTestClientConnection()
        realm = ConchTestRealm(avatar)
        p = portal.Portal(realm)
        sshpc = ConchTestSSHChecker()
        sshpc.registerChecker(ConchTestPasswordChecker())
        sshpc.registerChecker(ConchTestPublicKeyChecker())
        p.registerChecker(sshpc)
        fac = ConchTestServerFactory()
        fac.portal = p
        fac.startFactory()
        self.server = fac.buildProtocol(None)
        auth = ConchTestClientAuth('testuser', clientConnection)
        self.client = ConchTestClient(auth)


    def test_ourServerOurClient(self):
        """
        Test the Conch server against the Conch client.
        """
        self._setUp()
        def check(ignore):
            errors = self.flushLoggedErrors(error.ConchError)
            self.assertEquals(len(errors), 2)

            unknowChannelError = errors[0].value
            self.assertEquals(unknowChannelError.value, "unknown channel")
            self.assertEquals(unknowChannelError.data,
                connection.OPEN_UNKNOWN_CHANNEL_TYPE)

            badExecError = errors[1].value
            self.assertEquals(badExecError.value, "bad exec")
            self.assertIdentical(badExecError.data, None)
        return loopbackAsync(self.server, self.client).addCallback(check)


    def test_subsystemConnectionLost(self):
        """
        Test if subsystem's connectionLost is executed only once.
        """
        clientConnection = ConchTestClientBaseConnection(
            [(SSHTestSubsystemConnectionLostChannel, {})])
        self._setUp(clientConnection=clientConnection)

        def check(ignore):
            self.assertEquals(self.server.connectionLostCount, 1,
                "subsystem's connectionLost method executed more than once or "
                "not executed at all.")
        return loopbackAsync(self.server, self.client).addCallback(check)


    def test_sessionLoseConnection(self):
        """
        Test closing a client's session by a server.
        """
        clientConnection = ConchTestClientBaseConnection(
            [(SSHExecChannel, {})])
        self._setUp(avatar=ConchTestBaseAvatar(),
                    clientConnection=clientConnection)
        return loopbackAsync(self.server, self.client)



class TestSSHFactory(unittest.TestCase):

    if not Crypto:
        skip = "can't run w/o PyCrypto"

    if not pyasn1:
        skip = "can't run w/o PyASN1"

    def makeSSHFactory(self, primes=None):
        sshFactory = factory.SSHFactory()
        gpk = lambda: {'ssh-rsa' : keys.Key(None)}
        sshFactory.getPrimes = lambda: primes
        sshFactory.getPublicKeys = sshFactory.getPrivateKeys = gpk
        sshFactory.startFactory()
        return sshFactory


    def test_buildProtocol(self):
        """
        By default, buildProtocol() constructs an instance of
        SSHServerTransport.
        """
        factory = self.makeSSHFactory()
        protocol = factory.buildProtocol(None)
        self.assertIsInstance(protocol, transport.SSHServerTransport)


    def test_buildProtocolRespectsProtocol(self):
        """
        buildProtocol() calls 'self.protocol()' to construct a protocol
        instance.
        """
        calls = []
        def makeProtocol(*args):
            calls.append(args)
            return transport.SSHServerTransport()
        factory = self.makeSSHFactory()
        factory.protocol = makeProtocol
        factory.buildProtocol(None)
        self.assertEquals([()], calls)


    def test_multipleFactories(self):
        f1 = self.makeSSHFactory(primes=None)
        f2 = self.makeSSHFactory(primes={1:(2,3)})
        p1 = f1.buildProtocol(None)
        p2 = f2.buildProtocol(None)
        self.failIf('diffie-hellman-group-exchange-sha1' in p1.supportedKeyExchanges,
                p1.supportedKeyExchanges)
        self.failUnless('diffie-hellman-group-exchange-sha1' in p2.supportedKeyExchanges,
                p2.supportedKeyExchanges)



class EntropyTestCase(unittest.TestCase):
    """
    Tests for L{common.entropy}.
    """

    def test_deprecation(self):
        """
        Test the deprecation of L{common.entropy.get_bytes}.
        """
        def wrapper():
            return common.entropy.get_bytes(10)
        self.assertWarns(DeprecationWarning,
            "entropy.get_bytes is deprecated, please use "
            "twisted.python.randbytes.secureRandom instead.",
            __file__, wrapper)



class MPTestCase(unittest.TestCase):
    """
    Tests for L{common.getMP}.

    @cvar getMP: a method providing a MP parser.
    @type getMP: C{callable}
    """
    getMP = staticmethod(common.getMP)

    if not Crypto:
        skip = "can't run w/o PyCrypto"

    if not pyasn1:
        skip = "can't run w/o PyASN1"


    def test_getMP(self):
        """
        L{common.getMP} should parse the a multiple precision integer from a
        string: a 4-byte length followed by length bytes of the integer.
        """
        self.assertEquals(
            self.getMP('\x00\x00\x00\x04\x00\x00\x00\x01'),
            (1, ''))


    def test_getMPBigInteger(self):
        """
        L{common.getMP} should be able to parse a big enough integer
        (that doesn't fit on one byte).
        """
        self.assertEquals(
            self.getMP('\x00\x00\x00\x04\x01\x02\x03\x04'),
            (16909060, ''))


    def test_multipleGetMP(self):
        """
        L{common.getMP} has the ability to parse multiple integer in the same
        string.
        """
        self.assertEquals(
            self.getMP('\x00\x00\x00\x04\x00\x00\x00\x01'
                       '\x00\x00\x00\x04\x00\x00\x00\x02', 2),
            (1, 2, ''))


    def test_getMPRemainingData(self):
        """
        When more data than needed is sent to L{common.getMP}, it should return
        the remaining data.
        """
        self.assertEquals(
            self.getMP('\x00\x00\x00\x04\x00\x00\x00\x01foo'),
            (1, 'foo'))


    def test_notEnoughData(self):
        """
        When the string passed to L{common.getMP} doesn't even make 5 bytes,
        it should raise a L{struct.error}.
        """
        self.assertRaises(struct.error, self.getMP, '\x02\x00')



class PyMPTestCase(MPTestCase):
    """
    Tests for the python implementation of L{common.getMP}.
    """
    getMP = staticmethod(common.getMP_py)



class GMPYMPTestCase(MPTestCase):
    """
    Tests for the gmpy implementation of L{common.getMP}.
    """
    getMP = staticmethod(common._fastgetMP)



try:
    import gmpy
except ImportError:
    GMPYMPTestCase.skip = "gmpy not available"
