#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Example demonstrating the Twisted Backup System.

This example shows how to:
1. Create a backup service
2. Backup network relay configurations
3. Restore backups
4. Export for iPhone
5. Manage backup lifecycle
"""

import json
import tempfile
from pathlib import Path

from twisted.backup.relay import NetworkRelayBackup


def main():
    """Demonstrate backup system functionality."""
    
    # Create a temporary directory for this example
    backup_dir = tempfile.mkdtemp(prefix="twisted_backup_example_")
    print(f"Using backup directory: {backup_dir}\n")
    
    # Initialize the backup service
    print("1. Initializing backup service...")
    relay_backup = NetworkRelayBackup(
        storage_path=backup_dir,
        cloudflare_domain="private.example.com"
    )
    print("   ✓ Backup service initialized\n")
    
    # Create a sample network relay configuration
    print("2. Creating sample relay configuration...")
    relay_config = {
        "relay_name": "primary_relay",
        "version": "1.0",
        "port": 8080,
        "encryption": "TLS",
        "connections": [
            {
                "id": 1,
                "host": "relay1.example.com",
                "port": 443,
                "status": "active"
            },
            {
                "id": 2,
                "host": "relay2.example.com",
                "port": 443,
                "status": "standby"
            }
        ],
        "routing": {
            "default": "relay1.example.com",
            "failover": "relay2.example.com",
            "load_balancing": "round-robin"
        }
    }
    print("   ✓ Configuration created\n")
    
    # Create a full backup
    print("3. Creating full backup...")
    backup_ids = relay_backup.create_full_backup(relay_config)
    print(f"   ✓ Backup created with IDs:")
    for backup_type, backup_id in backup_ids.items():
        print(f"     - {backup_type}: {backup_id}")
    print()
    
    # List all backups
    print("4. Listing all backups...")
    backups = relay_backup.list_backups()
    print(f"   ✓ Found {len(backups)} backup(s)\n")
    
    # Restore the configuration
    print("5. Restoring configuration...")
    restored_config = relay_backup.restore_relay_config(backup_ids["config"])
    if restored_config == relay_config:
        print("   ✓ Configuration restored successfully")
        print("   ✓ Integrity verified: Original and restored data match\n")
    
    # Export for iPhone
    print("6. Exporting backup for iPhone...")
    iphone_data = relay_backup.export_for_iphone(backup_ids["config"])
    if iphone_data:
        print("   ✓ iPhone export created:")
        print(f"     - Backup ID: {iphone_data['BackupID']}")
        print(f"     - Date: {iphone_data['BackupDate']}")
        print(f"     - Size: {iphone_data['DataSize']} bytes")
        print(f"     - Checksum: {iphone_data['DataChecksum'][:16]}...")
        print(f"     - Data encoding: base64 (safe for iPhone)")
    print()
    
    # Get backup statistics
    print("7. Backup statistics...")
    stats = relay_backup.get_backup_statistics()
    print(f"   ✓ Total backups: {stats['total_backups']}")
    print(f"   ✓ Total size: {stats['total_size']} bytes")
    print(f"   ✓ Encrypted size: {stats['total_encrypted_size']} bytes")
    print(f"   ✓ Compression ratio: {100 - (stats['total_encrypted_size'] / stats['total_size'] * 100):.1f}%")
    print(f"   ✓ By type: {stats['by_type']}\n")
    
    # Demonstrate key security
    print("8. Encryption key management...")
    key = relay_backup.storage.get_encryption_key()
    print(f"   ✓ Encryption key (base64): {key[:32]}... (truncated)")
    print("   ⚠ Store this key securely!")
    print("   ⚠ Without this key, backups cannot be restored!\n")
    
    # Cleanup old backups
    print("9. Cleanup demonstration...")
    # Create a few more backups
    for i in range(3):
        relay_backup.backup_relay_config({"test": i})
    
    print(f"   - Created 3 additional test backups")
    print(f"   - Total backups before cleanup: {len(relay_backup.list_backups())}")
    
    deleted = relay_backup.cleanup_old_backups(keep_count=3)
    print(f"   ✓ Deleted {len(deleted)} old backup(s)")
    print(f"   ✓ Remaining backups: {len(relay_backup.list_backups())}\n")
    
    print("=" * 60)
    print("Backup System Example Complete!")
    print("=" * 60)
    print(f"\nBackup directory: {backup_dir}")
    print("Note: This directory will be cleaned up automatically.")
    print("\nSecurity Features:")
    print("  ✓ AES-256-GCM encryption")
    print("  ✓ SHA-256 integrity verification")
    print("  ✓ Authenticated encryption (AEAD)")
    print("  ✓ Secure random nonce generation")
    print("  ✓ iPhone-compatible export format")
    
    # Cleanup
    import shutil
    shutil.rmtree(backup_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
