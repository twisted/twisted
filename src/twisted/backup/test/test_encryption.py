# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.backup.encryption}.
"""

import unittest

from cryptography.exceptions import InvalidTag

from twisted.backup.encryption import BackupEncryption


class BackupEncryptionTests(unittest.TestCase):
    """
    Tests for L{BackupEncryption}.
    """
    
    def test_generateKey(self):
        """
        L{BackupEncryption.generate_key} generates a 32-byte key.
        """
        key = BackupEncryption.generate_key()
        self.assertEqual(len(key), 32)
    
    def test_initWithoutKey(self):
        """
        L{BackupEncryption} can be initialized without a key.
        """
        encryption = BackupEncryption()
        self.assertIsNotNone(encryption.key)
        self.assertEqual(len(encryption.key), 32)
    
    def test_initWithKey(self):
        """
        L{BackupEncryption} can be initialized with a provided key.
        """
        key = BackupEncryption.generate_key()
        encryption = BackupEncryption(key)
        self.assertEqual(encryption.key, key)
    
    def test_initWithInvalidKey(self):
        """
        L{BackupEncryption} raises ValueError for invalid key length.
        """
        with self.assertRaises(ValueError):
            BackupEncryption(b"short_key")
    
    def test_encryptDecrypt(self):
        """
        Data can be encrypted and decrypted successfully.
        """
        encryption = BackupEncryption()
        plaintext = b"sensitive backup data"
        
        nonce, ciphertext = encryption.encrypt(plaintext)
        
        # Nonce should be 12 bytes
        self.assertEqual(len(nonce), 12)
        
        # Ciphertext should be different from plaintext
        self.assertNotEqual(ciphertext, plaintext)
        
        # Decrypt and verify
        decrypted = encryption.decrypt(nonce, ciphertext)
        self.assertEqual(decrypted, plaintext)
    
    def test_encryptWithAssociatedData(self):
        """
        Encryption with associated data provides authentication.
        """
        encryption = BackupEncryption()
        plaintext = b"backup data"
        associated = b"metadata"
        
        nonce, ciphertext = encryption.encrypt(plaintext, associated)
        decrypted = encryption.decrypt(nonce, ciphertext, associated)
        
        self.assertEqual(decrypted, plaintext)
    
    def test_decryptWithWrongAssociatedData(self):
        """
        Decryption with wrong associated data fails authentication.
        """
        encryption = BackupEncryption()
        plaintext = b"backup data"
        associated = b"metadata"
        
        nonce, ciphertext = encryption.encrypt(plaintext, associated)
        
        # Try to decrypt with different associated data
        with self.assertRaises(InvalidTag):
            encryption.decrypt(nonce, ciphertext, b"wrong_metadata")
    
    def test_encryptToString(self):
        """
        L{BackupEncryption.encrypt_to_string} returns base64 string.
        """
        encryption = BackupEncryption()
        plaintext = b"test data"
        
        encrypted_string = encryption.encrypt_to_string(plaintext)
        
        # Should be a string
        self.assertIsInstance(encrypted_string, str)
        
        # Should be decodable
        decrypted = encryption.decrypt_from_string(encrypted_string)
        self.assertEqual(decrypted, plaintext)
    
    def test_keyToString(self):
        """
        Keys can be converted to and from base64 strings.
        """
        original_key = BackupEncryption.generate_key()
        key_string = BackupEncryption.key_to_string(original_key)
        
        self.assertIsInstance(key_string, str)
        
        restored_key = BackupEncryption.key_from_string(key_string)
        self.assertEqual(restored_key, original_key)
    
    def test_differentKeysProduceDifferentResults(self):
        """
        Different encryption keys produce different ciphertexts.
        """
        plaintext = b"test data"
        
        enc1 = BackupEncryption()
        enc2 = BackupEncryption()
        
        encrypted1 = enc1.encrypt_to_string(plaintext)
        encrypted2 = enc2.encrypt_to_string(plaintext)
        
        # Different keys should produce different ciphertexts
        self.assertNotEqual(encrypted1, encrypted2)
        
        # Each should decrypt with its own key
        self.assertEqual(enc1.decrypt_from_string(encrypted1), plaintext)
        self.assertEqual(enc2.decrypt_from_string(encrypted2), plaintext)
