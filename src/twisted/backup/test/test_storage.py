# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.backup.storage}.
"""

import json
import tempfile
import unittest
from pathlib import Path

from twisted.backup.encryption import BackupEncryption
from twisted.backup.storage import SecureStorage


class SecureStorageTests(unittest.TestCase):
    """
    Tests for L{SecureStorage}.
    """
    
    def setUp(self):
        """
        Create a temporary storage directory for testing.
        """
        self.temp_dir = tempfile.mkdtemp()
        self.key = BackupEncryption.generate_key()
        self.storage = SecureStorage(self.temp_dir, self.key)
    
    def tearDown(self):
        """
        Clean up temporary storage.
        """
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initCreatesDirectory(self):
        """
        L{SecureStorage} creates storage directory if it doesn't exist.
        """
        new_dir = Path(self.temp_dir) / "new_storage"
        storage = SecureStorage(str(new_dir), self.key)
        self.assertTrue(new_dir.exists())
    
    def test_storeBackup(self):
        """
        Backups can be stored successfully.
        """
        data = b"test backup data"
        backup_id = "test_backup_001"
        
        record = self.storage.store_backup(backup_id, data)
        
        self.assertEqual(record["backup_id"], backup_id)
        self.assertEqual(record["size"], len(data))
        self.assertIn("checksum", record)
        self.assertIn("timestamp", record)
    
    def test_storeAndRetrieveBackup(self):
        """
        Stored backups can be retrieved and decrypted.
        """
        original_data = b"important backup data"
        backup_id = "test_backup_002"
        
        self.storage.store_backup(backup_id, original_data)
        retrieved_data = self.storage.retrieve_backup(backup_id)
        
        self.assertEqual(retrieved_data, original_data)
    
    def test_retrieveNonExistentBackup(self):
        """
        Retrieving non-existent backup returns None.
        """
        result = self.storage.retrieve_backup("nonexistent")
        self.assertIsNone(result)
    
    def test_listBackups(self):
        """
        L{SecureStorage.list_backups} returns all stored backups.
        """
        self.storage.store_backup("backup_1", b"data 1")
        self.storage.store_backup("backup_2", b"data 2")
        
        backups = self.storage.list_backups()
        
        self.assertEqual(len(backups), 2)
        backup_ids = [b["backup_id"] for b in backups]
        self.assertIn("backup_1", backup_ids)
        self.assertIn("backup_2", backup_ids)
    
    def test_deleteBackup(self):
        """
        Backups can be deleted.
        """
        backup_id = "backup_to_delete"
        self.storage.store_backup(backup_id, b"data")
        
        result = self.storage.delete_backup(backup_id)
        self.assertTrue(result)
        
        # Verify it's gone
        retrieved = self.storage.retrieve_backup(backup_id)
        self.assertIsNone(retrieved)
    
    def test_deleteNonExistentBackup(self):
        """
        Deleting non-existent backup returns False.
        """
        result = self.storage.delete_backup("nonexistent")
        self.assertFalse(result)
    
    def test_storeWithMetadata(self):
        """
        Backups can be stored with metadata.
        """
        data = b"data"
        backup_id = "backup_with_meta"
        metadata = {"type": "config", "version": "1.0"}
        
        record = self.storage.store_backup(backup_id, data, metadata)
        
        self.assertEqual(record["metadata"], metadata)
    
    def test_integrityVerification(self):
        """
        Integrity verification catches corrupted data.
        """
        backup_id = "integrity_test"
        self.storage.store_backup(backup_id, b"original data")
        
        # Corrupt the encrypted file
        backup_file = Path(self.temp_dir) / f"{backup_id}.enc"
        with open(backup_file, 'w') as f:
            f.write("corrupted_data")
        
        # Should raise error on retrieval
        with self.assertRaises(Exception):
            self.storage.retrieve_backup(backup_id)
    
    def test_getEncryptionKey(self):
        """
        L{SecureStorage.get_encryption_key} returns base64-encoded key.
        """
        key_string = self.storage.get_encryption_key()
        self.assertIsInstance(key_string, str)
        
        # Should be able to reconstruct the key
        restored_key = BackupEncryption.key_from_string(key_string)
        self.assertEqual(restored_key, self.key)
    
    def test_exportToIphoneFormat(self):
        """
        L{SecureStorage.export_to_iphone_format} creates iPhone-compatible data.
        """
        backup_id = "iphone_backup"
        data = b"test data for iPhone"
        metadata = {"device": "iPhone", "version": "iOS 17"}
        
        self.storage.store_backup(backup_id, data, metadata)
        iphone_data = self.storage.export_to_iphone_format(backup_id)
        
        self.assertIsNotNone(iphone_data)
        self.assertEqual(iphone_data["BackupID"], backup_id)
        self.assertIn("BackupDate", iphone_data)
        self.assertIn("DataChecksum", iphone_data)
        self.assertEqual(iphone_data["Metadata"], metadata)
    
    def test_differentKeysCannotDecrypt(self):
        """
        Data encrypted with one key cannot be decrypted with another.
        """
        backup_id = "key_test"
        data = b"secret data"
        
        # Store with first key
        self.storage.store_backup(backup_id, data)
        
        # Try to retrieve with different key
        different_key = BackupEncryption.generate_key()
        storage2 = SecureStorage(self.temp_dir, different_key)
        
        with self.assertRaises(Exception):
            storage2.retrieve_backup(backup_id)
