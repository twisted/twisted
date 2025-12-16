# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.backup.relay}.
"""

import json
import tempfile
import unittest

from twisted.backup.relay import NetworkRelayBackup


class NetworkRelayBackupTests(unittest.TestCase):
    """
    Tests for L{NetworkRelayBackup}.
    """
    
    def setUp(self):
        """
        Create a temporary storage for testing.
        """
        self.temp_dir = tempfile.mkdtemp()
        self.relay_backup = NetworkRelayBackup(
            storage_path=self.temp_dir,
            cloudflare_domain="private.example.com"
        )
    
    def tearDown(self):
        """
        Clean up temporary storage.
        """
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_backupRelayConfig(self):
        """
        Network relay configurations can be backed up.
        """
        config = {
            "relay_name": "primary_relay",
            "port": 8080,
            "encryption": "TLS"
        }
        
        backup_id = self.relay_backup.backup_relay_config(config)
        
        self.assertTrue(backup_id.startswith("relay_config_"))
    
    def test_restoreRelayConfig(self):
        """
        Backed up configurations can be restored.
        """
        original_config = {
            "relay_name": "test_relay",
            "connections": ["conn1", "conn2"]
        }
        
        backup_id = self.relay_backup.backup_relay_config(original_config)
        restored_config = self.relay_backup.restore_relay_config(backup_id)
        
        self.assertEqual(restored_config, original_config)
    
    def test_backupNetworkData(self):
        """
        Network data can be backed up.
        """
        network_data = b"network packet data"
        
        backup_id = self.relay_backup.backup_network_data(network_data, "packet")
        
        self.assertTrue(backup_id.startswith("packet_"))
    
    def test_restoreBackup(self):
        """
        Backed up data can be restored.
        """
        original_data = b"important network data"
        
        backup_id = self.relay_backup.backup_network_data(original_data)
        restored_data = self.relay_backup.restore_backup(backup_id)
        
        self.assertEqual(restored_data, original_data)
    
    def test_listBackups(self):
        """
        All backups can be listed.
        """
        self.relay_backup.backup_relay_config({"test": "config1"})
        self.relay_backup.backup_relay_config({"test": "config2"})
        
        backups = self.relay_backup.list_backups()
        
        self.assertEqual(len(backups), 2)
    
    def test_listBackupsByType(self):
        """
        Backups can be filtered by type.
        """
        self.relay_backup.backup_relay_config({"test": "config"})
        self.relay_backup.backup_network_data(b"data", "packet")
        
        config_backups = self.relay_backup.list_backups("relay_config")
        packet_backups = self.relay_backup.list_backups("packet")
        
        self.assertEqual(len(config_backups), 1)
        self.assertEqual(len(packet_backups), 1)
    
    def test_createFullBackup(self):
        """
        A full backup includes all relay components.
        """
        full_config = {
            "relay_name": "main_relay",
            "connections": [
                {"id": 1, "host": "host1.example.com"},
                {"id": 2, "host": "host2.example.com"}
            ],
            "routing": {
                "default": "host1.example.com",
                "failover": "host2.example.com"
            }
        }
        
        backup_ids = self.relay_backup.create_full_backup(full_config)
        
        self.assertIn("config", backup_ids)
        self.assertIn("connections", backup_ids)
        self.assertIn("routing", backup_ids)
    
    def test_exportForIphone(self):
        """
        Backups can be exported in iPhone format.
        """
        config = {"device": "iPhone", "version": "1.0"}
        backup_id = self.relay_backup.backup_relay_config(config)
        
        iphone_data = self.relay_backup.export_for_iphone(backup_id)
        
        self.assertIsNotNone(iphone_data)
        self.assertEqual(iphone_data["BackupID"], backup_id)
        self.assertIn("BackupDate", iphone_data)
    
    def test_getBackupStatistics(self):
        """
        Backup statistics can be retrieved.
        """
        self.relay_backup.backup_relay_config({"test": "config"})
        self.relay_backup.backup_network_data(b"data")
        
        stats = self.relay_backup.get_backup_statistics()
        
        self.assertEqual(stats["total_backups"], 2)
        self.assertIn("total_size", stats)
        self.assertIn("by_type", stats)
    
    def test_cleanupOldBackups(self):
        """
        Old backups can be cleaned up.
        """
        import time
        # Create multiple backups with slight delays to ensure different timestamps
        for i in range(5):
            self.relay_backup.backup_relay_config({"index": i})
            time.sleep(0.01)  # Small delay to ensure different timestamps
        
        # Keep only 3 most recent
        deleted = self.relay_backup.cleanup_old_backups(keep_count=3)
        
        # At least some backups should be deleted
        self.assertGreaterEqual(len(deleted), 1)
        
        # Verify only 3 remain
        remaining = self.relay_backup.list_backups()
        self.assertEqual(len(remaining), 3)
    
    def test_restoreNonExistentBackup(self):
        """
        Restoring non-existent backup returns None.
        """
        result = self.relay_backup.restore_backup("nonexistent_id")
        self.assertIsNone(result)
    
    def test_restoreNonExistentConfig(self):
        """
        Restoring non-existent config returns None.
        """
        result = self.relay_backup.restore_relay_config("nonexistent_id")
        self.assertIsNone(result)
