# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.client.default}.
"""
from twisted.python.reflect import requireModule

if requireModule('Crypto.Cipher.DES3') and requireModule('pyasn1'):
    from twisted.conch.client.agent import SSHAgentClient
    from twisted.conch.client.default import SSHUserAuthClient
    from twisted.conch.client.options import ConchOptions
    from twisted.conch.ssh.keys import Key
else:
    skip = "PyCrypto and PyASN1 required for twisted.conch.client.default."

from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath
from twisted.conch.test import keydata
from twisted.test.proto_helpers import StringTransport



class SSHUserAuthClientTests(TestCase):
    """
    Tests for L{SSHUserAuthClient}.

    @type rsaPublic: L{Key}
    @ivar rsaPublic: A public RSA key.
    """

    def setUp(self):
        self.rsaPublic = Key.fromString(keydata.publicRSA_openssh)
        self.tmpdir = FilePath(self.mktemp())
        self.tmpdir.makedirs()
        self.rsaFile = self.tmpdir.child('id_rsa')
        self.rsaFile.setContent(keydata.privateRSA_openssh)
        self.tmpdir.child('id_rsa.pub').setContent(keydata.publicRSA_openssh)


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
        self.assertEqual(
            transport.value(),
            "\x00\x00\x00\x8b\r\x00\x00\x00u" + self.rsaPublic.blob() +
            "\x00\x00\x00\t" + cleartext +
            "\x00\x00\x00\x00")


    def test_agentGetPublicKey(self):
        """
        L{SSHUserAuthClient} looks up public keys from the agent using the
        L{SSHAgentClient} class.  That L{SSHAgentClient.getPublicKey} returns a
        L{Key} object with one of the public keys in the agent.  If no more
        keys are present, it returns C{None}.
        """
        agent = SSHAgentClient()
        agent.blobs = [self.rsaPublic.blob()]
        key = agent.getPublicKey()
        self.assertEqual(key.isPublic(), True)
        self.assertEqual(key, self.rsaPublic)
        self.assertEqual(agent.getPublicKey(), None)


    def test_getPublicKeyFromFile(self):
        """
        L{SSHUserAuthClient.getPublicKey()} is able to get a public key from
        the first file described by its options' C{identitys} list, and return
        the corresponding public L{Key} object.
        """
        options = ConchOptions()
        options.identitys = [self.rsaFile.path]
        client = SSHUserAuthClient("user",  options, None)
        key = client.getPublicKey()
        self.assertEqual(key.isPublic(), True)
        self.assertEqual(key, self.rsaPublic)


    def test_getPublicKeyAgentFallback(self):
        """
        If an agent is present, but doesn't return a key,
        L{SSHUserAuthClient.getPublicKey} continue with the normal key lookup.
        """
        options = ConchOptions()
        options.identitys = [self.rsaFile.path]
        agent = SSHAgentClient()
        client = SSHUserAuthClient("user",  options, None)
        client.keyAgent = agent
        key = client.getPublicKey()
        self.assertEqual(key.isPublic(), True)
        self.assertEqual(key, self.rsaPublic)


    def test_getPublicKeyBadKeyError(self):
        """
        If L{keys.Key.fromFile} raises a L{keys.BadKeyError}, the
        L{SSHUserAuthClient.getPublicKey} tries again to get a public key by
        calling itself recursively.
        """
        options = ConchOptions()
        self.tmpdir.child('id_dsa.pub').setContent(keydata.publicDSA_openssh)
        dsaFile = self.tmpdir.child('id_dsa')
        dsaFile.setContent(keydata.privateDSA_openssh)
        options.identitys = [self.rsaFile.path, dsaFile.path]
        self.tmpdir.child('id_rsa.pub').setContent('not a key!')
        client = SSHUserAuthClient("user",  options, None)
        key = client.getPublicKey()
        self.assertEqual(key.isPublic(), True)
        self.assertEqual(key, Key.fromString(keydata.publicDSA_openssh))
        self.assertEqual(client.usedFiles, [self.rsaFile.path, dsaFile.path])


    def test_getPrivateKey(self):
        """
        L{SSHUserAuthClient.getPrivateKey} will load a private key from the
        last used file populated by L{SSHUserAuthClient.getPublicKey}, and
        return a L{Deferred} which fires with the corresponding private L{Key}.
        """
        rsaPrivate = Key.fromString(keydata.privateRSA_openssh)
        options = ConchOptions()
        options.identitys = [self.rsaFile.path]
        client = SSHUserAuthClient("user",  options, None)
        # Populate the list of used files
        client.getPublicKey()

        def _cbGetPrivateKey(key):
            self.assertEqual(key.isPublic(), False)
            self.assertEqual(key, rsaPrivate)

        return client.getPrivateKey().addCallback(_cbGetPrivateKey)


    def test_getPrivateKeyPassphrase(self):
        """
        L{SSHUserAuthClient} can get a private key from a file, and return a
        Deferred called back with a private L{Key} object, even if the key is
        encrypted.
        """
        rsaPrivate = Key.fromString(keydata.privateRSA_openssh)
        passphrase = 'this is the passphrase'
        self.rsaFile.setContent(rsaPrivate.toString('openssh', passphrase))
        options = ConchOptions()
        options.identitys = [self.rsaFile.path]
        client = SSHUserAuthClient("user",  options, None)
        # Populate the list of used files
        client.getPublicKey()

        def _getPassword(prompt):
            self.assertEqual(prompt,
                              "Enter passphrase for key '%s': " % (
                              self.rsaFile.path,))
            return passphrase

        def _cbGetPrivateKey(key):
            self.assertEqual(key.isPublic(), False)
            self.assertEqual(key, rsaPrivate)

        self.patch(client, '_getPassword', _getPassword)
        return client.getPrivateKey().addCallback(_cbGetPrivateKey)
