# -*- test-case-name: twisted.backup.test.test_relay -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Network relay backup service for Cloudflare private domain data.

Provides automated backup of network relay data with encryption and secure storage.
"""

import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from twisted.internet import defer, protocol, reactor
from twisted.python import log
from twisted.web import client, http

from twisted.backup.encryption import BackupEncryption
from twisted.backup.storage import SecureStorage


class NetworkRelayBackup:
    """
    Manages backup of network relay data from Cloudflare private domains.
    
    Provides automated collection, encryption, and storage of network relay
    configurations and data with support for scheduled backups.
    """
    
    def __init__(
        self,
        storage_path: str,
        cloudflare_domain: Optional[str] = None,
        encryption_key: Optional[bytes] = None
    ):
        """
        Initialize network relay backup service.
        
        @param storage_path: Path for storing encrypted backups
        @param cloudflare_domain: Cloudflare domain to backup (optional)
        @param encryption_key: Encryption key for backups
        """
        self.storage = SecureStorage(storage_path, encryption_key)
        self.cloudflare_domain = cloudflare_domain
        self._backup_schedule = []
    
    def backup_relay_config(self, config_data: Dict[str, Any]) -> str:
        """
        Backup network relay configuration.
        
        @param config_data: Network relay configuration dictionary
        @return: Backup ID
        """
        # Use UUID to ensure uniqueness
        backup_id = f"relay_config_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Convert to JSON
        json_data = json.dumps(config_data, indent=2)
        
        # Store encrypted backup
        metadata = {
            "type": "relay_config",
            "domain": self.cloudflare_domain or "unknown",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.storage.store_backup(
            backup_id=backup_id,
            data=json_data.encode('utf-8'),
            metadata=metadata
        )
        
        log.msg(f"Backed up relay configuration: {backup_id}")
        return backup_id
    
    def backup_network_data(self, network_data: bytes, data_type: str = "network") -> str:
        """
        Backup network data.
        
        @param network_data: Raw network data to backup
        @param data_type: Type of network data
        @return: Backup ID
        """
        # Use UUID to ensure uniqueness
        backup_id = f"{data_type}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        metadata = {
            "type": data_type,
            "domain": self.cloudflare_domain or "unknown",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.storage.store_backup(
            backup_id=backup_id,
            data=network_data,
            metadata=metadata
        )
        
        log.msg(f"Backed up network data: {backup_id}")
        return backup_id
    
    def restore_backup(self, backup_id: str) -> Optional[bytes]:
        """
        Restore a backup.
        
        @param backup_id: Backup identifier
        @return: Decrypted backup data, or None if not found
        """
        data = self.storage.retrieve_backup(backup_id)
        if data:
            log.msg(f"Restored backup: {backup_id}")
        return data
    
    def restore_relay_config(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """
        Restore network relay configuration from backup.
        
        @param backup_id: Backup identifier
        @return: Configuration dictionary, or None if not found
        """
        data = self.restore_backup(backup_id)
        if data is None:
            return None
        
        try:
            config = json.loads(data.decode('utf-8'))
            return config
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            log.err(f"Failed to decode configuration: {e}")
            return None
    
    def list_backups(self, backup_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all backups, optionally filtered by type.
        
        @param backup_type: Optional type filter
        @return: List of backup records
        """
        all_backups = self.storage.list_backups()
        
        if backup_type is None:
            return all_backups
        
        return [
            b for b in all_backups
            if b.get("metadata", {}).get("type") == backup_type
        ]
    
    def create_full_backup(self, relay_config: Dict[str, Any]) -> Dict[str, str]:
        """
        Create a full backup including all relay data.
        
        @param relay_config: Complete relay configuration
        @return: Dictionary with backup IDs
        """
        backup_ids = {}
        
        # Backup main configuration
        backup_ids["config"] = self.backup_relay_config(relay_config)
        
        # If there's connection data, backup separately
        if "connections" in relay_config:
            connections_data = json.dumps(
                relay_config["connections"],
                indent=2
            ).encode('utf-8')
            backup_ids["connections"] = self.backup_network_data(
                connections_data,
                "connections"
            )
        
        # If there's routing data, backup separately
        if "routing" in relay_config:
            routing_data = json.dumps(
                relay_config["routing"],
                indent=2
            ).encode('utf-8')
            backup_ids["routing"] = self.backup_network_data(
                routing_data,
                "routing"
            )
        
        log.msg(f"Created full backup with IDs: {backup_ids}")
        return backup_ids
    
    def export_for_iphone(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """
        Export backup in iPhone-compatible format.
        
        @param backup_id: Backup identifier
        @return: iPhone-compatible data structure
        """
        return self.storage.export_to_iphone_format(backup_id)
    
    def get_backup_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored backups.
        
        @return: Statistics dictionary
        """
        backups = self.storage.list_backups()
        
        total_size = sum(b.get("size", 0) for b in backups)
        total_encrypted_size = sum(b.get("encrypted_size", 0) for b in backups)
        
        by_type = {}
        for backup in backups:
            backup_type = backup.get("metadata", {}).get("type", "unknown")
            by_type[backup_type] = by_type.get(backup_type, 0) + 1
        
        return {
            "total_backups": len(backups),
            "total_size": total_size,
            "total_encrypted_size": total_encrypted_size,
            "by_type": by_type,
            "storage_path": str(self.storage.storage_path)
        }
    
    def cleanup_old_backups(self, keep_count: int = 10) -> List[str]:
        """
        Remove old backups, keeping only the most recent ones.
        
        @param keep_count: Number of recent backups to keep
        @return: List of deleted backup IDs
        """
        backups = self.storage.list_backups()
        
        # Sort by timestamp (newest first)
        sorted_backups = sorted(
            backups,
            key=lambda b: b.get("timestamp", ""),
            reverse=True
        )
        
        deleted = []
        for backup in sorted_backups[keep_count:]:
            backup_id = backup["backup_id"]
            if self.storage.delete_backup(backup_id):
                deleted.append(backup_id)
                log.msg(f"Deleted old backup: {backup_id}")
        
        return deleted


class CloudflareRelayProtocol(protocol.Protocol):
    """
    Protocol for receiving data from Cloudflare relay endpoints.
    
    Collects data and triggers backup storage.
    """
    
    def __init__(self, backup_service: NetworkRelayBackup):
        """
        Initialize protocol.
        
        @param backup_service: Backup service to use for storing data
        """
        self.backup_service = backup_service
        self.received_data = []
    
    def dataReceived(self, data: bytes) -> None:
        """
        Called when data is received.
        
        @param data: Received data
        """
        self.received_data.append(data)
    
    def connectionLost(self, reason: Any = protocol.connectionDone) -> None:
        """
        Called when connection is closed.
        
        @param reason: Reason for connection closure
        """
        # Backup all received data
        if self.received_data:
            combined_data = b''.join(self.received_data)
            self.backup_service.backup_network_data(
                combined_data,
                "cloudflare_relay"
            )
