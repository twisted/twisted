# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.client.default}.
"""

try:
    import Crypto.Cipher.DES3
except ImportError:
    skip = "PyCrypto required for twisted.conch.client.default."
else:
    from twisted.conch.client.default import SSHUserAuthClient
    from twisted.conch.client.options import ConchOptions
    from twisted.conch.ssh.agent import SSHAgentClient
    from twisted.conch.ssh.keys import Key


from twisted.trial.unittest import TestCase
from twisted.conch.test import keydata
from twisted.test.proto_helpers import StringTransport



class SSHUserAuthClientTest(TestCase):
    """
    Tests for L{SSHUserAuthClient}.

    @type rsaPublic: L{Key}
    @ivar rsaPublic: A public RSA key.
    """

    def setUp(self):
        self.rsaPublic = Key.fromString(keydata.publicRSA_openssh)


    def test_signDataWithAgent(self):
        """
        When connected to an agent, L{SSHUserAuthClient} can use it to
        request signatures of particular data with a particular L{Key}.
        """
        client = SSHUserAuthClient("user", ConchOptions(), None)
        agent = SSHAgentClient()
        transport = StringTransport()
        agent.makeConnection(transport)
        client.keyAgent = agent
        cleartext = "Sign here"
        client.signData(self.rsaPublic, cleartext)
        self.assertEquals(
            transport.value(),
            "\x00\x00\x00\x8b\r\x00\x00\x00u" + self.rsaPublic.blob() +
            "\x00\x00\x00\t" + cleartext +
            "\x00\x00\x00\x00")
