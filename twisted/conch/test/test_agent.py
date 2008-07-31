from zope.interface import implements

from twisted.conch.ssh import agent, keys

from twisted.trial import unittest
from twisted.test import iosim
from twisted.conch.test import keydata
from twisted.conch.error import ConchError

class MockFactory(object): 
    keys = {}

class AgentTestBase(unittest.TestCase):
    """Tests for SSHAgentServer/Client."""

    def setUp(self):
        # wire up our client <-> server
        self.client, self.server, self.pump = iosim.connectedServerAndClient(agent.SSHAgentServer, 
                                                                             agent.SSHAgentClient)

        # the server's end of the protocol is stateful and we store it on the factory, for which we
        # only need a mock
        self.server.factory = MockFactory()        

        # pub/priv keys of each kind
        self.rsa_priv = keys.Key.fromString(keydata.privateRSA_openssh)
        self.dsa_priv = keys.Key.fromString(keydata.privateDSA_openssh)

        self.rsa_pub = keys.Key.fromString(keydata.publicRSA_openssh)
        self.dsa_pub = keys.Key.fromString(keydata.publicDSA_openssh)

class TestUnimplementedVersionOneServer(AgentTestBase):
    """Tests for methods with no-op implementations on the server. We need these
       for clients, such as openssh, that try v1 methods before going to v2.

       Because the client doesn't expose these operations with nice method names,
       we invoke sendRequest directly with an op code.
    """

    def test_agentc_REQUEST_RSA_IDENTITIES(self):
        d = self.client.sendRequest(agent.AGENTC_REQUEST_RSA_IDENTITIES, '')
        self.pump.flush()
        def _cb(packet):
            self.assertEquals(agent.AGENT_RSA_IDENTITIES_ANSWER, ord(packet[0]))
        return d.addCallback(_cb)

    def test_agentc_REMOVE_RSA_IDENTITY(self):
        d = self.client.sendRequest(agent.AGENTC_REMOVE_RSA_IDENTITY, '')
        self.pump.flush()
        def _cb(emptystr):
            self.assertEquals('', emptystr)
        return d.addCallback(_cb)

    def test_agentc_REMOVE_ALL_RSA_IDENTITIES(self):
        d = self.client.sendRequest(agent.AGENTC_REMOVE_ALL_RSA_IDENTITIES, '')
        self.pump.flush()
        def _cb(emptystr):
            self.assertEquals('', emptystr)
        return d.addCallback(_cb)

class CorruptServer(agent.SSHAgentServer):
    """A misbehaving server that returns bogus response op codes so that we can
       verify that our callbacks that deal with these op codes handle such miscreants."""
    def agentc_REQUEST_IDENTITIES(self, data):
        self.sendResponse(254, '')

    def agentc_SIGN_REQUEST(self, data):
        self.sendResponse(254, '')

class TestClientWithBrokenServer(AgentTestBase):
    """verify error handling code in the client using a misbehaving server"""
    def setUp(self):
        AgentTestBase.setUp(self)
        self.client, self.server, self.pump = iosim.connectedServerAndClient(CorruptServer,
                                                                             agent.SSHAgentClient)
        # the server's end of the protocol is stateful and we store it on the factory, for which we
        # only need a mock
        self.server.factory = MockFactory()        

    def test_signDataCallbackErrorHandling(self):
        d = self.client.signData(self.rsa_pub.blob(), "John Hancock")
        self.pump.flush()
        def _eb(f):
            try:
                f.trap(ConchError)
            except:
                self.fail("Expected ConchError on errback")
        return d.addCallback(lambda x: self.fail("expected errback")).addErrback(_eb)

    def test_requestIdentitiesCallbackErrorHandling(self):
        d = self.client.requestIdentities()
        self.pump.flush()
        def _eb(f):
            try:
                f.trap(ConchError)
            except:
                self.fail("Expected ConchError on errback")
        return d.addCallback(lambda x: self.fail("expected errback")).addErrback(_eb)

class TestAgentKeyAddition(AgentTestBase):
    """Test adding different flavors of keys to an agent."""
    def test_addRSAIdentityNoComment(self):
        d = self.client.addIdentity(self.rsa_priv.privateBlob())
        self.pump.flush()
        def _check(ignored):
            servers_key_tuple = self.server.factory.keys[self.rsa_priv.blob()]
            self.assertEquals(self.rsa_priv, servers_key_tuple[0])
            self.assertEquals('', servers_key_tuple[1])
        return d.addCallback(_check)

    def test_addDSAIdentityNoComment(self):
        d = self.client.addIdentity(self.dsa_priv.privateBlob())
        self.pump.flush()
        def _check(ignored):
            servers_key_tuple = self.server.factory.keys[self.dsa_priv.blob()]
            self.assertEquals(self.dsa_priv, servers_key_tuple[0])
            self.assertEquals('', servers_key_tuple[1])
        return d.addCallback(_check)

    def test_addRSAIdentityWithComment(self):
        d = self.client.addIdentity(self.rsa_priv.privateBlob(), comment='My special key')
        self.pump.flush()
        def _check(ignored):
            servers_key_tuple = self.server.factory.keys[self.rsa_priv.blob()]
            self.assertEquals(self.rsa_priv, servers_key_tuple[0])
            self.assertEquals('My special key', servers_key_tuple[1])
        return d.addCallback(_check)

    def test_addDSAIdentityWithComment(self):
        d = self.client.addIdentity(self.dsa_priv.privateBlob(), comment='My special key')
        self.pump.flush()
        def _check(ignored):
            servers_key_tuple = self.server.factory.keys[self.dsa_priv.blob()]
            self.assertEquals(self.dsa_priv, servers_key_tuple[0])
            self.assertEquals('My special key', servers_key_tuple[1])
        return d.addCallback(_check)

class TestAgentClientFailure(AgentTestBase):
    def test_agentFailure(self):
        "verify that the client raises ConchError on AGENT_FAILURE"
        d = self.client.sendRequest(254, '')        
        self.pump.flush()
        def _eb(f):
            try:
                f.trap(ConchError)
            except:
                self.fail("got something other than ConchError on AGENT_FAILURE")
        return d.addCallback(lambda x: self.fail("expected ConchError")).addErrback(_eb)

class TestAgentIdentityRequests(AgentTestBase):
    """Test operations against a server with identities already loaded"""
    def setUp(self):
        AgentTestBase.setUp(self)
        self.server.factory.keys[self.dsa_priv.blob()] = (self.dsa_priv, 'a comment')
        self.server.factory.keys[self.rsa_priv.blob()] = (self.rsa_priv, 'another comment')

    def test_signDataRSA(self):
        d = self.client.signData(self.rsa_pub.blob(), "John Hancock")
        self.pump.flush()
        def _check(sig):
            expected = self.rsa_priv.sign("John Hancock")
            self.assertEquals(expected, sig)
            self.assertTrue(self.rsa_pub.verify(sig, "John Hancock"))
        return d.addCallback(_check)

    def test_signDataDSA(self):
        d = self.client.signData(self.dsa_pub.blob(), "John Hancock")
        self.pump.flush()
        def _check(sig):
        #    expected = self.dsa_priv.sign("John Hancock")
        #  Cannot do this b/c DSA uses random numbers when signing
        #    self.assertEquals(expected, sig)
             self.assertTrue(self.dsa_pub.verify(sig, "John Hancock"))
        return d.addCallback(_check)

    def test_signDataRSAErrbackOnUnknownBlob(self):
        del self.server.factory.keys[self.rsa_pub.blob()]
        d = self.client.signData(self.rsa_pub.blob(), "John Hancock")
        self.pump.flush()
        def _eb(f):
            try:
                f.trap(ConchError)
            except:
                self.fail("Expected ConchError on errback")
        return d.addCallback(lambda x: self.fail("expected callback")).addErrback(_eb)

    def test_requestIdentities(self):
        d = self.client.requestIdentities()
        self.pump.flush()
        def _check(keyt):
            expected = {}
            expected[self.dsa_pub.blob()] = 'a comment'
            expected[self.rsa_pub.blob()] = 'another comment'

            received = dict((keys.Key.fromString(k[0], type='blob').blob(), k[1]) for k in keyt)
            self.assertEquals(expected, received)
        return d.addCallback(_check)

class TestAgentKeyRemoval(AgentTestBase):
    """Test support for removing keys in a remote server"""
    def setUp(self):
        AgentTestBase.setUp(self)
        self.server.factory.keys[self.dsa_priv.blob()] = (self.dsa_priv, 'a comment')
        self.server.factory.keys[self.rsa_priv.blob()] = (self.rsa_priv, 'another comment')

    def test_removeRSAIdentity(self):
        d = self.client.removeIdentity(self.rsa_priv.blob()) # only need public key for this
        self.pump.flush()

        def _check(ignored):
            self.assertEquals(1, len(self.server.factory.keys))
            self.assertTrue(self.server.factory.keys.has_key(self.dsa_priv.blob()))
            self.assertFalse(self.server.factory.keys.has_key(self.rsa_priv.blob()))
        return d.addCallback(_check)

    def test_removeDSAIdentity(self):
        d = self.client.removeIdentity(self.dsa_priv.blob()) # only need public key for this
        self.pump.flush()

        def _check(ignored):
            self.assertEquals(1, len(self.server.factory.keys))
            self.assertTrue(self.server.factory.keys.has_key(self.rsa_priv.blob()))
        return d.addCallback(_check)

    def test_removeAllIdentities(self):
        d = self.client.removeAllIdentities()
        self.pump.flush()

        def _check(ignored):
            self.assertEquals(0, len(self.server.factory.keys))
        return d.addCallback(_check)
