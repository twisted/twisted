# -*- test-case-name: twisted.conch.test.test_conch -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

import os, struct, sys, signal
from twisted.conch import avatar
from twisted.cred.credentials import IUsernamePassword
from twisted.cred import portal
from twisted.internet import reactor, defer, protocol, error
from twisted.python import log, failure, runtime
from twisted.trial import unittest, util
try:
    import Crypto
except:
    Crypto = None

from twisted.test.test_process import SignalMixin
from test_ssh import ConchTestRealm

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
    done = 0

    def connectionMade(self):
        log.msg('MAD(ssh): connection made')

    def outReceived(self, data):
        self.buf += data

    def errReceived(self, data):
        log.msg("ERR(ssh): '%s'" % data)

    def processEnded(self, reason):
        self.done = 1
        unittest.assertEquals(reason.value.exitCode, 0, 'exit code was not 0: %s' % reason.value.exitCode)
        self.buf = self.buf.replace('\r\n', '\n')
        unittest.assertEquals(self.buf, 'goodbye\n')

class ConchTestForwardingProcess(protocol.ProcessProtocol):

    def __init__(self, port, fac):
        self.port = port
        self.fac = fac
        self.done = 0
        self.connected = 0
        self.buf = ''

    def connectionMade(self):
        reactor.callLater(1, self._connect)
    
    def _connect(self):
        self.connected = 1
        cc = protocol.ClientCreator(reactor, ConchTestForwardingPort, self)
        d = cc.connectTCP('127.0.0.1', self.port)
        d.addErrback(self._ebConnect)

    def _ebConnect(self, f):
        # probably because the server wasn't listening in time
        # but who knows, just try again
        log.msg('ERROR CONNECTING TO %s' % self.port)
        log.err(f)
        log.flushErrors()
        reactor.callLater(1, self._connect)

    def errReceived(self, data):
        log.msg("ERR(ssh): '%s'" % data)

    def processEnded(self, reason):
        log.msg('FORWARDING PROCESS CLOSED')
        self.done = 1

class ConchTestForwardingPort(protocol.Protocol):

    data  = 'test forwarding\n'

    def __init__(self, proto):
        self.proto = proto

    def connectionMade(self):
        self.proto.fac.proto.expectedLoseConnection = 1
        self.buf = ''
        self.transport.write(self.data)

    def dataReceived(self, data):
        self.buf += data

    def connectionLost(self, reason):
        unittest.failUnlessEqual(self.buf, self.data)

        # forwarding-only clients don't die on their own
        self.proto.transport.write('\x03')
        os.kill(self.proto.transport.pid, signal.SIGHUP)

if Crypto:
    from twisted.conch.client import options, default, connect
    from twisted.conch.error import ConchError
    from twisted.conch.ssh import keys, transport, factory, forwarding 
    from twisted.conch.ssh import connection, common, session, channel
    from Crypto.PublicKey import RSA, DSA

    from test_keys import publicRSA_openssh, privateRSA_openssh
    from test_keys import publicDSA_openssh, privateDSA_openssh
    from test_ssh import ConchTestServerFactory, ConchTestPublicKeyChecker


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
                reactor.callLater(0,reactor.spawnProcess, env=os.environ, *self.spawn)
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

class CmdLineClientTestBase(SignalMixin):

    if not Crypto:
        skip = "can't run w/o PyCrypto"

    def setUpClass(self):
        SignalMixin.setUpClass(self)
        open('rsa_test','w').write(privateRSA_openssh)
        open('rsa_test.pub','w').write(publicRSA_openssh)
        open('dsa_test.pub','w').write(publicDSA_openssh)
        open('dsa_test','w').write(privateDSA_openssh)
        os.chmod('dsa_test', 33152)
        os.chmod('rsa_test', 33152)
        open('kh_test','w').write('localhost '+publicRSA_openssh)

    def tearDownClass(self):
        SignalMixin.tearDownClass(self)
        for f in ['rsa_test','rsa_test.pub','dsa_test','dsa_test.pub', 'kh_test']:
            os.remove(f)

    def setUp(self):
        realm = ConchTestRealm()
        p = portal.Portal(realm)
        p.registerChecker(ConchTestPublicKeyChecker())
        self.fac = fac = ConchTestServerFactory()
        fac.portal = p
        self.server = reactor.listenTCP(0, fac, interface="127.0.0.1")

    def tearDown(self):
        try:
            self.fac.proto.done = 1
        except AttributeError:
            pass
        else:
            self.fac.proto.transport.loseConnection()
            reactor.iterate()
        d = self.server.stopListening()
        if d:
            util.wait(d)

    # actual tests

    def testExec(self):
        p = ConchTestOpenSSHProcess()
        self.execute('echo goodbye', p)

    def testLocalToRemoteForwarding(self):
        f = EchoFactory()
        serv = reactor.listenTCP(0, f)
        port = serv.getHost().port
        p = ConchTestForwardingProcess(port+10,self.fac)
        self.execute('', p, preargs='-N -L%i:localhost:%i' % (port+10, port))
        serv.stopListening()

    def testRemoteToLocalForwarding(self):
        f = EchoFactory()
        serv = reactor.listenTCP(0, f)
        port = serv.getHost().port
        p = ConchTestForwardingProcess(port+10, self.fac)
        self.execute('', p, preargs='-N -R %i:localhost:%i' % (port+10, port))
        serv.stopListening()

class OpenSSHClientTestCase(CmdLineClientTestBase, unittest.TestCase):

    def execute(self, args, p, preargs = ''):
        cmdline = ('ssh -2 -l testuser -p %i '
                   '-oUserKnownHostsFile=kh_test '
                   '-oPasswordAuthentication=no '
                   # Always use the RSA key, since that's the one in kh_test.
                   '-oHostKeyAlgorithms=ssh-rsa '
                   '-a '
                   '-i dsa_test ') + preargs + \
                   ' localhost ' + args
        port = self.server.getHost().port
        ssh_path = None
        for path in ['/usr', '', '/usr/local']:
            if os.path.exists(path+'/bin/ssh'):
                ssh_path = path+'/bin/ssh'
                break
        if not ssh_path:
            log.msg('skipping test, cannot find ssh')
            raise unittest.SkipTest, 'skipping test, cannot find ssh'
        cmds = (cmdline % port).split()
        reactor.spawnProcess(p, ssh_path, cmds)
        util.spinWhile(lambda: not p.done, timeout=10)

        # cleanup
        if not p.done:
            os.kill(p.transport.pid, signal.SIGTERM)
            util.spinWhile(lambda: not p.done)

class CmdLineClientTestCase(CmdLineClientTestBase, unittest.TestCase):

    def execute(self, args, p, preargs=''):
        if runtime.platformType == 'win32':
            raise unittest.SkipTest, "can't run cmdline client on win32"
        port = self.server.getHost().port
        cmd = ('-p %i -l testuser '
               '--known-hosts kh_test '
               '--user-authentications publickey '
               '--host-key-algorithms ssh-rsa '
               '-a -I '
               '-K direct '
               '-i dsa_test '
               '-v ') % port + preargs + \
               ' localhost ' + args
        cmds = _makeArgs(cmd.split())
        log.msg(str(cmds))
        reactor.spawnProcess(p, sys.executable, cmds, env=os.environ)
        # wait for process to finish
        util.spinWhile(lambda: not p.done, timeout=10)
        
        # cleanup
        if not p.done:
            os.kill(p.transport.pid, signal.SIGTERM)
            util.spinWhile(lambda: not p.done)

class UnixClientTestCase(CmdLineClientTestBase, unittest.TestCase):

    def execute(self, args, p, preargs = ''):
        if runtime.platformType == 'win32':
            raise unittest.SkipTest, "can't run cmdline client on win32"
        port = self.server.getHost().port
        cmd1 = ('-p %i -l testuser '
                '--known-hosts kh_test '
                '--user-authentications publickey '
                '--host-key-algorithms ssh-rsa '
                '-a ' 
                '-K direct '
                '-i dsa_test '
                'localhost') % port
        cmd2 = ('-p %i -l testuser '
                '-K unix '
                '-v ') % port + preargs + \
                ' localhost ' + args
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
        d.addErrback(lambda f: unittest.fail('Failure connecting to test server: %s' % f))
        
        util.spinWhile(lambda: not p.done, timeout=10)

        # cleanup
        if not p.done:
            os.kill(p.transport.pid, signal.SIGTERM)
            util.spinWhile(lambda: not p.done)
        conn.transport.transport.loseConnection()
        reactor.iterate()
