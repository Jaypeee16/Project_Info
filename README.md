# Secure Journal Application

A local desktop journal app built with Python + customtkinter.

## Features

- Dark, minimal desktop UI.
- **Passphrase-based key derivation** (v1.1.0): PBKDF2-HMAC-SHA256 with 100,000 iterations.
- Playfair encryption for title, tags, mood.
- XOR + hexadecimal encryption for main journal content.
- Local JSON storage with encrypted fields only.
- Atomic save writes plus rolling backup restore.
- Automatic upgrade path from legacy hardcoded-key journals.

## Version

**v1.1.0** - Passphrase-Based Key Derivation Release

## Run Locally (Dev)

1. Create and activate a virtual environment.
2. Install runtime dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Start the app:

```powershell
python secure_journal_app.py
```

## Data Files

- Primary data store: `journal_data.json`
- Backup file: `journal_data.json.bak`

Both files are created in the same folder as the script/executable.

## Package for Windows (.exe)

Use the included build script:

```powershell
.\build_windows.ps1
```

If PowerShell blocks script execution, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```

One-file executable build:

```powershell
.\build_windows.ps1 -OneFile
```

Build output:

- Default: `dist\SecureJournal\`
- One-file: `dist\SecureJournal.exe`

Executable metadata and branding:

- App icon: `assets/secure_journal.ico`
- Version metadata: `version_info.txt`

## Security

### Passphrase Protection (v1.1.0+)

The journal now uses **passphrase-based key derivation**:

- **PBKDF2-HMAC-SHA256**: Industry-standard key derivation with 100,000 iterations
- **Per-Journal Salt**: Unique 32-byte cryptographic salt prevents rainbow table attacks
- **Verification Tokens**: HMAC-based verification ensures correct passphrase before decryption
- **Automatic Upgrade**: Legacy journals can optionally upgrade to passphrase protection

**First Launch:**
- New journals: Offered option to set up passphrase protection
- Existing journals: Offered option to upgrade from hardcoded keys to passphrase keys
- Current behavior: Uses passphrase-derived keys if salt/verification exist; falls back to hardcoded keys otherwise

**Minimum Passphrase:** 6 characters (recommended: 12+ characters with mixed case/numbers/symbols)

For detailed security architecture, see [PASSPHRASE_SECURITY.md](PASSPHRASE_SECURITY.md).

### Encryption Methods

- **Title, Tags, Mood**: Playfair cipher (classical block cipher)
- **Content**: XOR cipher + hex encoding (symmetric stream cipher)
- **Storage**: JSON format with encrypted fields only; unencrypted salt/verification metadata

All encryption keys are derived from user passphrase at runtime (never hardcoded in protected journals).

### Notes

- Classical Playfair behavior merges `J` with `I`.
- No encryption/decryption performance penalty; key derivation happens once at startup.

## Release Checklist

1. Run local app and verify create/edit/save/delete flow works.
2. Test passphrase setup on first launch (new journal scenario).
3. Verify encryption with derived keys: create entry → quit → restart → enter passphrase → verify decryption.
4. Test upgrade path: delete salt/verification from existing journal → restart → verify upgrade prompt → set passphrase.
5. Confirm encrypted storage in `journal_data.json` with salt/verification metadata.
6. Verify backup behavior with `journal_data.json.bak`.
7. Build package using `./build_windows.ps1` (or `-OneFile` variant).
8. Launch `dist\SecureJournal\SecureJournal.exe` (or one-file exe) and smoke test passphrase flow.
9. Verify executable properties show version 1.1.0 and expected metadata.
10. Ensure `README.md`, `PASSPHRASE_SECURITY.md`, `requirements.txt` are up to date.
11. Remove local test entries from production release bundle if needed.
