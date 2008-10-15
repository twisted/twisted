# -*- test-case-name: twisted.conch.test.test_cftp -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE file for details.

import sys, os

try:
    import Crypto.Cipher.DES3
except ImportError:
    Crypto = None

try:
    from twisted.conch import unix, error
    from twisted.conch.scripts import cftp
    from twisted.conch.client import connect, default, options, direct
    from twisted.conch.ssh import connection, transport
    from twisted.conch.test.test_filetransfer import FileTransferForTestAvatar
except ImportError:
    unix = None
    try:
        del sys.modules['twisted.conch.unix'] # remove the bad import
    except KeyError:
        # In Python 2.4, the bad import has already been cleaned up for us.
        pass

from twisted.cred import portal
from twisted.internet import reactor, protocol, interfaces, defer
from twisted.internet.utils import getProcessOutputAndValue
from twisted.python import log
from twisted.conch.client import direct, options
from twisted.trial import unittest

from twisted.conch.test import test_ssh, test_conch
from twisted.conch.test.test_filetransfer import SFTPTestBase
from twisted.conch.test.test_filetransfer import TestAvatar

class TestRealm:
    def requestAvatar(self, avatarID, mind, *interfaces):
        a = TestAvatar()
        return interfaces[0], a, lambda: None

class ClientTestBase(unittest.TestCase):
    """
    Provides SSH server start/stop capabilities that our subclasses
    (which test client behavior) can rely on.
    """

    def setUp(self):
        """
        Prepare the key data and known hosts files.
        """

        f = open('dsa_test.pub','w')
        f.write(test_ssh.publicDSA_openssh)
        f.close()
        f = open('dsa_test','w')
        f.write(test_ssh.privateDSA_openssh)
        f.close()
        os.chmod('dsa_test', 33152)
        f = open('kh_test','w')
        f.write('127.0.0.1 ' + test_ssh.publicRSA_openssh)
        f.close()

    def startServer(self):
        """
        Fire up an SSH server on an available port.
        """

        realm = TestRealm()
        p = portal.Portal(realm)
        p.registerChecker(test_ssh.ConchTestPublicKeyChecker())
        self.serverFactory = test_ssh.ConchTestServerFactory()
        self.serverFactory.portal = p
        self.server = reactor.listenTCP(0, self.serverFactory, interface="127.0.0.1")

    def stopServer(self):
        """
        Bring down the SSH server
        """

        if not hasattr(self.server.factory, 'proto'):
            return self._cbStopServer(None)
        self.server.factory.proto.expectedLoseConnection = 1
        d = defer.maybeDeferred(
            self.server.factory.proto.transport.loseConnection)
        d.addCallback(self._cbStopServer)
        return d

    def _cbStopServer(self, ignored):
        return defer.maybeDeferred(self.server.stopListening)

    def tearDown(self):
        """
        Clean up the files we created for our tests.
        """

        for f in ['dsa_test.pub', 'dsa_test', 'kh_test']:
            try:
                os.remove(f)
            except:
                pass

class TestOurServerOurClientConnections(ClientTestBase):
    """
    Tests that exercise connection behavior for conch clients talking
    to conch servers.  The server could just as easily be an OpenSSH
    server, as it is not under test in these scenarios.
    """

    def setUp(self):
        """
        Start up a server before each test.
        """

        d = defer.maybeDeferred(ClientTestBase.setUp, self)
        d.addCallback(lambda _: self.startServer())
        return d

    def tearDown(self):
        """
        Kill off our server
        """

        d = defer.maybeDeferred(ClientTestBase.tearDown, self)
        d.addCallback(lambda _: self.stopServer())
        return d

    def _makeOpts(self):
        """
        create the options we'll use for the SSH client.
        """

        opts = options.ConchOptions()
        opts['noagent'] = 1
        opts['user'] = 'testuser'
        opts['port'] = self.server.getHost().port
        opts['identity'] = 'dsa_test'
        opts['known_hosts'] = 'kh_test'
        opts['user-authentications'] = 'publickey'
        opts['host-key-algorithms'] = ['ssh-rsa',]
        opts['connection-usage'] = 'direct'
        opts['log'] = 1
        opts.identitys = ['dsa_test',]
        return opts

    def _cbConnect(self, ignored, conn):
        """
        A callback that arranges additional callbacks for the deferred on the supplied connection.
        These shutdown the connection.

        Returns the connection's deferred so that it can become part of the callback chain.
        """
        conn.deferred.addCallback(lambda _: log.msg("client connection is up, ready to close it down"))
        conn.deferred.addCallback((lambda _, c: c.transport.loseConnection()), conn)
        return conn.deferred

    def test_direct_connect_lose_connection_workaround(self):
        """
        direct.connect has a buggy factory that relies on a single
        Deferred for multiple goals: notificaction of connection
        failures AND of connection termination.  To work around this,
        it's necessary to inject a replacement deferred onto the
        connection's factory so that requests to close the transport
        down are not ignored.  When the replacement deferred is fired,
        it gets an errback even during an orderly shutdown, so it's
        also necessary to examine the cause of the disconnect.
        """

        # a conch options instance
        opts = self._makeOpts()
        # an all-permitting verify host key function
        vhk = lambda *ignored: defer.succeed(1)

        # a connection that calls back when the (client) service is started
        conn = ClientConnection()

        # the workaround
        def _cbInjectReplacementDeferredOnFactory(ign, d, conn):
            log.msg("will insert new deferred on factory")
            conn.transport.factory.d = d
        
        # the replacement deferred for the transport's factory
        newd = defer.Deferred()

        # set up a connection as usual
        d = direct.connect(self.server.getHost().host, opts['port'], 
                           opts, vhk, default.SSHUserAuthClient(opts['user'], opts, conn))

        # after we get called back, inject the replacement
        d.addCallback(_cbInjectReplacementDeferredOnFactory, newd, conn)
        # and then "normal" work can begin, in this case, we just call loseConnection
        d.addCallback(self._cbConnect, conn)
        
        # the replacement deferred will get an errback when
        # loseConnection eventually happens
        afd = self.assertFailure(newd, error.ConchError)
        # and that errback's value will be a connection lost message,
        # since that's what we wanted.
        afd.addCallback(lambda v: self.assertEquals(transport.DISCONNECT_CONNECTION_LOST, v.data))
        return afd

    def test_connect_connectTCP_loseConnection(self):
        """
        Test that connections openned with connect.connectTCP do not have
        the same issues as those opened with direct.connect.
        """

        # a conch options instance
        opts = self._makeOpts()
        # an all-permitting verify host key function
        vhk = lambda *ignored: defer.succeed(1)

        # a connection that calls back when the (client) service is started
        conn = ClientConnection()

        # set up a connection as usual
        willConnect = connect.connectTCP(self.server.getHost().host, opts['port'], 
                                         opts, vhk, default.SSHUserAuthClient(opts['user'], opts, conn))

        willConnect.addCallback(lambda _: log.msg("will connect did connect"))
        # and then "normal" work can begin, in this case, we just call loseConnection
        willConnect.addCallback(self._cbConnect, conn)

        def _cb_didDisconnect(ignored, conn):
            dd = conn.transport.factory.didDisconnect
            dd.addErrback(lambda f: self.assertEquals(transport.DISCONNECT_CONNECTION_LOST, f.value.data))
            return dd

        willConnect.addCallback(_cb_didDisconnect, conn)
        
        return willConnect

    def test_connect_connectTCP_serverDisconnects(self):
        """
        test callback/errback chain of our client when the server
        drops the connection.
        """

        # a conch options instance
        opts = self._makeOpts()
        # an all-permitting verify host key function
        vhk = lambda *ignored: defer.succeed(1)

        # a connection that calls back when the (client) service is started
        conn = ClientConnection()

        # set up a connection as usual
        willConnect = connect.connectTCP(self.server.getHost().host, opts['port'], 
                                         opts, vhk, default.SSHUserAuthClient(opts['user'], opts, conn))

        willConnect.addCallback(lambda _: log.msg("will connect did connect"))

        def _cb_serverDisconnect(ignored):
            # make our server shutdown so that the client has to
            # show that it can handle that case
            self.serverFactory.proto.expectedLoseConnection = 1
            self.serverFactory.proto.loseConnection()

        willConnect.addCallback(_cb_serverDisconnect)

        def _cb_didDisconnect(ignored, conn):
            dd = conn.transport.factory.didDisconnect
            dd.addErrback(lambda f: self.assertEquals(transport.DISCONNECT_CONNECTION_LOST, f.value.data))
            return dd

        willConnect.addCallback(_cb_didDisconnect, conn)
        
        return willConnect

    def test_connect_connectTCP_err_handling_during_connection(self):
        """
        test err back chain when the connection can't be established.
        """

        # a conch options instance
        opts = self._makeOpts()
        # an host key verifier that fails every time
        vhk = lambda *ignored: defer.fail(1)

        # a connection that calls back when the (client) service is started
        conn = ClientConnection()

        # set up a connection as usual
        willConnect = connect.connectTCP(self.server.getHost().host, opts['port'], 
                                         opts, vhk, default.SSHUserAuthClient(opts['user'], opts, conn))

        willConnect.addErrback(lambda f: self.assertEquals(transport.DISCONNECT_HOST_KEY_NOT_VERIFIABLE, f.value.data))
        # make certain the errback got called
        willConnect.addCallback(lambda d: self.assertEquals(transport.DISCONNECT_HOST_KEY_NOT_VERIFIABLE, d))

        return willConnect

class ClientConnection(connection.SSHConnection):
    """
    A simple SSHConnection that calls back on a deferred when it gets
    the serviceStarted notification.
    """

    def __init__(self):
        """
        Set up in the super class and then prepare a deferred.
        """

        connection.SSHConnection.__init__(self)
        self.deferred = defer.Deferred()

    def serviceStarted(self):
        """
        We're ready to start opening channels now, so tell whoever
        is monitoring our deferred.
        """

        connection.SSHConnection.serviceStarted(self)
        self.deferred.callback(None)

if not unix or not Crypto or not interfaces.IReactorProcess(reactor, None):
    TestOurServerOurClient.skip = "don't run w/o PyCrypto"
