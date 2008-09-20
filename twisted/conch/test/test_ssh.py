# -*- test-case-name: twisted.conch.test.test_ssh -*-
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

import struct

try:
    import Crypto.Cipher.DES3
except ImportError:
    Crypto = None

from twisted.conch.ssh import common, session, forwarding
from twisted.conch import avatar, error
from twisted.conch.test.keydata import publicRSA_openssh, privateRSA_openssh
from twisted.conch.test.keydata import publicDSA_openssh, privateDSA_openssh
from twisted.cred import portal
from twisted.internet import defer, protocol, reactor
from twisted.internet.error import ProcessTerminated
from twisted.python import failure, log
from twisted.trial import unittest

from test_recvline import LoopbackRelay



class ConchTestRealm:

    def requestAvatar(self, avatarID, mind, *interfaces):
        unittest.assertEquals(avatarID, 'testuser')
        a = ConchTestAvatar()
        return interfaces[0], a, a.logout

class ConchTestAvatar(avatar.ConchUser):
    loggedOut = False

    def __init__(self):
        avatar.ConchUser.__init__(self)
        self.listeners = {}
        self.channelLookup.update({'session': session.SSHSession,
                        'direct-tcpip':forwarding.openConnectForwardingClient})
        self.subsystemLookup.update({'crazy': CrazySubsystem})

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
        loggedOut = True
        for listener in self.listeners.values():
            log.msg('stopListening %s' % listener)
            listener.stopListening()

class ConchSessionForTestAvatar:

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

#    def closeReceived(self):
#        #if self.proto:
#        #   self.proto.transport.loseConnection()
#        self.loseConnection()

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

from twisted.python import components
components.registerAdapter(ConchSessionForTestAvatar, ConchTestAvatar, session.ISession)

class CrazySubsystem(protocol.Protocol):

    def __init__(self, *args, **kw):
        pass

    def connectionMade(self):
        """
        good ... good
        """

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


if Crypto: # stuff that needs PyCrypto to even import
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
            unittest.assertEquals(credentials.blob, keys.getPublicKeyString(data=publicDSA_openssh))
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
                'ssh-rsa':keys.getPublicKeyString(data=publicRSA_openssh),
                'ssh-dss':keys.getPublicKeyString(data=publicDSA_openssh)
            }

        def getPrivateKeys(self):
            return {
                'ssh-rsa':keys.getPrivateKeyObject(data=privateRSA_openssh),
                'ssh-dss':keys.getPrivateKeyObject(data=privateDSA_openssh)
            }

        def getPrimes(self):
            return {
                2048:[(transport.DH_GENERATOR, transport.DH_PRIME)]
            }

        def getService(self, trans, name):
            return factory.SSHFactory.getService(self, trans, name)

    class ConchTestBase:

        done = 0
        allowedToError = 0

        def connectionLost(self, reason):
            if self.done:
                return
            if not hasattr(self,'expectedLoseConnection'):
                unittest.fail('unexpectedly lost connection %s\n%s' % (self, reason))
            self.done = 1

        def receiveError(self, reasonCode, desc):
            self.expectedLoseConnection = 1
            if not self.allowedToError:
                unittest.fail('got disconnect for %s: reason %s, desc: %s' %
                               (self, reasonCode, desc))
            self.loseConnection()

        def receiveUnimplemented(self, seqID):
            unittest.fail('got unimplemented: seqid %s'  % seqID)
            self.expectedLoseConnection = 1
            self.loseConnection()

    class ConchTestServer(ConchTestBase, transport.SSHServerTransport):

        def connectionLost(self, reason):
            ConchTestBase.connectionLost(self, reason)
            transport.SSHServerTransport.connectionLost(self, reason)

    class ConchTestClient(ConchTestBase, transport.SSHClientTransport):

        def connectionLost(self, reason):
            ConchTestBase.connectionLost(self, reason)
            transport.SSHClientTransport.connectionLost(self, reason)

        def verifyHostKey(self, key, fp):
            unittest.assertEquals(key, keys.getPublicKeyString(data = publicRSA_openssh))
            unittest.assertEquals(fp,'3d:13:5f:cb:c9:79:8a:93:06:27:65:bc:3d:0b:8f:af')
            return defer.succeed(1)

        def connectionSecure(self):
            self.requestService(ConchTestClientAuth('testuser',
                ConchTestClientConnection()))

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
            return defer.succeed(keys.getPrivateKeyObject(data=privateDSA_openssh))

        def getPublicKey(self):
            return keys.getPublicKeyString(data=publicDSA_openssh)

    class ConchTestClientConnection(connection.SSHConnection):

        name = 'ssh-connection'
        results = 0
        totalResults = 8

        def serviceStarted(self):
            self.openChannel(SSHTestFailExecChannel(conn = self))
            self.openChannel(SSHTestFalseChannel(conn = self))
            self.openChannel(SSHTestEchoChannel(localWindow=4, localMaxPacket=5, conn = self))
            self.openChannel(SSHTestErrChannel(localWindow=4, localMaxPacket=5, conn = self))
            self.openChannel(SSHTestMaxPacketChannel(localWindow=12, localMaxPacket=1, conn = self))
            self.openChannel(SSHTestShellChannel(conn = self))
            self.openChannel(SSHTestSubsystemChannel(conn = self))
            self.openChannel(SSHUnknownChannel(conn = self))

        def addResult(self):
            self.results += 1
            log.msg('got %s of %s results' % (self.results, self.totalResults))
            if self.results == self.totalResults:
                self.transport.expectedLoseConnection = 1
                self.serviceStopped()

    class SSHUnknownChannel(channel.SSHChannel):

        name = 'crazy-unknown-channel'

        def openFailed(self, reason):
            """
            good .... good
            """
            log.msg('unknown open failed')
            log.flushErrors()
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
            log.flushErrors()
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



class SSHProtocolTestCase(unittest.TestCase):

    if not Crypto:
        skip = "can't run w/o PyCrypto"

    def testOurServerOurClient(self):
        """test the Conch server against the Conch client
        """
        realm = ConchTestRealm()
        p = portal.Portal(realm)
        sshpc = ConchTestSSHChecker()
        sshpc.registerChecker(ConchTestPasswordChecker())
        sshpc.registerChecker(ConchTestPublicKeyChecker())
        p.registerChecker(sshpc)
        fac = ConchTestServerFactory()
        fac.portal = p
        fac.startFactory()
        self.server = fac.buildProtocol(None)
        self.clientTransport = LoopbackRelay(self.server)
        self.client = ConchTestClient()
        self.serverTransport = LoopbackRelay(self.client)

        self.server.makeConnection(self.serverTransport)
        self.client.makeConnection(self.clientTransport)

        while self.serverTransport.buffer or self.clientTransport.buffer:
            log.callWithContext({'system': 'serverTransport'},
                                self.serverTransport.clearBuffer)
            log.callWithContext({'system': 'clientTransport'},
                                self.clientTransport.clearBuffer)
        self.failIf(self.server.done and self.client.done)


class TestSSHFactory(unittest.TestCase):

    if not Crypto:
        skip = "can't run w/o PyCrypto"

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
        protocol = factory.buildProtocol(None)
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
