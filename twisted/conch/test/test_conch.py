# -*- test-case-name: twisted.conch.test.test_conch -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

import os, sys

try:
    import Crypto
except:
    Crypto = None

from twisted.cred import portal
from twisted.internet import reactor, defer, protocol, error
from twisted.python import log, runtime
from twisted.trial import unittest

from twisted.test.test_process import SignalMixin
from twisted.conch.test.test_ssh import ConchTestRealm

from twisted.conch.test.test_keys import publicRSA_openssh, privateRSA_openssh
from twisted.conch.test.test_keys import publicDSA_openssh, privateDSA_openssh



class Echo(protocol.Protocol):
    def connectionMade(self):
        log.msg('ECHO CONNECTION MADE')


    def connectionLost(self, reason):
        log.msg('ECHO CONNECTION DONE')


    def dataReceived(self, data):
        self.transport.write(data)
        if '\n' in data:
            self.transport.loseConnection()



class EchoFactory(protocol.Factory):
    protocol = Echo



class ConchTestOpenSSHProcess(protocol.ProcessProtocol):
    buf = ''


    def _getDeferred(self):
        d, self.deferred = self.deferred, None
        return d


    def outReceived(self, data):
        self.buf += data


    def processEnded(self, reason):
        if reason.value.exitCode != 0:
            self._getDeferred().errback(
                self.failureException("exit code was not 0: %s"
                                      % reason.value.exitCode))
        else:
            buf = self.buf.replace('\r\n', '\n')
            self._getDeferred().callback(buf)



class ConchTestForwardingProcess(protocol.ProcessProtocol):
    """
    Manages a third-party process which launches a server.

    Uses L{ConchTestForwardingPort} to connect to the third-party server.
    Once L{ConchTestForwardingPort} has disconnected, kill the process and fire
    a Deferred with the data received by the L{ConchTestForwardingPort}.
    """

    def __init__(self, port, data):
        """
        @type port: C{int}
        @param port: The port on which the third-party server is listening.
        (it is assumed that the server is running on localhost).

        @type data: C{str}
        @param data: This is sent to the third-party server. Must end with '\n'
        in order to trigger a disconnect.
        """
        self.port = port
        self.buffer = None
        self.data = data


    def _getDeferred(self):
        d, self.deferred = self.deferred, None
        return d


    def connectionMade(self):
        self._connect()


    def _connect(self):
        """
        Connect to the server, which is often a third-party process.
        Tries to reconnect if it fails because we have no way of determining
        exactly when the port becomes available for listening -- we can only
        know when the process starts.
        """
        cc = protocol.ClientCreator(reactor, ConchTestForwardingPort, self,
                                    self.data)
        d = cc.connectTCP('127.0.0.1', self.port)
        d.addErrback(self._ebConnect)
        return d


    def _ebConnect(self, f):
        reactor.callLater(1, self._connect)


    def forwardingPortDisconnected(self, buffer):
        self.buffer = buffer
        self.transport.write('\x03')
        self.transport.loseConnection()
        reactor.callLater(0, self._reallyDie)


    def _reallyDie(self):
        try:
            self.transport.signalProcess('KILL')
        except error.ProcessExitedAlready:
            pass


    def processEnded(self, reason):
        self._getDeferred().callback(self.buffer)



class ConchTestForwardingPort(protocol.Protocol):
    """
    Connects to server launched by a third-party process (managed by
    L{ConchTestForwardingProcess}) sends data, then reports whatever it
    received back to the L{ConchTestForwardingProcess} once the connection
    is ended.
    """


    def __init__(self, protocol, data):
        """
        @type protocol: L{ConchTestForwardingProcess}
        @param protocol: The L{ProcessProtocol} which made this connection.

        @type data: str
        @param data: The data to be sent to the third-party server.
        """
        self.protocol = protocol
        self.data = data


    def connectionMade(self):
        self.buffer = ''
        self.transport.write(self.data)


    def dataReceived(self, data):
        self.buffer += data


    def connectionLost(self, reason):
        self.protocol.forwardingPortDisconnected(self.buffer)



if Crypto:
    from twisted.conch.client import options, default, connect
    from twisted.conch.error import ConchError
    from twisted.conch.ssh import forwarding
    from twisted.conch.ssh import connection

    from twisted.conch.test.test_ssh import ConchTestServerFactory
    from twisted.conch.test.test_ssh import ConchTestPublicKeyChecker


    class SSHTestConnectionForUnix(connection.SSHConnection):

        def __init__(self, p, exe=None, cmds=None):
            connection.SSHConnection.__init__(self)
            if p:
                self.spawn = (p, exe, cmds)
            else:
                self.spawn = None
            self.connected = 0
            self.remoteForwards = {}


        def serviceStarted(self):
            if self.spawn:
                env = os.environ.copy()
                env['PYTHONPATH'] = os.pathsep.join(sys.path)
                reactor.callLater(0,reactor.spawnProcess, env=env, *self.spawn)
            self.connected = 1

        def requestRemoteForwarding(self, remotePort, hostport):
            data = forwarding.packGlobal_tcpip_forward(('0.0.0.0', remotePort))
            d = self.sendGlobalRequest('tcpip-forward', data,
                                       wantReply=1)
            log.msg('requesting remote forwarding %s:%s' %(remotePort, hostport))
            d.addCallback(self._cbRemoteForwarding, remotePort, hostport)
            d.addErrback(self._ebRemoteForwarding, remotePort, hostport)

        def _cbRemoteForwarding(self, result, remotePort, hostport):
            log.msg('accepted remote forwarding %s:%s' % (remotePort, hostport))
            self.remoteForwards[remotePort] = hostport
            log.msg(repr(self.remoteForwards))

        def _ebRemoteForwarding(self, f, remotePort, hostport):
            log.msg('remote forwarding %s:%s failed' % (remotePort, hostport))
            log.msg(f)

        def cancelRemoteForwarding(self, remotePort):
            data = forwarding.packGlobal_tcpip_forward(('0.0.0.0', remotePort))
            self.sendGlobalRequest('cancel-tcpip-forward', data)
            log.msg('cancelling remote forwarding %s' % remotePort)
            try:
                del self.remoteForwards[remotePort]
            except:
                pass
            log.msg(repr(self.remoteForwards))

        def channel_forwarded_tcpip(self, windowSize, maxPacket, data):
            log.msg('%s %s' % ('FTCP', repr(data)))
            remoteHP, origHP = forwarding.unpackOpen_forwarded_tcpip(data)
            log.msg(self.remoteForwards)
            log.msg(remoteHP)
            if self.remoteForwards.has_key(remoteHP[1]):
                connectHP = self.remoteForwards[remoteHP[1]]
                log.msg('connect forwarding %s' % (connectHP,))
                return forwarding.SSHConnectForwardingChannel(connectHP,
                                                remoteWindow = windowSize,
                                                remoteMaxPacket = maxPacket,
                                                conn = self)
            else:
                raise ConchError(connection.OPEN_CONNECT_FAILED, "don't know about that port")



def _makeArgs(args, mod="conch"):
    start = [sys.executable, '-c'
"""
### Twisted Preamble
import sys, os
path = os.path.abspath(sys.argv[0])
while os.path.dirname(path) != path:
    if os.path.basename(path).startswith('Twisted'):
        sys.path.insert(0, path)
        break
    path = os.path.dirname(path)

from twisted.conch.scripts.%s import run
run()""" % mod]
    return start + list(args)



class ForwardingTestBase(SignalMixin):
    """
    Template class for tests of the Conch server's ability to forward arbitrary
    protocols over SSH.

    These tests are integration tests, not unit tests. They launch a Conch
    server, a custom TCP server (just an L{EchoProtocol}) and then call
    L{execute}.

    L{execute} is implemented by subclasses of L{ForwardingTestBase}. It should
    cause an SSH client to connect to the Conch server, asking it to forward
    data to the custom TCP server.
    """

    if not Crypto:
        skip = "can't run w/o PyCrypto"

    def _createFiles(self):
        for f in ['rsa_test','rsa_test.pub','dsa_test','dsa_test.pub',
                  'kh_test']:
            if os.path.exists(f):
                os.remove(f)
        open('rsa_test','w').write(privateRSA_openssh)
        open('rsa_test.pub','w').write(publicRSA_openssh)
        open('dsa_test.pub','w').write(publicDSA_openssh)
        open('dsa_test','w').write(privateDSA_openssh)
        os.chmod('dsa_test', 33152)
        os.chmod('rsa_test', 33152)
        open('kh_test','w').write('127.0.0.1 '+publicRSA_openssh)


    def _getFreePort(self):
        f = EchoFactory()
        serv = reactor.listenTCP(0, f)
        port = serv.getHost().port
        serv.stopListening()
        return port


    def _makeConchFactory(self):
        """
        Make a L{ConchTestServerFactory}, which allows us to start a
        L{ConchTestServer} -- i.e. an actually listening conch.
        """
        realm = ConchTestRealm()
        p = portal.Portal(realm)
        p.registerChecker(ConchTestPublicKeyChecker())
        factory = ConchTestServerFactory()
        factory.portal = p
        return factory


    def setUp(self):
        self._createFiles()
        self.conchFactory = self._makeConchFactory()
        self.conchFactory.expectedLoseConnection = 1
        self.conchServer = reactor.listenTCP(0, self.conchFactory,
                                             interface="127.0.0.1")
        self.echoServer = reactor.listenTCP(0, EchoFactory())
        self.echoPort = self.echoServer.getHost().port


    def tearDown(self):
        try:
            self.conchFactory.proto.done = 1
        except AttributeError:
            pass
        else:
            self.conchFactory.proto.transport.loseConnection()
        return defer.gatherResults([
                defer.maybeDeferred(self.conchServer.stopListening),
                defer.maybeDeferred(self.echoServer.stopListening)])


    def test_exec(self):
        """
        Test that we can use whatever client to send the command "echo goodbye"
        to the Conch server. Make sure we receive "goodbye" back from the
        server.
        """
        d = self.execute('echo goodbye', ConchTestOpenSSHProcess())
        return d.addCallback(self.assertEquals, 'goodbye\n')


    def test_localToRemoteForwarding(self):
        """
        Test that we can use whatever client to forward a local port to a
        specified port on the server.
        """
        lport = self._getFreePort()
        process = ConchTestForwardingProcess(lport, 'test\n')
        d = self.execute('', process,
                         preargs='-N -L%i:127.0.0.1:%i'
                         % (lport, self.echoPort))
        d.addCallback(self.assertEqual, 'test\n')
        return d


    def test_remoteToLocalForwarding(self):
        """
        Test that we can use whatever client to forward a port from the server
        to a port locally.
        """
        lport = self._getFreePort()
        process = ConchTestForwardingProcess(lport, 'test\n')
        d = self.execute('', process,
                         preargs='-N -R %i:127.0.0.1:%i'
                         % (lport, self.echoPort))
        d.addCallback(self.assertEqual, 'test\n')
        return d



class OpenSSHClientTestCase(ForwardingTestBase, unittest.TestCase):

    def _findSSH(self):
        """
        Find an installed executable on the system called 'ssh' and return
        the absolute path to it.
        """
        # XXX - if we are going to search for installed binaries, then
        # we should do it by examining the PATH environment variable.
        for path in ['/usr', '', '/usr/local']:
            # XXX - should also check that its executable
            if os.path.exists(path + '/bin/ssh'):
                return path + '/bin/ssh'
         

    def execute(self, args, p, preargs = ''):
        p.deferred = defer.Deferred()
        cmdline = ('ssh -2 -l testuser -p %i '
                   '-oUserKnownHostsFile=kh_test '
                   '-oPasswordAuthentication=no '
                   # Always use the RSA key, since that's the one in kh_test.
                   '-oHostKeyAlgorithms=ssh-rsa '
                   '-a '
                   '-i dsa_test ') + preargs + \
                   ' 127.0.0.1 ' + args
        port = self.conchServer.getHost().port
        sshPath = self._findSSH()
        if not sshPath:
            raise unittest.SkipTest('skipping test, cannot find ssh')
        cmds = (cmdline % port).split()
        reactor.spawnProcess(p, sshPath, cmds)
        return p.deferred



class CmdLineClientTestCase(ForwardingTestBase, unittest.TestCase):
    def setUp(self):
        if runtime.platformType == 'win32':
            raise unittest.SkipTest("can't run cmdline client on win32")
        ForwardingTestBase.setUp(self)


    def execute(self, args, p, preargs=''):
        p.deferred = defer.Deferred()
        port = self.conchServer.getHost().port
        cmd = ('-p %i -l testuser '
               '--known-hosts kh_test '
               '--user-authentications publickey '
               '--host-key-algorithms ssh-rsa '
               '-a -I '
               '-K direct '
               '-i dsa_test '
               '-v ') % port + preargs + \
               ' 127.0.0.1 ' + args
        cmds = _makeArgs(cmd.split())
        log.msg(str(cmds))
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)
        reactor.spawnProcess(p, sys.executable, cmds, env=env)
        return p.deferred



class UnixClientTestCase(ForwardingTestBase, unittest.TestCase):
    def setUp(self):
        if runtime.platformType == 'win32':
            raise unittest.SkipTest("can't run cmdline client on win32")
        ForwardingTestBase.setUp(self)


    def execute(self, args, p, preargs = ''):
        p.deferred = defer.Deferred()
        port = self.conchServer.getHost().port
        cmd1 = ('-p %i -l testuser '
                '--known-hosts kh_test '
                '--user-authentications publickey '
                '--host-key-algorithms ssh-rsa '
                '-a '
                '-K direct '
                '-i dsa_test '
                '127.0.0.1') % port
        cmd2 = ('-p %i -l testuser '
                '-K unix '
                '-v ') % port + preargs + \
                ' 127.0.0.1 ' + args
        cmds1 = cmd1.split()
        cmds2 = _makeArgs(cmd2.split())
        o = options.ConchOptions()
        def _(host, *args):
            o['host'] = host
        o.parseArgs = _
        o.parseOptions(cmds1)
        vhk = default.verifyHostKey
        conn = SSHTestConnectionForUnix(p, sys.executable, cmds2)
        uao = default.SSHUserAuthClient(o['user'], o, conn)
        d = connect.connect(o['host'], int(o['port']), o, vhk, uao)
        d.addErrback(lambda f:
                     self.fail('Failure connecting to test server: %s' % f))
        d.addCallback(lambda x : p.deferred)
        def cleanup(buf):
            d = defer.maybeDeferred(conn.transport.transport.loseConnection)
            d.addCallback(lambda x: buf)
            return d
        d.addCallback(cleanup)
        return d
