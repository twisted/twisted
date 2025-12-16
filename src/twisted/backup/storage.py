# -*- test-case-name: twisted.backup.test.test_storage -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Secure storage backend for encrypted backups.

Provides filesystem-based secure storage with encryption and integrity verification.
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from twisted.backup.encryption import BackupEncryption


class SecureStorage:
    """
    Manages encrypted backup storage on the filesystem.
    
    Stores encrypted backups with metadata and provides retrieval
    with integrity verification. Optimized for iPhone data structures.
    """
    
    def __init__(self, storage_path: str, encryption_key: bytes = None):
        """
        Initialize secure storage.
        
        @param storage_path: Directory path for storing backups
        @param encryption_key: Encryption key for backups. If None, generates new key.
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.encryption = BackupEncryption(encryption_key)
        self._index_file = self.storage_path / "backup_index.json"
        self._load_index()
    
    def _load_index(self) -> None:
        """Load backup index from disk."""
        if self._index_file.exists():
            with open(self._index_file, 'r') as f:
                self._index = json.load(f)
        else:
            self._index = {"backups": []}
    
    def _save_index(self) -> None:
        """Save backup index to disk."""
        with open(self._index_file, 'w') as f:
            json.dump(self._index, f, indent=2)
    
    def store_backup(
        self,
        backup_id: str,
        data: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store encrypted backup data.
        
        @param backup_id: Unique identifier for the backup
        @param data: Raw backup data to encrypt and store
        @param metadata: Optional metadata about the backup
        @return: Backup record with storage information
        """
        # Calculate checksum of original data
        checksum = hashlib.sha256(data).hexdigest()
        
        # Encrypt the data
        encrypted_data = self.encryption.encrypt_to_string(data)
        
        # Create backup record
        timestamp = datetime.utcnow().isoformat()
        record = {
            "backup_id": backup_id,
            "timestamp": timestamp,
            "checksum": checksum,
            "size": len(data),
            "encrypted_size": len(encrypted_data),
            "metadata": metadata or {}
        }
        
        # Store encrypted data
        backup_file = self.storage_path / f"{backup_id}.enc"
        with open(backup_file, 'w') as f:
            f.write(encrypted_data)
        
        # Update index
        self._index["backups"].append(record)
        self._save_index()
        
        return record
    
    def retrieve_backup(self, backup_id: str) -> Optional[bytes]:
        """
        Retrieve and decrypt backup data.
        
        @param backup_id: Backup identifier
        @return: Decrypted backup data, or None if not found
        @raises: ValueError if integrity check fails
        """
        backup_file = self.storage_path / f"{backup_id}.enc"
        
        if not backup_file.exists():
            return None
        
        # Find backup record
        record = None
        for backup in self._index["backups"]:
            if backup["backup_id"] == backup_id:
                record = backup
                break
        
        if record is None:
            return None
        
        # Read and decrypt
        with open(backup_file, 'r') as f:
            encrypted_data = f.read()
        
        data = self.encryption.decrypt_from_string(encrypted_data)
        
        # Verify integrity
        checksum = hashlib.sha256(data).hexdigest()
        if checksum != record["checksum"]:
            raise ValueError(f"Integrity check failed for backup {backup_id}")
        
        return data
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List all stored backups.
        
        @return: List of backup records
        """
        return self._index["backups"]
    
    def delete_backup(self, backup_id: str) -> bool:
        """
        Delete a backup.
        
        @param backup_id: Backup identifier
        @return: True if deleted, False if not found
        """
        backup_file = self.storage_path / f"{backup_id}.enc"
        
        if not backup_file.exists():
            return False
        
        # Remove from index
        self._index["backups"] = [
            b for b in self._index["backups"]
            if b["backup_id"] != backup_id
        ]
        self._save_index()
        
        # Delete file
        backup_file.unlink()
        return True
    
    def get_encryption_key(self) -> str:
        """
        Get the encryption key as a base64 string.
        
        @return: Base64-encoded encryption key
        """
        return BackupEncryption.key_to_string(self.encryption.key)
    
    def export_to_iphone_format(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """
        Export backup in iPhone-compatible format (property list compatible).
        
        @param backup_id: Backup identifier
        @return: Dictionary in iPhone-compatible format, or None if not found
        """
        data = self.retrieve_backup(backup_id)
        if data is None:
            return None
        
        # Find backup record
        record = None
        for backup in self._index["backups"]:
            if backup["backup_id"] == backup_id:
                record = backup
                break
        
        # Create iPhone-compatible structure
        iphone_data = {
            "BackupID": backup_id,
            "BackupDate": record["timestamp"],
            "BackupData": data.decode('utf-8', errors='replace'),
            "DataChecksum": record["checksum"],
            "DataSize": record["size"],
            "Metadata": record["metadata"]
        }
        
        return iphone_data
