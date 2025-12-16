# Twisted Backup System

A secure, encrypted backup system for private server network relay data with support for Cloudflare private domain integration and iPhone-optimized data structures.

## Features

- **AES-256-GCM Encryption**: Military-grade encryption with authenticated encryption
- **Secure Storage**: Encrypted backup storage with integrity verification
- **Network Relay Backup**: Automated backup of network relay configurations and data
- **iPhone Compatibility**: Export backups in iPhone-compatible format
- **Cloudflare Integration**: Support for Cloudflare private domain data backup
- **Backup Management**: List, restore, and cleanup old backups

## Installation

The backup module requires the `cryptography` package, which is already included in Twisted's `conch` extra dependencies:

```bash
pip install twisted[conch]
```

## Quick Start

### Basic Encryption

```python
from twisted.backup.encryption import BackupEncryption

# Create encryption handler
encryption = BackupEncryption()

# Encrypt data
plaintext = b"sensitive data"
nonce, ciphertext = encryption.encrypt(plaintext)

# Decrypt data
decrypted = encryption.decrypt(nonce, ciphertext)
```

### Secure Storage

```python
from twisted.backup.storage import SecureStorage

# Initialize secure storage
storage = SecureStorage("/path/to/backups")

# Store encrypted backup
backup_id = "my_backup_001"
data = b"important data"
metadata = {"type": "config", "version": "1.0"}
storage.store_backup(backup_id, data, metadata)

# Retrieve backup
restored_data = storage.retrieve_backup(backup_id)

# List all backups
backups = storage.list_backups()
```

### Network Relay Backup

```python
from twisted.backup.relay import NetworkRelayBackup

# Initialize relay backup service
relay_backup = NetworkRelayBackup(
    storage_path="/path/to/backups",
    cloudflare_domain="private.example.com"
)

# Backup relay configuration
config = {
    "relay_name": "primary_relay",
    "port": 8080,
    "encryption": "TLS",
    "connections": [
        {"id": 1, "host": "host1.example.com"},
        {"id": 2, "host": "host2.example.com"}
    ],
    "routing": {
        "default": "host1.example.com",
        "failover": "host2.example.com"
    }
}

# Create full backup
backup_ids = relay_backup.create_full_backup(config)

# Restore configuration
restored_config = relay_backup.restore_relay_config(backup_ids["config"])

# Export for iPhone
iphone_data = relay_backup.export_for_iphone(backup_ids["config"])
```

## Security Features

### Encryption

The backup system uses AES-256-GCM (Galois/Counter Mode) which provides:

- **Confidentiality**: Data is encrypted and unreadable without the key
- **Authentication**: Tampering with encrypted data is detectable
- **Integrity**: Data corruption is automatically detected

### Key Management

```python
from twisted.backup.encryption import BackupEncryption

# Generate a new encryption key
key = BackupEncryption.generate_key()

# Save key securely (base64 encoded)
key_string = BackupEncryption.key_to_string(key)

# Restore key from string
restored_key = BackupEncryption.key_from_string(key_string)

# Use key with storage
storage = SecureStorage("/path/to/backups", key)
```

**Important**: Store your encryption keys securely! Loss of the encryption key means permanent loss of backup data.

### Integrity Verification

All backups include SHA-256 checksums that are automatically verified on retrieval:

```python
# Store backup (checksum calculated automatically)
storage.store_backup(backup_id, data)

# Retrieve backup (checksum verified automatically)
try:
    data = storage.retrieve_backup(backup_id)
except ValueError as e:
    print(f"Integrity check failed: {e}")
```

## Advanced Usage

### Backup Statistics

```python
stats = relay_backup.get_backup_statistics()
print(f"Total backups: {stats['total_backups']}")
print(f"Total size: {stats['total_size']} bytes")
print(f"Backups by type: {stats['by_type']}")
```

### Cleanup Old Backups

```python
# Keep only the 10 most recent backups
deleted = relay_backup.cleanup_old_backups(keep_count=10)
print(f"Deleted {len(deleted)} old backups")
```

### Filter Backups by Type

```python
# List only configuration backups
config_backups = relay_backup.list_backups("relay_config")

# List only network data backups
network_backups = relay_backup.list_backups("network")
```

### iPhone Export Format

The iPhone export format creates a property-list compatible dictionary:

```python
iphone_data = storage.export_to_iphone_format(backup_id)

# iPhone-compatible structure:
# {
#     "BackupID": "backup_id",
#     "BackupDate": "2025-12-16T06:00:00.000000",
#     "BackupData": "decoded_data",
#     "DataChecksum": "sha256_hash",
#     "DataSize": 1024,
#     "Metadata": {...}
# }
```

## Architecture

### Components

1. **BackupEncryption** (`twisted.backup.encryption`): Handles AES-256-GCM encryption and decryption
2. **SecureStorage** (`twisted.backup.storage`): Manages encrypted file storage with metadata
3. **NetworkRelayBackup** (`twisted.backup.relay`): Provides high-level backup operations for network relay data

### Storage Structure

```
/path/to/backups/
├── backup_index.json          # Index of all backups with metadata
├── backup_001.enc              # Encrypted backup file
├── backup_002.enc
└── backup_003.enc
```

### Backup Metadata

Each backup includes metadata:

```json
{
  "backup_id": "relay_config_1234567890_abcd1234",
  "timestamp": "2025-12-16T06:00:00.000000",
  "checksum": "sha256_hash",
  "size": 1024,
  "encrypted_size": 1088,
  "metadata": {
    "type": "relay_config",
    "domain": "private.example.com",
    "timestamp": "2025-12-16T06:00:00.000000"
  }
}
```

## Best Practices

1. **Key Management**: 
   - Store encryption keys separately from backups
   - Use secure key storage (e.g., environment variables, key management services)
   - Never commit keys to version control

2. **Regular Backups**:
   - Schedule regular backups of critical relay configurations
   - Test restore procedures periodically

3. **Cleanup**:
   - Implement retention policies to manage storage space
   - Keep multiple backup versions for disaster recovery

4. **Security**:
   - Use strong encryption keys (generated by `BackupEncryption.generate_key()`)
   - Protect backup storage directories with appropriate filesystem permissions
   - Monitor backup integrity regularly

## API Reference

See the module docstrings for detailed API documentation:

- `twisted.backup.encryption.BackupEncryption`
- `twisted.backup.storage.SecureStorage`
- `twisted.backup.relay.NetworkRelayBackup`

## Testing

Run the backup module tests:

```bash
python -m twisted.trial twisted.backup.test
```

## License

This module is part of Twisted and follows the same MIT license as the rest of Twisted Matrix Laboratories.
