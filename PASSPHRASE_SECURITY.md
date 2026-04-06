# Passphrase-Based Key Derivation Security Feature

## Feature Overview

**Feature Name:** Passphrase-Based Key Derivation

**Version:** 1.1.0

**Status:** Production Ready

---

## Description

The Secure Journal now supports **passphrase-based key derivation**, a significant security enhancement that replaces hardcoded encryption keys with keys derived from a user-provided passphrase. This feature provides two critical security benefits:

1. **User-Controlled Protection**: Each journal is protected by a unique user passphrase
2. **PBKDF2 Encryption**: Keys are derived using PBKDF2-HMAC-SHA256 with 100,000 iterations and 32-byte cryptographic salt

---

## Purpose

### Problem Solved
Previously, the journal used **hardcoded encryption keys** (`PLAYFAIR_KEY="SECRET"` and `XOR_KEY="SUPERSECRETKEY"`). This approach had a critical limitation:
- Anyone with access to the source code could decrypt all journals
- All journals used identical encryption keys
- No way to revoke or change encryption keys without recompiling

### Security Improvement
The passphrase-based approach provides:
- **Per-Journal Protection**: Each journal has a unique salt and verification token
- **User Ownership**: Only users with the correct passphrase can unlock their journal
- **Strong Derivation**: PBKDF2 with 100,000 iterations resists brute-force attacks
- **Runtime Derivation**: Keys are derived at startup, never hardcoded
- **Verification Tokens**: HMAC-based tokens verify passphrase correctness before decryption

---

## Technical Implementation

### 1. Key Derivation Algorithm

```python
Master Key = PBKDF2-HMAC-SHA256(
    passphrase,
    salt,
    iterations=100000,
    hash_length=32
)

Playfair Key = SHA256(Master Key || b"playfair")[:26]
XOR Key      = SHA256(Master Key || b"xor_cipher")[:30]
Verification = HMAC-SHA256(Master Key, "SECURE_JOURNAL_VERIFICATION")
```

**Parameters:**
- **Salt**: 32 random bytes (256 bits) generated per journal
- **Iterations**: 100,000 (OWASP recommended for 2024)
- **Minimum Passphrase**: 6 characters
- **Derivation**: SHA256-based domain separation for distinct keys

### 2. Storage Format

Journals are now stored with metadata:

```json
{
  "version": "1.1",
  "salt": "hex_encoded_32_bytes",
  "verification": "hmac_verification_token",
  "entries": [
    {
      "id": "entry_id",
      "title": "encrypted_playfair_text",
      "tags": "encrypted_playfair_text",
      "mood": "encrypted_playfair_text",
      "content": "hex_encoded_xor_encrypted_text",
      "created_at": "ISO_timestamp",
      "updated_at": "ISO_timestamp"
    }
  ]
}
```

**Key Points:**
- Salt and verification are **unencrypted** (necessary for initial passphrase verification)
- Verification token allows the app to confirm passphrase correctness without decrypting data
- Version marker enables future schema migrations

### 3. Startup Workflow

```
1. Load journal_data.json
2. Check if salt and verification exist
   ├─ Yes: Existing protected journal
   │  ├─ Prompt for passphrase
   │  ├─ Verify passphrase using HMAC token
   │  ├─ Derive keys from passphrase
   │  └─ Decrypt and load entries
   └─ No: New journal or legacy journal
      ├─ Offer passphrase setup
      ├─ Generate salt
      ├─ Derive keys
      └─ Optionally re-encrypt legacy entries
```

### 4. Backward Compatibility

The app gracefully handles three scenarios:

1. **New Empty Journal**: Offers passphrase setup dialog
2. **Existing Legacy Journal** (hardcoded keys): Offers to upgrade with passphrase protection
3. **Protected Journal Backup**: Restores with passphrase verification

---

## User Experience

### First Run: Setting Up a New Journal

1. App launches and detects no data
2. Dialog: "Set up passphrase protection for your journal?"
   - **Yes** → Prompts for passphrase (min 6 chars) → Saves with protection
   - **No** → Uses hardcoded keys (not recommended)

### Existing Journal: Upgrading to Passphrase Protection

1. App detects legacy data (no salt/verification)
2. Dialog: "Your journal appears to be using legacy encryption. Upgrade to passphrase protection?"
   - **Yes** → Prompts for passphrase → Re-encrypts all entries with derived keys
   - **No** → Continues with hardcoded keys

### Locked Journal: Entering Passphrase

1. App loads and detects salt/verification
2. Dialog: "Enter your journal passphrase:"
3. User enters passphrase
4. App verifies using HMAC token
   - **Correct**: Derives keys and loads all entries
   - **Incorrect**: Shows error and exits (data protected)

---

## Security Considerations

### Strengths

✅ **PBKDF2-HMAC-SHA256**: Industry-standard key derivation function  
✅ **100,000 Iterations**: OWASP-recommended for resisting brute-force attacks  
✅ **Unique Salt**: 32 random bytes per journal prevent rainbow table attacks  
✅ **Verification Tokens**: HMAC prevents passphrase guessing without full decryption  
✅ **Domain Separation**: Different keys for Playfair and XOR prevent key reuse attacks  
✅ **Atomic Saves**: Temporary file + atomic replace prevents corruption  
✅ **Encryption Verification**: Round-trip tests confirm data integrity  

### Limitations

⚠️ **Passphrase Strength**: Security depends on passphrase complexity (minimum 6 chars recommended but not enforced)  
⚠️ **No Key Rotation**: Changing passphrase requires re-encrypting all entries (future enhancement)  
⚠️ **Local Storage Only**: No cloud backup; loss of `journal_data.json` means permanent data loss  
⚠️ **Backup Files**: Backup (`.bak`) uses same encryption; both files must be protected  
⚠️ **No Timeout Lock**: Once unlocked, journal remains unlocked until app closes  

---

## Code Changes

### New Functions

| Function | Purpose |
|----------|---------|
| `generate_salt()` | Creates 32 random bytes for PBKDF2 |
| `derive_keys_from_passphrase()` | PBKDF2 key derivation with 100k iterations |
| `verify_passphrase()` | Validates passphrase using HMAC token |
| `set_global_keys()` | Sets global encryption keys at runtime |
| `get_playfair_key()` | Returns derived or fallback Playfair key |
| `get_xor_key()` | Returns derived or fallback XOR key |

### Modified Functions

| Function | Changes |
|----------|---------|
| `_transform_playfair_text()` | Uses `get_playfair_key()` instead of hardcoded key |
| `xor_encrypt_hex()` | Uses `get_xor_key()` instead of hardcoded key |
| `xor_decrypt_hex()` | Uses `get_xor_key()` instead of hardcoded key |
| `load_records_detailed()` | Returns salt and verification metadata |
| `save_records()` | Saves salt and verification with entries |
| `JournalApp.__init__()` | Calls `_initialize_passphrase_and_records()` |

### New Methods

| Method | Purpose |
|--------|---------|
| `_initialize_passphrase_and_records()` | Main startup workflow |
| `_prompt_for_passphrase()` | Custom dialog for passphrase entry |
| `_setup_new_journal_with_passphrase()` | Initial setup for new journals |
| `_setup_passphrase_for_existing_journal()` | Upgrade legacy journals |

---

## Testing Recommendations

### Unit Tests

```python
# Test key derivation consistency
assert derive_keys_from_passphrase("test", salt1) == derive_keys_from_passphrase("test", salt1)

# Test password verification
_, _, token = derive_keys_from_passphrase("test", salt)
assert verify_passphrase("test", salt, token) == True
assert verify_passphrase("wrong", salt, token) == False

# Test different salts produce different keys
keys1 = derive_keys_from_passphrase("test", salt1)
keys2 = derive_keys_from_passphrase("test", salt2)
assert keys1 != keys2
```

### Integration Tests

1. **New Journal Setup**: Start fresh → setup passphrase → create entry → quit → restart → verify passphrase prompt shows
2. **Entry Encryption**: Create entry with derived keys → verify encrypted correctly → restart → verify decryption works
3. **Upgrade Path**: Create journal with hardcoded keys → restart → upgrade dialog → setup passphrase → verify re-encryption
4. **Wrong Password**: Restart with saved journal → enter wrong passphrase → verify error and no data loaded
5. **Backup Recovery**: Delete journal → restore from backup → enter passphrase → verify recovery works

---

## Migration Guide

### For Existing Users

1. **No Action Required** if you don't want passphrase protection
   - App continues to use hardcoded keys
   - App works exactly as before

2. **To Enable Passphrase Protection**
   - Start app normally
   - Dialog appears: "Upgrade to passphrase protection?"
   - Select Yes
   - Enter desired passphrase (6+ characters recommended)
   - App re-encrypts all entries with derived keys
   - All future entries use passphrase protection

### For New Users

1. Start app
2. Dialog appears: "Set up passphrase protection?"
3. Select Yes
4. Enter desired passphrase
5. Start journaling with full protection

---

## Future Enhancements

### Proposed Security Features

1. **Passphrase Change**: Ability to change passphrase and re-encrypt all entries
2. **Per-Entry Locking**: Individual entries could have separate unlocking with timeout
3. **Key Rotation**: Periodic re-encryption with new keys to limit damage if salt is compromised
4. **Biometric Unlock** (Optional): Touch ID / Windows Hello for passphrase storage locally
5. **Multi-Factor Unlock**: Passphrase + security questions for account recovery

### Related Features

1. **Full-Text Search**: Search within encrypted content (requires decryption each search)
2. **Export/Import**: Backup and restore encrypted journals with or without passphrase
3. **Auto-Lock Timer**: Lock journal after N minutes of inactivity
4. **Session Management**: Support multiple user profiles with unique passphrases

---

## Configuration

```python
# Tunable Parameters (in secure_journal_app.py)

PBKDF2_ITERATIONS = 100000      # OWASP 2024 recommendation
SALT_SIZE = 32                   # 256-bit salt
VERIFICATION_TOKEN = "SECURE_JOURNAL_VERIFICATION"  # Domain separation
```

**Recommendations:**
- Keep `PBKDF2_ITERATIONS ≥ 100000` for security
- Keep `SALT_SIZE = 32` (256 bits standard)
- Change `VERIFICATION_TOKEN` only if using custom builds

---

## Compliance & Security Standards

✅ **NIST SP 800-132**: PBKDF2 recommended for password-based key derivation  
✅ **OWASP 2024**: 100,000+ iterations for non-interactive use  
✅ **RFC 2898**: PBKDF2-HMAC-SHA256 specification compliance  
✅ **CWE-916**: Use of Predictable Seed in Pseudo-Random Number Generator (mitigated by cryptographic salt)  

---

## Support & Documentation

For questions about this feature:
- See `README.md` for general setup
- Check `secure_journal_app.py` inline comments for implementation details
- Review this file for architectural decisions

---

## Version History

**v1.1.0** (Current)
- Initial passphrase-based key derivation implementation
- PBKDF2-HMAC-SHA256 with 100,000 iterations
- Backward compatible with hardcoded key journals
- Upgrade path for existing journals

---

**Last Updated:** April 6, 2026  
**Maintainer:** Project_Info Team  
**License:** MIT
