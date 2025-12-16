# -*- test-case-name: twisted.backup.test.test_encryption -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Encryption utilities for secure backup storage.

Provides AES-256-GCM encryption for backup data with secure key management.
"""

import base64
import os
from typing import Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class BackupEncryption:
    """
    Handles encryption and decryption of backup data using AES-256-GCM.
    
    This provides authenticated encryption with additional data (AEAD) ensuring
    both confidentiality and integrity of backup data.
    """
    
    def __init__(self, key: bytes = None):
        """
        Initialize encryption handler.
        
        @param key: 32-byte encryption key. If None, generates a new key.
        """
        if key is None:
            key = AESGCM.generate_key(bit_length=256)
        elif len(key) != 32:
            raise ValueError("Encryption key must be 32 bytes for AES-256")
        
        self._aesgcm = AESGCM(key)
        self._key = key
    
    @property
    def key(self) -> bytes:
        """
        Get the encryption key.
        
        @return: The 32-byte encryption key
        """
        return self._key
    
    def encrypt(self, plaintext: bytes, associated_data: bytes = None) -> Tuple[bytes, bytes]:
        """
        Encrypt data with AES-256-GCM.
        
        @param plaintext: Data to encrypt
        @param associated_data: Optional additional authenticated data
        @return: Tuple of (nonce, ciphertext)
        """
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, associated_data)
        return nonce, ciphertext
    
    def decrypt(self, nonce: bytes, ciphertext: bytes, associated_data: bytes = None) -> bytes:
        """
        Decrypt data with AES-256-GCM.
        
        @param nonce: The nonce used during encryption
        @param ciphertext: Encrypted data
        @param associated_data: Optional additional authenticated data
        @return: Decrypted plaintext
        @raises: cryptography.exceptions.InvalidTag if authentication fails
        """
        return self._aesgcm.decrypt(nonce, ciphertext, associated_data)
    
    def encrypt_to_string(self, plaintext: bytes, associated_data: bytes = None) -> str:
        """
        Encrypt data and return base64-encoded string.
        
        @param plaintext: Data to encrypt
        @param associated_data: Optional additional authenticated data
        @return: Base64-encoded string containing nonce and ciphertext
        """
        nonce, ciphertext = self.encrypt(plaintext, associated_data)
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode('ascii')
    
    def decrypt_from_string(self, encrypted_string: str, associated_data: bytes = None) -> bytes:
        """
        Decrypt data from base64-encoded string.
        
        @param encrypted_string: Base64-encoded encrypted data
        @param associated_data: Optional additional authenticated data
        @return: Decrypted plaintext
        """
        combined = base64.b64decode(encrypted_string)
        nonce = combined[:12]
        ciphertext = combined[12:]
        return self.decrypt(nonce, ciphertext, associated_data)
    
    @staticmethod
    def generate_key() -> bytes:
        """
        Generate a new random 256-bit encryption key.
        
        @return: 32-byte encryption key
        """
        return AESGCM.generate_key(bit_length=256)
    
    @staticmethod
    def key_to_string(key: bytes) -> str:
        """
        Convert encryption key to base64 string for storage.
        
        @param key: Encryption key
        @return: Base64-encoded key
        """
        return base64.b64encode(key).decode('ascii')
    
    @staticmethod
    def key_from_string(key_string: str) -> bytes:
        """
        Convert base64 string to encryption key.
        
        @param key_string: Base64-encoded key
        @return: Encryption key bytes
        """
        return base64.b64decode(key_string)
