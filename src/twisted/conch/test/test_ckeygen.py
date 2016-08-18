# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.scripts.ckeygen}.
"""

import __builtin__
import getpass
import sys
from StringIO import StringIO

from twisted.python.reflect import requireModule

if requireModule('cryptography') and requireModule('pyasn1'):
    from twisted.conch.ssh.keys import (Key, BadKeyError,
        BadFingerPrintFormat, FingerprintFormats)
    from twisted.conch.scripts.ckeygen import (
        changePassPhrase, displayPublicKey, printFingerprint,
        _saveKey, enumrepresentation)
else:
    skip = "cryptography and pyasn1 required for twisted.conch.scripts.ckeygen"

from twisted.python.filepath import FilePath
from twisted.trial.unittest import TestCase
from twisted.conch.test.keydata import (
    publicRSA_openssh, privateRSA_openssh, privateRSA_openssh_encrypted)



def makeGetpass(*passphrases):
    """
    Return a callable to patch C{getpass.getpass}.  Yields a passphrase each
    time called. Use case is to provide an old, then new passphrase(s) as if
    requested interactively.

    @param passphrases: The list of passphrases returned, one per each call.

    @return: A callable to patch C{getpass.getpass}.
    """
    passphrases = iter(passphrases)

    def fakeGetpass(_):
        return passphrases.next()

    return fakeGetpass



class KeyGenTests(TestCase):
    """
    Tests for various functions used to implement the I{ckeygen} script.
    """
    def setUp(self):
        """
        Patch C{sys.stdout} with a L{StringIO} instance to tests can make
        assertions about what's printed.
        """
        self.stdout = StringIO()
        self.patch(sys, 'stdout', self.stdout)


    def test_enumrepresentation(self):
        """
        L{enumrepresentation} takes a dictionary as input and returns a
        dictionary with its attributes changed to enum representation.
        """
        options = enumrepresentation({'format': 'md5-hex'})
        self.assertIs(options['format'],
            FingerprintFormats.MD5_HEX)


    def test_enumrepresentationsha256(self):
        """
        Test for format L{FingerprintFormats.SHA256-BASE64}.
        """
        options = enumrepresentation({'format': 'sha256-base64'})
        self.assertIs(options['format'],
            FingerprintFormats.SHA256_BASE64)



    def test_enumrepresentationBadFormat(self):
        """
        Test for unsupported fingerprint format
        """
        with self.assertRaises(BadFingerPrintFormat) as em:
            enumrepresentation({'format': 'sha-base64'})
        self.assertEqual('Unsupported fingerprint format: sha-base64',
            em.exception.args[0])



    def test_printFingerprint(self):
        """
        L{printFingerprint} writes a line to standard out giving the number of
        bits of the key, its fingerprint, and the basename of the file from it
        was read.
        """
        filename = self.mktemp()
        FilePath(filename).setContent(publicRSA_openssh)
        printFingerprint({'filename': filename,
            'format': 'md5-hex'})
        self.assertEqual(
            self.stdout.getvalue(),
            '768 3d:13:5f:cb:c9:79:8a:93:06:27:65:bc:3d:0b:8f:af temp\n')


    def test_printFingerprintsha256(self):
        """
        L{printFigerprint} will print key fingerprint in
        L{FingerprintFormats.SHA256-BASE64} format if explicitly specified.
        """
        filename = self.mktemp()
        FilePath(filename).setContent(publicRSA_openssh)
        printFingerprint({'filename': filename,
            'format': 'sha256-base64'})
        self.assertEqual(
            self.stdout.getvalue(),
            '768 ryaugIFT0B8ItuszldMEU7q14rG/wj9HkRosMeBWkts= temp\n')


    def test_printFingerprintBadFingerPrintFormat(self):
        """
        L{printFigerprint} raises C{keys.BadFingerprintFormat} when unsupported
        formats are requested.
        """
        filename = self.mktemp()
        FilePath(filename).setContent(publicRSA_openssh)
        with self.assertRaises(BadFingerPrintFormat) as em:
            printFingerprint({'filename': filename, 'format':'sha-base64'})
        self.assertEqual('Unsupported fingerprint format: sha-base64',
            em.exception.args[0])


    def test_saveKey(self):
        """
        L{_saveKey} writes the private and public parts of a key to two
        different files and writes a report of this to standard out.
        """
        base = FilePath(self.mktemp())
        base.makedirs()
        filename = base.child('id_rsa').path
        key = Key.fromString(privateRSA_openssh)
        _saveKey(key, {'filename': filename, 'pass': 'passphrase',
            'format': 'md5-hex'})
        self.assertEqual(
            self.stdout.getvalue(),
            "Your identification has been saved in %s\n"
            "Your public key has been saved in %s.pub\n"
            "The key fingerprint in <FingerprintFormats=MD5_HEX> is:\n"
            "3d:13:5f:cb:c9:79:8a:93:06:27:65:bc:3d:0b:8f:af\n" % (
                filename,
                filename))
        self.assertEqual(
            key.fromString(
                base.child('id_rsa').getContent(), None, 'passphrase'),
            key)
        self.assertEqual(
            Key.fromString(base.child('id_rsa.pub').getContent()),
            key.public())


    def test_saveKeysha256(self):
        """
        L{_saveKey} will generate key fingerprint in
        L{FingerprintFormats.SHA256-BASE64} format if explicitly specified.
        """
        base = FilePath(self.mktemp())
        base.makedirs()
        filename = base.child('id_rsa').path
        key = Key.fromString(privateRSA_openssh)
        _saveKey(key, {'filename': filename, 'pass': 'passphrase',
            'format': 'sha256-base64'})
        self.assertEqual(
            self.stdout.getvalue(),
            "Your identification has been saved in %s\n"
            "Your public key has been saved in %s.pub\n"
            "The key fingerprint in <FingerprintFormats=SHA256_BASE64> is:\n"
            "ryaugIFT0B8ItuszldMEU7q14rG/wj9HkRosMeBWkts=\n" % (
                filename,
                filename))
        self.assertEqual(
            key.fromString(
                base.child('id_rsa').getContent(), None, 'passphrase'),
            key)
        self.assertEqual(
            Key.fromString(base.child('id_rsa.pub').getContent()),
            key.public())


    def test_saveKeyBadFingerPrintformat(self):
        """
        L{_saveKey} raises C{keys.BadFingerprintFormat} when unsupported
        formats are requested.
        """
        base = FilePath(self.mktemp())
        base.makedirs()
        filename = base.child('id_rsa').path
        key = Key.fromString(privateRSA_openssh)
        with self.assertRaises(BadFingerPrintFormat) as em:
            _saveKey(key, {'filename': filename, 'pass': 'passphrase',
                'format': 'sha-base64'})
        self.assertEqual('Unsupported fingerprint format: sha-base64',
            em.exception.args[0])


    def test_saveKeyEmptyPassphrase(self):
        """
        L{_saveKey} will choose an empty string for the passphrase if
        no-passphrase is C{True}.
        """
        base = FilePath(self.mktemp())
        base.makedirs()
        filename = base.child('id_rsa').path
        key = Key.fromString(privateRSA_openssh)
        _saveKey(key, {'filename': filename, 'no-passphrase': True,
            'format': 'md5-hex'})
        self.assertEqual(
            key.fromString(
                base.child('id_rsa').getContent(), None, b''),
            key)


    def test_saveKeyNoFilename(self):
        """
        When no path is specified, it will ask for the path used to store the
        key.
        """
        base = FilePath(self.mktemp())
        base.makedirs()
        keyPath = base.child('custom_key').path

        self.patch(__builtin__, 'raw_input', lambda _: keyPath)
        key = Key.fromString(privateRSA_openssh)
        _saveKey(key, {'filename': None, 'no-passphrase': True,
            'format': 'md5-hex'})

        persistedKeyContent = base.child('custom_key').getContent()
        persistedKey = key.fromString(persistedKeyContent, None, b'')
        self.assertEqual(key, persistedKey)


    def test_displayPublicKey(self):
        """
        L{displayPublicKey} prints out the public key associated with a given
        private key.
        """
        filename = self.mktemp()
        pubKey = Key.fromString(publicRSA_openssh)
        FilePath(filename).setContent(privateRSA_openssh)
        displayPublicKey({'filename': filename})
        self.assertEqual(
            self.stdout.getvalue().strip('\n'),
            pubKey.toString('openssh'))


    def test_displayPublicKeyEncrypted(self):
        """
        L{displayPublicKey} prints out the public key associated with a given
        private key using the given passphrase when it's encrypted.
        """
        filename = self.mktemp()
        pubKey = Key.fromString(publicRSA_openssh)
        FilePath(filename).setContent(privateRSA_openssh_encrypted)
        displayPublicKey({'filename': filename, 'pass': 'encrypted'})
        self.assertEqual(
            self.stdout.getvalue().strip('\n'),
            pubKey.toString('openssh'))


    def test_displayPublicKeyEncryptedPassphrasePrompt(self):
        """
        L{displayPublicKey} prints out the public key associated with a given
        private key, asking for the passphrase when it's encrypted.
        """
        filename = self.mktemp()
        pubKey = Key.fromString(publicRSA_openssh)
        FilePath(filename).setContent(privateRSA_openssh_encrypted)
        self.patch(getpass, 'getpass', lambda x: 'encrypted')
        displayPublicKey({'filename': filename})
        self.assertEqual(
            self.stdout.getvalue().strip('\n'),
            pubKey.toString('openssh'))


    def test_displayPublicKeyWrongPassphrase(self):
        """
        L{displayPublicKey} fails with a L{BadKeyError} when trying to decrypt
        an encrypted key with the wrong password.
        """
        filename = self.mktemp()
        FilePath(filename).setContent(privateRSA_openssh_encrypted)
        self.assertRaises(
            BadKeyError, displayPublicKey,
            {'filename': filename, 'pass': 'wrong'})


    def test_changePassphrase(self):
        """
        L{changePassPhrase} allows a user to change the passphrase of a
        private key interactively.
        """
        oldNewConfirm = makeGetpass('encrypted', 'newpass', 'newpass')
        self.patch(getpass, 'getpass', oldNewConfirm)

        filename = self.mktemp()
        FilePath(filename).setContent(privateRSA_openssh_encrypted)

        changePassPhrase({'filename': filename})
        self.assertEqual(
            self.stdout.getvalue().strip('\n'),
            'Your identification has been saved with the new passphrase.')
        self.assertNotEqual(privateRSA_openssh_encrypted,
                            FilePath(filename).getContent())


    def test_changePassphraseWithOld(self):
        """
        L{changePassPhrase} allows a user to change the passphrase of a
        private key, providing the old passphrase and prompting for new one.
        """
        newConfirm = makeGetpass('newpass', 'newpass')
        self.patch(getpass, 'getpass', newConfirm)

        filename = self.mktemp()
        FilePath(filename).setContent(privateRSA_openssh_encrypted)

        changePassPhrase({'filename': filename, 'pass': 'encrypted'})
        self.assertEqual(
            self.stdout.getvalue().strip('\n'),
            'Your identification has been saved with the new passphrase.')
        self.assertNotEqual(privateRSA_openssh_encrypted,
                            FilePath(filename).getContent())


    def test_changePassphraseWithBoth(self):
        """
        L{changePassPhrase} allows a user to change the passphrase of a private
        key by providing both old and new passphrases without prompting.
        """
        filename = self.mktemp()
        FilePath(filename).setContent(privateRSA_openssh_encrypted)

        changePassPhrase(
            {'filename': filename, 'pass': 'encrypted',
             'newpass': 'newencrypt'})
        self.assertEqual(
            self.stdout.getvalue().strip('\n'),
            'Your identification has been saved with the new passphrase.')
        self.assertNotEqual(privateRSA_openssh_encrypted,
                            FilePath(filename).getContent())


    def test_changePassphraseWrongPassphrase(self):
        """
        L{changePassPhrase} exits if passed an invalid old passphrase when
        trying to change the passphrase of a private key.
        """
        filename = self.mktemp()
        FilePath(filename).setContent(privateRSA_openssh_encrypted)
        error = self.assertRaises(
            SystemExit, changePassPhrase,
            {'filename': filename, 'pass': 'wrong'})
        self.assertEqual('Could not change passphrase: old passphrase error',
                         str(error))
        self.assertEqual(privateRSA_openssh_encrypted,
                         FilePath(filename).getContent())


    def test_changePassphraseEmptyGetPass(self):
        """
        L{changePassPhrase} exits if no passphrase is specified for the
        C{getpass} call and the key is encrypted.
        """
        self.patch(getpass, 'getpass', makeGetpass(''))
        filename = self.mktemp()
        FilePath(filename).setContent(privateRSA_openssh_encrypted)
        error = self.assertRaises(
            SystemExit, changePassPhrase, {'filename': filename})
        self.assertEqual(
            'Could not change passphrase: Passphrase must be provided '
            'for an encrypted key',
            str(error))
        self.assertEqual(privateRSA_openssh_encrypted,
                         FilePath(filename).getContent())


    def test_changePassphraseBadKey(self):
        """
        L{changePassPhrase} exits if the file specified points to an invalid
        key.
        """
        filename = self.mktemp()
        FilePath(filename).setContent('foobar')
        error = self.assertRaises(
            SystemExit, changePassPhrase, {'filename': filename})
        self.assertEqual(
            "Could not change passphrase: cannot guess the type of 'foobar'",
            str(error))
        self.assertEqual('foobar', FilePath(filename).getContent())


    def test_changePassphraseCreateError(self):
        """
        L{changePassPhrase} doesn't modify the key file if an unexpected error
        happens when trying to create the key with the new passphrase.
        """
        filename = self.mktemp()
        FilePath(filename).setContent(privateRSA_openssh)

        def toString(*args, **kwargs):
            raise RuntimeError('oops')

        self.patch(Key, 'toString', toString)

        error = self.assertRaises(
            SystemExit, changePassPhrase,
            {'filename': filename,
             'newpass': 'newencrypt'})

        self.assertEqual(
            'Could not change passphrase: oops', str(error))

        self.assertEqual(privateRSA_openssh, FilePath(filename).getContent())


    def test_changePassphraseEmptyStringError(self):
        """
        L{changePassPhrase} doesn't modify the key file if C{toString} returns
        an empty string.
        """
        filename = self.mktemp()
        FilePath(filename).setContent(privateRSA_openssh)

        def toString(*args, **kwargs):
            return ''

        self.patch(Key, 'toString', toString)

        error = self.assertRaises(
            SystemExit, changePassPhrase,
            {'filename': filename, 'newpass': 'newencrypt'})

        self.assertEqual(
            "Could not change passphrase: "
            "cannot guess the type of ''", str(error))

        self.assertEqual(privateRSA_openssh, FilePath(filename).getContent())


    def test_changePassphrasePublicKey(self):
        """
        L{changePassPhrase} exits when trying to change the passphrase on a
        public key, and doesn't change the file.
        """
        filename = self.mktemp()
        FilePath(filename).setContent(publicRSA_openssh)
        error = self.assertRaises(
            SystemExit, changePassPhrase,
            {'filename': filename, 'newpass': 'pass'})
        self.assertEqual(
            'Could not change passphrase: key not encrypted', str(error))
        self.assertEqual(publicRSA_openssh, FilePath(filename).getContent())
